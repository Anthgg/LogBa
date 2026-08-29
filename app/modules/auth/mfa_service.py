import io
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import pyotp
import qrcode
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError, UnauthorizedError, ValidationError
from app.modules.auth.mfa_crypto import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_recovery_codes,
)
from app.modules.auth.models import (
    MfaRecoveryCode,
    StepUpGrant,
    User,
    UserMfaFactor,
)
from app.modules.auth.password import verify_password
from app.shared.audit.contracts import AuditContext
from app.shared.audit.service import AuditService

settings = get_settings()
audit_service = AuditService()


class MfaService:
    def get_mfa_status(self, db: Session, user_id: uuid.UUID) -> Tuple[bool, List[str], int]:
        stmt = select(UserMfaFactor).where(
            UserMfaFactor.user_id == user_id,
            UserMfaFactor.status == "ACTIVE",
        )
        active_factor = db.execute(stmt).scalars().first()
        if not active_factor:
            return False, [], 0

        # Count unused recovery codes
        rec_stmt = select(func.count(MfaRecoveryCode.id)).where(
            MfaRecoveryCode.factor_id == active_factor.id,
            MfaRecoveryCode.used_at.is_(None),
        )
        remaining_codes = db.execute(rec_stmt).scalar() or 0

        return True, ["TOTP"], remaining_codes

    def enroll_totp(
        self,
        db: Session,
        user_id: uuid.UUID,
        current_password: str,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Tuple[uuid.UUID, str, str]:
        user = db.get(User, user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("Usuario inactivo o no encontrado.", code="USER_INACTIVE")

        # 1. Re-authenticate password before starting enrollment
        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedError("Contraseña actual incorrecta.", code="INVALID_PASSWORD")

        # 2. Invalidate any existing PENDING enrollment for this user
        pending_stmt = select(UserMfaFactor).where(
            UserMfaFactor.user_id == user_id,
            UserMfaFactor.status == "PENDING",
        )
        for old_pending in db.execute(pending_stmt).scalars().all():
            db.delete(old_pending)
        db.flush()

        # 3. Generate raw secret and encrypt at rest
        raw_secret = pyotp.random_base32()
        ciphertext, nonce = encrypt_totp_secret(raw_secret)

        factor = UserMfaFactor(
            user_id=user_id,
            factor_type="TOTP",
            status="PENDING",
            secret_ciphertext=ciphertext,
            secret_nonce=nonce,
            is_test_data=user.is_test_data,
        )
        db.add(factor)
        db.flush()

        # 4. Construct otpauth URI
        totp = pyotp.TOTP(raw_secret)
        otpauth_url = totp.provisioning_uri(
            name=user.email,
            issuer_name=settings.MFA_TOTP_ISSUER,
        )

        audit_service.record_event(
            db=db,
            context=AuditContext(
                correlation_id=correlation_id or uuid.uuid4(),
                actor_type="AUTHENTICATED",
                actor_id=user_id,
                organization_id=user.organization_id,
            ),
            resource_type="mfa",
            resource_id=factor.id,
            action="mfa.enrollment.started",
            result="SUCCESS",
        )
        db.commit()

        return factor.id, raw_secret, otpauth_url

    def generate_qr_image_bytes(
        self, db: Session, user_id: uuid.UUID, enrollment_id: uuid.UUID
    ) -> bytes:
        stmt = select(UserMfaFactor).where(
            UserMfaFactor.id == enrollment_id,
            UserMfaFactor.user_id == user_id,
            UserMfaFactor.status == "PENDING",
        )
        factor = db.execute(stmt).scalars().first()
        if not factor:
            raise NotFoundError(
                "Solicitud de enrolamiento no encontrada o expirada.", code="ENROLLMENT_NOT_FOUND"
            )

        user = db.get(User, user_id)
        if not user:
            raise NotFoundError("Usuario no encontrado.", code="USER_NOT_FOUND")

        raw_secret = decrypt_totp_secret(factor.secret_ciphertext, factor.secret_nonce)
        totp = pyotp.TOTP(raw_secret)
        otpauth_url = totp.provisioning_uri(
            name=user.email,
            issuer_name=settings.MFA_TOTP_ISSUER,
        )

        qr_img = qrcode.make(otpauth_url)
        buf = io.BytesIO()
        qr_img.save(buf, format="PNG")
        return buf.getvalue()

    def confirm_totp(
        self,
        db: Session,
        user_id: uuid.UUID,
        enrollment_id: uuid.UUID,
        code: str,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Tuple[uuid.UUID, List[str]]:
        now = datetime.now(timezone.utc)
        stmt = select(UserMfaFactor).where(
            UserMfaFactor.id == enrollment_id,
            UserMfaFactor.user_id == user_id,
            UserMfaFactor.status == "PENDING",
        )
        factor = db.execute(stmt).scalars().first()
        if not factor:
            raise NotFoundError(
                "Solicitud de enrolamiento no encontrada o ya confirmada.",
                code="ENROLLMENT_NOT_FOUND",
            )

        user = db.get(User, user_id)
        if not user:
            raise NotFoundError("Usuario no encontrado.", code="USER_NOT_FOUND")

        # 1. Decrypt and verify TOTP code
        raw_secret = decrypt_totp_secret(factor.secret_ciphertext, factor.secret_nonce)
        totp = pyotp.TOTP(raw_secret, interval=30, digits=6)

        if not totp.verify(code.strip(), valid_window=1):
            audit_service.record_event(
                db=db,
                context=AuditContext(
                    correlation_id=correlation_id or uuid.uuid4(),
                    actor_type="AUTHENTICATED",
                    actor_id=user_id,
                    organization_id=user.organization_id,
                ),
                resource_type="mfa",
                resource_id=factor.id,
                action="mfa.enrollment.failed",
                result="FAILURE",
                reason="INVALID_TOTP_CODE",
            )
            db.commit()
            raise ValidationError("Codigo de verificacion incorrecto.", code="INVALID_MFA_CODE")

        # 2. Disable any existing ACTIVE factor
        old_active_stmt = select(UserMfaFactor).where(
            UserMfaFactor.user_id == user_id,
            UserMfaFactor.status == "ACTIVE",
        )
        for old_f in db.execute(old_active_stmt).scalars().all():
            old_f.status = "DISABLED"
            old_f.disabled_at = now

        # 3. Activate this factor
        factor.status = "ACTIVE"
        factor.confirmed_at = now
        factor.last_used_counter = None

        # 4. Generate recovery codes (hashed in DB, plaintext returned once)
        plaintext_codes, hashed_codes = generate_recovery_codes(8)
        for h_code in hashed_codes:
            rec = MfaRecoveryCode(
                factor_id=factor.id,
                code_hash=h_code,
                created_at=now,
            )
            db.add(rec)

        audit_service.record_event(
            db=db,
            context=AuditContext(
                correlation_id=correlation_id or uuid.uuid4(),
                actor_type="AUTHENTICATED",
                actor_id=user_id,
                organization_id=user.organization_id,
            ),
            resource_type="mfa",
            resource_id=factor.id,
            action="mfa.enrollment.confirmed",
            result="SUCCESS",
        )
        db.commit()
        return factor.id, plaintext_codes

    def disable_mfa(
        self,
        db: Session,
        user_id: uuid.UUID,
        current_password: str,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        user = db.get(User, user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("Usuario no encontrado.", code="USER_NOT_FOUND")

        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedError("Contraseña actual incorrecta.", code="INVALID_PASSWORD")

        stmt = select(UserMfaFactor).where(
            UserMfaFactor.user_id == user_id,
            UserMfaFactor.status == "ACTIVE",
        )
        active_factors = db.execute(stmt).scalars().all()
        for f in active_factors:
            f.status = "DISABLED"
            f.disabled_at = now

        # Revoke all active Step-Up grants for this user
        grants_stmt = select(StepUpGrant).where(StepUpGrant.user_id == user_id)
        for g in db.execute(grants_stmt).scalars().all():
            db.delete(g)

        audit_service.record_event(
            db=db,
            context=AuditContext(
                correlation_id=correlation_id or uuid.uuid4(),
                actor_type="AUTHENTICATED",
                actor_id=user_id,
                organization_id=user.organization_id,
            ),
            resource_type="mfa",
            action="mfa.disabled",
            result="SUCCESS",
        )
        db.commit()

    def regenerate_recovery_codes(
        self,
        db: Session,
        user_id: uuid.UUID,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> List[str]:
        now = datetime.now(timezone.utc)
        stmt = select(UserMfaFactor).where(
            UserMfaFactor.user_id == user_id,
            UserMfaFactor.status == "ACTIVE",
        )
        factor = db.execute(stmt).scalars().first()
        if not factor:
            raise ValidationError(
                "El usuario no tiene MFA activo configurado.", code="MFA_NOT_CONFIGURED"
            )

        # Invalidate old recovery codes
        old_rec_stmt = select(MfaRecoveryCode).where(MfaRecoveryCode.factor_id == factor.id)
        for old_rec in db.execute(old_rec_stmt).scalars().all():
            db.delete(old_rec)
        db.flush()

        # Generate new recovery codes
        plaintext_codes, hashed_codes = generate_recovery_codes(8)
        for h_code in hashed_codes:
            rec = MfaRecoveryCode(
                factor_id=factor.id,
                code_hash=h_code,
                created_at=now,
            )
            db.add(rec)

        audit_service.record_event(
            db=db,
            context=AuditContext(
                correlation_id=correlation_id or uuid.uuid4(),
                actor_type="AUTHENTICATED",
                actor_id=user_id,
            ),
            resource_type="mfa",
            resource_id=factor.id,
            action="mfa.recovery_codes.regenerated",
            result="SUCCESS",
        )
        db.commit()
        return plaintext_codes
