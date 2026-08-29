import time
import uuid

import pyotp
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import ValidationError
from app.db.connection import SessionLocal
from app.main import app
from app.modules.auth.csrf import generate_csrf_token, validate_csrf_token
from app.modules.auth.models import AuthSession, User
from app.modules.auth.password import (
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.scripts import seed_demo
from tests.conftest import enable_step_up_for_client

settings = get_settings()


def csrf_headers():
    return {"X-CSRF-Token": generate_csrf_token()}


def enroll_mfa_and_grant_step_up_auth(client: TestClient):
    enroll_res = client.post(
        "/api/auth/mfa/totp/enroll",
        json={"current_password": settings.DEMO_USER_PASSWORD},
        headers=csrf_headers(),
    )
    if enroll_res.status_code == 200:
        data = enroll_res.json()
        manual_key = data["manual_key"]
        totp = pyotp.TOTP(manual_key)
        client.post(
            "/api/auth/mfa/totp/confirm",
            json={"enrollment_id": data["enrollment_id"], "code": totp.at(int(time.time()) - 30)},
            headers=csrf_headers(),
        )
        return manual_key
    return None


@pytest.fixture
def client():
    return TestClient(app)


def get_csrf(client: TestClient) -> str:
    res = client.get("/api/auth/csrf")
    assert res.status_code == 200
    return res.json()["csrf_token"]


def test_password_argon2id_hashing_and_verification():
    raw_pwd = "SuperSecretPassword2026!"
    hashed = hash_password(raw_pwd)
    assert hashed.startswith("$argon2id$")
    assert verify_password(raw_pwd, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False


def test_password_policy_min_length():
    validate_password_policy("123456789012")  # 12 chars -> pass
    with pytest.raises(ValidationError, match="12 caracteres"):
        validate_password_policy("short")


def test_csrf_token_signing_and_validation():
    token = generate_csrf_token()
    assert validate_csrf_token(token) is True
    assert validate_csrf_token("invalid:token:format") is False
    assert validate_csrf_token("") is False


def test_login_flow_and_session_cookie(client: TestClient):
    seed_demo.run_seed()
    csrf = get_csrf(client)

    # 1. Login with demo credentials
    login_res = client.post(
        "/api/auth/login",
        json={
            "email": "gerencia.demo@logistica.local",
            "password": settings.DEMO_USER_PASSWORD,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["user"]["email"] == "gerencia.demo@logistica.local"
    assert "MANAGEMENT" in data["roles"]
    assert "organization.read" in data["permissions"]
    assert "password_hash" not in str(data)

    # Verify HttpOnly session cookie was set
    cookie = client.cookies.get(settings.SESSION_COOKIE_NAME)
    assert cookie is not None

    # Verify token in DB is hashed, NOT plaintext
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email_normalized="gerencia.demo@logistica.local").first()
        assert user is not None
        session = (
            db.query(AuthSession)
            .filter_by(user_id=user.id)
            .order_by(AuthSession.created_at.desc())
            .first()
        )
        assert session is not None
        assert session.token_hash != cookie
        assert len(session.token_hash) == 64  # SHA-256 hex length
    finally:
        db.close()


def test_login_invalid_credentials_and_audit(client: TestClient):
    seed_demo.run_seed()
    csrf = get_csrf(client)
    corr_id = str(uuid.uuid4())

    # Invalid password
    bad_res = client.post(
        "/api/auth/login",
        json={
            "email": "gerencia.demo@logistica.local",
            "password": "WrongPassword123!",
        },
        headers={"X-CSRF-Token": csrf, "X-Correlation-ID": corr_id},
    )
    assert bad_res.status_code == 401
    assert bad_res.json()["code"] == "INVALID_CREDENTIALS"

    # Inexistent email
    bad_email_res = client.post(
        "/api/auth/login",
        json={
            "email": "nonexistent@logistica.local",
            "password": settings.DEMO_USER_PASSWORD,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert bad_email_res.status_code == 401
    assert bad_email_res.json()["code"] == "INVALID_CREDENTIALS"


def test_auth_me_endpoint_and_lifecycle(client: TestClient):
    seed_demo.run_seed()
    # 1. Unauthenticated -> 401
    unauth_res = client.get("/api/auth/me")
    assert unauth_res.status_code == 401
    assert unauth_res.json()["code"] == "AUTHENTICATION_REQUIRED"

    # 2. Login
    csrf = get_csrf(client)
    login_res = client.post(
        "/api/auth/login",
        json={
            "email": "almacen.demo@logistica.local",
            "password": settings.DEMO_USER_PASSWORD,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert login_res.status_code == 200

    # 3. Authenticated me
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["user"]["email"] == "almacen.demo@logistica.local"
    assert "WAREHOUSE" in me_data["roles"]
    assert "warehouse.read" in me_data["permissions"]

    # 4. Logout
    csrf2 = get_csrf(client)
    logout_res = client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": csrf2},
    )
    assert logout_res.status_code == 200

    # 5. After logout -> 401
    post_logout_res = client.get("/api/auth/me")
    assert post_logout_res.status_code == 401


def test_rbac_http_enforcement_and_permission_denial(client: TestClient):
    seed_demo.run_seed()
    csrf = get_csrf(client)

    # 1. Login as WAREHOUSE operator
    client.post(
        "/api/auth/login",
        json={
            "email": "almacen.demo@logistica.local",
            "password": settings.DEMO_USER_PASSWORD,
        },
        headers={"X-CSRF-Token": csrf},
    )

    # 2. Allowed operation: read structure (requires organization.read)
    struct_res = client.get("/api/logistics/structure")
    assert struct_res.status_code == 200

    # 3. Forbidden operation: create role (requires roles.create) -> 403
    csrf_op = get_csrf(client)
    corr_id = str(uuid.uuid4())
    deny_res = client.post(
        "/api/logistics/roles",
        json={
            "code": "ILLEGAL-ROLE",
            "name": "Illegal Role",
            "description": "Attempted role creation",
        },
        headers={"X-CSRF-Token": csrf_op, "X-Correlation-ID": corr_id},
    )
    assert deny_res.status_code == 403
    assert deny_res.json()["code"] == "PERMISSION_DENIED"


def test_auditor_access_and_read_only_policy(client: TestClient):
    seed_demo.run_seed()
    csrf = get_csrf(client)

    # 1. Login as AUDITOR
    client.post(
        "/api/auth/login",
        json={
            "email": "auditor.demo@logistica.local",
            "password": settings.DEMO_USER_PASSWORD,
        },
        headers={"X-CSRF-Token": csrf},
    )

    # 2. Allowed: read audit events
    audit_res = client.get("/api/logistics/audit-events")
    assert audit_res.status_code == 200

    # 3. Allowed: export audit CSV
    export_res = client.get("/api/logistics/audit-events/export")
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers["content-type"]

    # 4. Denied: mutate organization -> 403
    csrf_op = get_csrf(client)
    mutate_res = client.post(
        "/api/logistics/organizations",
        json={"code": "ILLEGAL-ORG", "name": "Illegal Org"},
        headers={"X-CSRF-Token": csrf_op},
    )
    assert mutate_res.status_code == 403
    assert mutate_res.json()["code"] == "PERMISSION_DENIED"


def test_user_administration_lifecycle(client: TestClient):
    seed_demo.run_seed()
    csrf = get_csrf(client)

    # Login as MANAGEMENT
    client.post(
        "/api/auth/login",
        json={
            "email": "gerencia.demo@logistica.local",
            "password": settings.DEMO_USER_PASSWORD,
        },
        headers={"X-CSRF-Token": csrf},
    )
    enable_step_up_for_client(client)

    # 1. Get organization ID
    struct_res = client.get("/api/logistics/structure")
    org_id = struct_res.json()["organizations"][0]["id"]

    # 2. Create new user
    new_email = f"user-{uuid.uuid4().hex[:6]}@logistica.local"
    create_csrf = get_csrf(client)
    create_res = client.post(
        "/api/logistics/users",
        json={
            "organization_id": org_id,
            "email": new_email,
            "display_name": "Test Operator",
            "initial_password": "InitialSecurePassword2026!",
            "role_codes": ["WAREHOUSE"],
            "is_test_data": True,
        },
        headers={"X-CSRF-Token": create_csrf},
    )
    assert create_res.status_code == 201
    user_data = create_res.json()
    user_id = user_data["id"]
    assert user_data["email"] == new_email
    assert "WAREHOUSE" in user_data["roles"]

    # 3. List users
    list_res = client.get("/api/logistics/users")
    assert list_res.status_code == 200
    assert any(u["id"] == user_id for u in list_res.json())

    # 4. Assign role
    assign_csrf = get_csrf(client)
    assign_res = client.put(
        f"/api/logistics/users/{user_id}/roles",
        json={"role_codes": ["INVENTORY"]},
        headers={"X-CSRF-Token": assign_csrf},
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["roles"] == ["INVENTORY"]

    # 5. Disable user
    dis_csrf = get_csrf(client)
    dis_res = client.patch(
        f"/api/logistics/users/{user_id}/disable",
        headers={"X-CSRF-Token": dis_csrf},
    )
    assert dis_res.status_code == 200
    assert dis_res.json()["is_active"] is False


def test_production_secure_cookie_enforcement(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "SESSION_COOKIE_SECURE", False)
    with pytest.raises(RuntimeError, match="PRODUCTION_SECURE_COOKIE_ENFORCED_VIOLATION"):
        settings.enforce_production_security()
