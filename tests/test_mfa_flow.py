import uuid

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.connection import SessionLocal
from app.main import app
from app.modules.auth.csrf import generate_csrf_token
from app.modules.auth.mfa_crypto import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    hash_recovery_code,
)
from app.modules.auth.models import MfaRecoveryCode, UserMfaFactor
from app.scripts import seed_demo

settings = get_settings()


@pytest.fixture
def client():
    return TestClient(app)


def csrf_headers():
    return {"X-CSRF-Token": generate_csrf_token()}


def login_client(c: TestClient, email: str, password: str = settings.DEMO_USER_PASSWORD):
    csrf = generate_csrf_token()
    res = c.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200
    return res.json()


def test_mfa_crypto_encryption_and_decryption():
    secret = pyotp.random_base32()
    ciphertext, nonce = encrypt_totp_secret(secret)
    assert ciphertext != secret
    assert nonce is not None

    decrypted = decrypt_totp_secret(ciphertext, nonce)
    assert decrypted == secret


def test_mfa_status_endpoint(client: TestClient):
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    res = client.get("/api/auth/mfa/status")
    assert res.status_code == 200
    data = res.json()
    assert "enabled" in data
    assert "methods" in data
    assert "recovery_codes_remaining" in data


def test_mfa_totp_enrollment_and_qr_endpoint(client: TestClient):
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    # 1. Start Enrollment
    enroll_res = client.post(
        "/api/auth/mfa/totp/enroll",
        json={"current_password": settings.DEMO_USER_PASSWORD},
        headers=csrf_headers(),
    )
    assert enroll_res.status_code == 200
    data = enroll_res.json()
    assert "enrollment_id" in data
    assert "manual_key" in data
    assert "qr_endpoint" in data
    assert "otpauth_url" in data

    enrollment_id = data["enrollment_id"]

    # 2. Get QR image from backend
    qr_res = client.get(data["qr_endpoint"])
    assert qr_res.status_code == 200
    assert qr_res.headers["content-type"] == "image/png"
    assert len(qr_res.content) > 100

    # 3. Check DB factor state (Encrypted at rest, status PENDING)
    db = SessionLocal()
    try:
        factor = db.get(UserMfaFactor, uuid.UUID(enrollment_id))
        assert factor is not None
        assert factor.status == "PENDING"
        assert factor.secret_ciphertext != data["manual_key"]
        # Decrypt check
        decrypted = decrypt_totp_secret(factor.secret_ciphertext, factor.secret_nonce)
        assert decrypted == data["manual_key"]
    finally:
        db.close()


def test_mfa_totp_confirmation_and_recovery_codes(client: TestClient):
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    # 1. Enroll
    enroll_res = client.post(
        "/api/auth/mfa/totp/enroll",
        json={"current_password": settings.DEMO_USER_PASSWORD},
        headers=csrf_headers(),
    )
    enroll_data = enroll_res.json()
    manual_key = enroll_data["manual_key"]
    enrollment_id = enroll_data["enrollment_id"]

    # 2. Confirm with Invalid code -> must fail
    bad_confirm = client.post(
        "/api/auth/mfa/totp/confirm",
        json={"enrollment_id": enrollment_id, "code": "000000"},
        headers=csrf_headers(),
    )
    assert bad_confirm.status_code == 422

    # 3. Confirm with Valid TOTP code
    totp = pyotp.TOTP(manual_key)
    valid_code = totp.now()

    confirm_res = client.post(
        "/api/auth/mfa/totp/confirm",
        json={"enrollment_id": enrollment_id, "code": valid_code},
        headers=csrf_headers(),
    )
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["status"] == "ACTIVE"
    assert "recovery_codes" in confirm_data
    assert len(confirm_data["recovery_codes"]) == 8

    # 4. Verify DB persistence and single-use recovery code hashes
    db = SessionLocal()
    try:
        factor = db.get(UserMfaFactor, uuid.UUID(enrollment_id))
        assert factor is not None
        assert factor.status == "ACTIVE"
        assert factor.confirmed_at is not None

        # Recovery codes hashed
        rec_codes = (
            db.execute(select(MfaRecoveryCode).where(MfaRecoveryCode.factor_id == factor.id))
            .scalars()
            .all()
        )
        assert len(rec_codes) == 8
        first_plaintext = confirm_data["recovery_codes"][0]
        first_hash = hash_recovery_code(first_plaintext)
        assert any(r.code_hash == first_hash for r in rec_codes)
    finally:
        db.close()

    # 5. Check status endpoint reflects ACTIVE MFA
    status_res = client.get("/api/auth/mfa/status")
    assert status_res.status_code == 200
    assert status_res.json()["enabled"] is True
    assert status_res.json()["recovery_codes_remaining"] == 8


def test_mfa_disable_and_recovery_regeneration(client: TestClient):
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    # 1. Enroll and Activate
    enroll_res = client.post(
        "/api/auth/mfa/totp/enroll",
        json={"current_password": settings.DEMO_USER_PASSWORD},
        headers=csrf_headers(),
    )
    enroll_data = enroll_res.json()
    totp = pyotp.TOTP(enroll_data["manual_key"])
    client.post(
        "/api/auth/mfa/totp/confirm",
        json={"enrollment_id": enroll_data["enrollment_id"], "code": totp.now()},
        headers=csrf_headers(),
    )

    # 2. Regenerate Recovery Codes
    regen_res = client.post(
        "/api/auth/mfa/recovery-codes/regenerate",
        headers=csrf_headers(),
    )
    assert regen_res.status_code == 200
    assert len(regen_res.json()["recovery_codes"]) == 8

    # 3. Disable MFA with wrong password -> fails
    bad_disable = client.post(
        "/api/auth/mfa/disable",
        json={"current_password": "WrongPassword123!"},
        headers=csrf_headers(),
    )
    assert bad_disable.status_code == 401

    # 4. Disable MFA with correct password -> succeeds
    disable_res = client.post(
        "/api/auth/mfa/disable",
        json={"current_password": settings.DEMO_USER_PASSWORD},
        headers=csrf_headers(),
    )
    assert disable_res.status_code == 200
    assert disable_res.json()["status"] == "mfa_disabled"

    # Status now reports disabled
    status_res = client.get("/api/auth/mfa/status")
    assert status_res.json()["enabled"] is False
