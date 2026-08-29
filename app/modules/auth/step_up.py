import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import PreconditionRequiredError, ValidationError
from app.core.rbac import AuthenticatedPrincipal
from app.modules.auth.mfa_crypto import decrypt_totp_secret, hash_recovery_code
from app.modules.auth.models import (
    MfaRecoveryCode,
    StepUpChallenge,
    StepUpGrant,
    UserMfaFactor,
)
from app.modules.organization.permissions_catalog import CANONICAL_PERMISSIONS_CATALOG
from app.shared.audit.contracts import AuditContext
from app.shared.audit.service import AuditService

settings = get_settings()
audit_service = AuditService()


@dataclass(frozen=True)
class StepUpPolicy:
    policy_code: str
    min_risk: str
    challenge_ttl_seconds: int
    grant_ttl_seconds: int
    max_attempts: int


# Canonical Step-Up Policies
POLICIES: Dict[str, StepUpPolicy] = {
    "HIGH_RISK_ACTION": StepUpPolicy(
        policy_code="HIGH_RISK_ACTION",
        min_risk="HIGH",
        challenge_ttl_seconds=settings.STEP_UP_CHALLENGE_TTL_SECONDS,
        grant_ttl_seconds=settings.STEP_UP_HIGH_GRANT_TTL_SECONDS,
        max_attempts=settings.STEP_UP_MAX_ATTEMPTS,
    ),
    "CRITICAL_RISK_ACTION": StepUpPolicy(
        policy_code="CRITICAL_RISK_ACTION",
        min_risk="CRITICAL",
        challenge_ttl_seconds=settings.STEP_UP_CHALLENGE_TTL_SECONDS,
        grant_ttl_seconds=settings.STEP_UP_CRITICAL_GRANT_TTL_SECONDS,
        max_attempts=settings.STEP_UP_MAX_ATTEMPTS,
    ),
}

# Fast lookup for permission -> risk_level
PERMISSION_RISK_MAP: Dict[str, str] = {
    str(p["code"]): str(p["risk_level"])
    for p in CANONICAL_PERMISSIONS_CATALOG
    if p.get("code") and p.get("risk_level")
}


