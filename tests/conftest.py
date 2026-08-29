import hashlib
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.connection import SessionLocal
from app.modules.auth.models import AuthSession, StepUpGrant, UserMfaFactor

settings = get_settings()


def enable_step_up_for_client(c: TestClient) -> None:
    """Helper for functional test suites to attach valid Step-Up grants to the test session."""
    cookie_val = c.cookies.get(settings.SESSION_COOKIE_NAME)
    if not cookie_val:
        return
    db = SessionLocal()
    try:
        t_hash = hashlib.sha256(cookie_val.encode("utf-8")).hexdigest()
        sess = (
            db.execute(select(AuthSession).where(AuthSession.token_hash == t_hash))
            .scalars()
            .first()
        )
        if not sess:
            return

        user_id = sess.user_id
        factor = (
            db.execute(
                select(UserMfaFactor).where(
                    UserMfaFactor.user_id == user_id,
                    UserMfaFactor.status == "ACTIVE",
                )
            )
            .scalars()
            .first()
        )

        if not factor:
            factor = UserMfaFactor(
                user_id=user_id,
                factor_type="TOTP",
                status="ACTIVE",
                secret_ciphertext="dummy_ct",
                secret_nonce="dummy_nonce",
                confirmed_at=datetime.now(timezone.utc),
            )
            db.add(factor)
            db.flush()

        now = datetime.now(timezone.utc)
        for policy in ["HIGH_RISK_ACTION", "CRITICAL_RISK_ACTION"]:
            existing_grant = (
                db.execute(
                    select(StepUpGrant).where(
                        StepUpGrant.user_id == user_id,
                        StepUpGrant.session_id == sess.id,
                        StepUpGrant.policy_code == policy,
                    )
                )
                .scalars()
                .first()
            )

            if not existing_grant:
                grant = StepUpGrant(
                    user_id=user_id,
                    session_id=sess.id,
                    policy_code=policy,
                    method="TOTP",
                    factor_id=factor.id,
                    verified_at=now,
                    expires_at=now + timedelta(hours=2),
                )
                db.add(grant)
        db.commit()
    finally:
        db.close()