class StepUpPolicyEngine:
    def get_policy_for_permission(self, permission_code: str) -> Optional[StepUpPolicy]:
        risk_level = PERMISSION_RISK_MAP.get(permission_code, "LOW").upper()
        if risk_level == "CRITICAL":
            return POLICIES["CRITICAL_RISK_ACTION"]
        elif risk_level == "HIGH":
            return POLICIES["HIGH_RISK_ACTION"]
        return None

    def evaluate_step_up(
        self,
        db: Session,
        principal: AuthenticatedPrincipal,
        permission_code: str,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> None:
        policy = self.get_policy_for_permission(permission_code)
        if not policy:
            return  # LOW / MEDIUM does not require step-up

        now = datetime.now(timezone.utc)

        # 1. Check if user has an ACTIVE MFA factor
        active_factor_stmt = select(UserMfaFactor).where(
            UserMfaFactor.user_id == principal.user_id,
            UserMfaFactor.status == "ACTIVE",
        )
        active_factor = db.execute(active_factor_stmt).scalars().first()

        if not active_factor:
            raise PreconditionRequiredError(
                message="Operacion sensible requiere autenticacion multifactor (MFA) configurada.",
                code="MFA_ENROLLMENT_REQUIRED",
                details={
                    "required_action": "ENROLL_MFA",
                    "permission": permission_code,
                    "risk_level": policy.min_risk,
                },
            )

        # 2. Check if a valid grant exists for this specific session
        grant_stmt = (
            select(StepUpGrant)
            .where(
                StepUpGrant.user_id == principal.user_id,
                StepUpGrant.session_id == principal.session_id,
                StepUpGrant.policy_code == policy.policy_code,
                StepUpGrant.expires_at > now,
            )
            .order_by(StepUpGrant.expires_at.desc())
        )

        active_grant = db.execute(grant_stmt).scalars().first()
        if active_grant:
            return  # Valid session-bound grant active!

        # 3. Grant not found -> Create a new Step-Up challenge
        expires_at = now + timedelta(seconds=policy.challenge_ttl_seconds)
        challenge = StepUpChallenge(
            user_id=principal.user_id,
            session_id=principal.session_id,
            policy_code=policy.policy_code,
            reason_code="SENSITIVE_OPERATION",
            status="PENDING",
            created_at=now,
            expires_at=expires_at,
            attempt_count=0,
            max_attempts=policy.max_attempts,
            correlation_id=str(correlation_id) if correlation_id else None,
        )
        db.add(challenge)
        db.flush()

        audit_service.record_event(
            db=db,
            context=AuditContext(
                correlation_id=correlation_id or uuid.uuid4(),
                actor_type="AUTHENTICATED",
                actor_id=principal.user_id,
                session_id=principal.session_id,
                organization_id=principal.organization_id,
            ),
            resource_type="step_up",
            resource_id=challenge.id,
            action="step_up.challenge.created",
            result="SUCCESS",
            metadata={
                "policy_code": policy.policy_code,
                "permission": permission_code,
                "expires_at": expires_at.isoformat(),
            },
        )
        db.commit()

        raise PreconditionRequiredError(
            message="Esta accion sensible requiere verificacion adicional (Step-Up).",
            code="STEP_UP_REQUIRED",
            details={
                "challenge_id": str(challenge.id),
                "policy": policy.policy_code,
                "reason": "SENSITIVE_OPERATION",
                "methods": ["TOTP", "RECOVERY_CODE"],
                "expires_at": expires_at.isoformat(),
            },
        )

    def verify_step_up(
        self,
        db: Session,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        challenge_id: uuid.UUID,
        method: str,
        code: str,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> StepUpGrant:
        import pyotp

        now = datetime.now(timezone.utc)

        # 1. Retrieve and validate challenge
        stmt = select(StepUpChallenge).where(
            StepUpChallenge.id == challenge_id,
            StepUpChallenge.user_id == user_id,
            StepUpChallenge.session_id == session_id,
        )
        challenge = db.execute(stmt).scalars().first()
        if not challenge:
            raise ValidationError(
                message="Desafio de step-up no encontrado.",
                code="CHALLENGE_NOT_FOUND",
            )

        if challenge.status == "LOCKED":
            raise ValidationError(
                message="Desafio de step-up bloqueado por exceso de intentos.",
                code="CHALLENGE_LOCKED",
            )

        if challenge.status != "PENDING" or challenge.expires_at <= now:
            challenge.status = "EXPIRED"
            db.commit()
            raise ValidationError(
                message="El desafio de step-up ha expirado.",
                code="CHALLENGE_EXPIRED",
            )

        # 2. Retrieve user active MFA factor
        factor_stmt = select(UserMfaFactor).where(
            UserMfaFactor.user_id == user_id,
            UserMfaFactor.status == "ACTIVE",
        )
        factor = db.execute(factor_stmt).scalars().first()
        if not factor:
            raise ValidationError(
                message="El usuario no posee un factor MFA activo.",
                code="MFA_NOT_CONFIGURED",
            )

        verified = False
        method_upper = method.strip().upper()

        if method_upper == "TOTP":
            secret_plaintext = decrypt_totp_secret(factor.secret_ciphertext, factor.secret_nonce)
            totp = pyotp.TOTP(secret_plaintext, interval=30, digits=6)

            # Valid window: +-1 time step (30s)
            verified = totp.verify(code.strip(), valid_window=1)

            if verified:
                # Anti-replay protection
                current_time_step = int(time.time() // 30)
                if (
                    factor.last_used_counter is not None
                    and current_time_step <= factor.last_used_counter
                ):
                    # Counter replay attempt!
                    verified = False
                    challenge.attempt_count += 1
                    if challenge.attempt_count >= challenge.max_attempts:
                        challenge.status = "LOCKED"
                    db.commit()
                    raise ValidationError(
                        message="Codigo TOTP ya utilizado. Espere el siguiente ciclo.",
                        code="TOTP_REPLAY_DETECTED",
                    )
                factor.last_used_counter = current_time_step

        elif method_upper == "RECOVERY_CODE":
            code_h = hash_recovery_code(code)
            rec_stmt = select(MfaRecoveryCode).where(
                MfaRecoveryCode.factor_id == factor.id,
                MfaRecoveryCode.code_hash == code_h,
                MfaRecoveryCode.used_at.is_(None),
            )
            rec_code = db.execute(rec_stmt).scalars().first()
            if rec_code:
                rec_code.used_at = now
                verified = True
                audit_service.record_event(
                    db=db,
                    context=AuditContext(
                        correlation_id=correlation_id or uuid.uuid4(),
                        actor_type="AUTHENTICATED",
                        actor_id=user_id,
                        session_id=session_id,
                    ),
                    resource_type="mfa",
                    resource_id=factor.id,
                    action="mfa.recovery_code.used",
                    result="SUCCESS",
                )

        else:
            raise ValidationError(
                message="Metodo de verificacion no soportado.",
                code="UNSUPPORTED_MFA_METHOD",
            )

        if not verified:
            challenge.attempt_count += 1
            if challenge.attempt_count >= challenge.max_attempts:
                challenge.status = "LOCKED"
                audit_action = "step_up.challenge.locked"
            else:
                audit_action = "step_up.verification.failure"

            audit_service.record_event(
                db=db,
                context=AuditContext(
                    correlation_id=correlation_id or uuid.uuid4(),
                    actor_type="AUTHENTICATED",
                    actor_id=user_id,
                    session_id=session_id,
                ),
                resource_type="step_up",
                resource_id=challenge.id,
                action=audit_action,
                result="FAILURE",
                reason="INVALID_CODE",
                metadata={"method": method_upper, "attempt_count": challenge.attempt_count},
            )
            db.commit()
            raise ValidationError(
                message="Codigo de verificacion incorrecto.",
                code="INVALID_STEP_UP_CODE",
                details={
                    "attempt_count": challenge.attempt_count,
                    "max_attempts": challenge.max_attempts,
                },
            )

        # 3. Create Session-bound Step-Up Grant
        policy = POLICIES.get(challenge.policy_code, POLICIES["HIGH_RISK_ACTION"])
        grant_expires_at = now + timedelta(seconds=policy.grant_ttl_seconds)

        challenge.status = "VERIFIED"

        grant = StepUpGrant(
            user_id=user_id,
            session_id=session_id,
            policy_code=challenge.policy_code,
            method=method_upper,
            factor_id=factor.id,
            verified_at=now,
            expires_at=grant_expires_at,
            correlation_id=str(correlation_id) if correlation_id else None,
        )
        db.add(grant)
        db.flush()

        audit_service.record_event(
            db=db,
            context=AuditContext(
                correlation_id=correlation_id or uuid.uuid4(),
                actor_type="AUTHENTICATED",
                actor_id=user_id,
                session_id=session_id,
            ),
            resource_type="step_up",
            resource_id=grant.id,
            action="step_up.grant.created",
            result="SUCCESS",
            metadata={
                "policy_code": challenge.policy_code,
                "method": method_upper,
                "expires_at": grant_expires_at.isoformat(),
            },
        )
        db.commit()
        return grant
