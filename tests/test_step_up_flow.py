import time
import uuid

import pyotp
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.modules.auth.csrf import generate_csrf_token
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


def enroll_and_activate_mfa(c: TestClient):
    enroll_res = c.post(
        "/api/auth/mfa/totp/enroll",
        json={"current_password": settings.DEMO_USER_PASSWORD},
        headers=csrf_headers(),
    )
    assert enroll_res.status_code == 200
    enroll_data = enroll_res.json()
    manual_key = enroll_data["manual_key"]
    enrollment_id = enroll_data["enrollment_id"]

    totp = pyotp.TOTP(manual_key)
    # Confirm using previous time-step so current time-step is fresh for challenge verification
    confirm_code = totp.at(int(time.time()) - 30)
    confirm_res = c.post(
        "/api/auth/mfa/totp/confirm",
        json={"enrollment_id": enrollment_id, "code": confirm_code},
        headers=csrf_headers(),
    )
    assert confirm_res.status_code == 200
    return manual_key, confirm_res.json()["recovery_codes"]


def test_low_risk_permission_does_not_require_step_up(client: TestClient):
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    # organization.read is LOW risk
    res = client.get("/api/logistics/structure")
    assert res.status_code == 200


def test_high_risk_without_mfa_triggers_428_mfa_enrollment_required(client: TestClient):
    seed_demo.run_seed()
    user_info = login_client(client, "gerencia.demo@logistica.local")
    user_id = user_info["user"]["id"]

    # users.disable is HIGH risk -> user has no MFA configured
    res = client.patch(
        f"/api/logistics/users/{user_id}/disable",
        headers=csrf_headers(),
    )
    assert res.status_code == 428
    data = res.json()
    assert data["code"] == "MFA_ENROLLMENT_REQUIRED"


def test_high_risk_with_active_mfa_triggers_428_step_up_required(client: TestClient):
    seed_demo.run_seed()
    user_info = login_client(client, "gerencia.demo@logistica.local")
    user_id = user_info["user"]["id"]

    # 1. Activate MFA
    enroll_and_activate_mfa(client)

    # 2. Try HIGH risk action without Step-Up grant
    res = client.patch(
        f"/api/logistics/users/{user_id}/disable",
        headers=csrf_headers(),
    )
    assert res.status_code == 428
    data = res.json()
    assert data["code"] == "STEP_UP_REQUIRED"
    assert "challenge_id" in data["details"]
    assert data["details"]["policy"] == "HIGH_RISK_ACTION"


def test_step_up_verification_and_subsequent_execution(client: TestClient):
    seed_demo.run_seed()
    user_info = login_client(client, "gerencia.demo@logistica.local")
    org_id = user_info["organization_id"]

    # 1. Activate MFA
    manual_key, _ = enroll_and_activate_mfa(client)

    # 2. Create target user to disable
    target_email = f"test-target-{uuid.uuid4().hex[:6]}@logistica.local"
    create_res = client.post(
        "/api/logistics/users",
        json={
            "organization_id": org_id,
            "email": target_email,
            "display_name": "Target User",
            "initial_password": "InitialSecurePassword2026!",
            "role_codes": ["WAREHOUSE"],
            "is_test_data": True,
        },
        headers=csrf_headers(),
    )
    # Note: users.create is HIGH risk, triggers step-up!
    assert create_res.status_code == 428
    challenge_id = create_res.json()["details"]["challenge_id"]

    # 3. Verify Step-Up challenge with TOTP
    totp = pyotp.TOTP(manual_key)
    verify_res = client.post(
        "/api/auth/step-up/verify",
        json={
            "challenge_id": challenge_id,
            "method": "TOTP",
            "code": totp.now(),
        },
        headers=csrf_headers(),
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "VERIFIED"

    # 4. Retry sensitive operation (users.create) -> Now succeeds because grant is active!
    create_res_2 = client.post(
        "/api/logistics/users",
        json={
            "organization_id": org_id,
            "email": target_email,
            "display_name": "Target User",
            "initial_password": "InitialSecurePassword2026!",
            "role_codes": ["WAREHOUSE"],
            "is_test_data": True,
        },
        headers=csrf_headers(),
    )
    assert create_res_2.status_code == 201


def test_step_up_session_isolation():
    seed_demo.run_seed()
    client_a = TestClient(app)
    client_b = TestClient(app)

    # 1. Login in Session A and activate MFA
    user_info = login_client(client_a, "gerencia.demo@logistica.local")
    org_id = user_info["organization_id"]
    manual_key, _ = enroll_and_activate_mfa(client_a)

    # 2. Trigger step-up in Session A and verify
    res_a = client_a.post(
        "/api/logistics/users",
        json={
            "organization_id": org_id,
            "email": f"isolated-a-{uuid.uuid4().hex[:6]}@logistica.local",
            "display_name": "Isolated User A",
            "initial_password": "InitialSecurePassword2026!",
            "is_test_data": True,
        },
        headers=csrf_headers(),
    )
    assert res_a.status_code == 428
    challenge_a = res_a.json()["details"]["challenge_id"]

    totp = pyotp.TOTP(manual_key)
    verify_a = client_a.post(
        "/api/auth/step-up/verify",
        json={"challenge_id": challenge_a, "method": "TOTP", "code": totp.now()},
        headers=csrf_headers(),
    )
    assert verify_a.status_code == 200

    # 3. Login in Session B as same user
    login_client(client_b, "gerencia.demo@logistica.local")

    # 4. Try sensitive operation in Session B -> MUST STILL REQUIRE STEP-UP (Grant A not reused!)
    res_b = client_b.post(
        "/api/logistics/users",
        json={
            "organization_id": org_id,
            "email": f"isolated-b-{uuid.uuid4().hex[:6]}@logistica.local",
            "display_name": "Isolated User B",
            "initial_password": "InitialSecurePassword2026!",
            "is_test_data": True,
        },
        headers=csrf_headers(),
    )
    assert res_b.status_code == 428
    assert res_b.json()["code"] == "STEP_UP_REQUIRED"


def test_step_up_with_recovery_code_and_single_use(client: TestClient):
    seed_demo.run_seed()
    user_info = login_client(client, "gerencia.demo@logistica.local")
    org_id = user_info["organization_id"]

    # 1. Activate MFA & obtain recovery codes
    _, recovery_codes = enroll_and_activate_mfa(client)
    first_code = recovery_codes[0]

    # 2. Trigger step-up
    res = client.post(
        "/api/logistics/users",
        json={
            "organization_id": org_id,
            "email": f"rec-user-1-{uuid.uuid4().hex[:6]}@logistica.local",
            "display_name": "Rec User 1",
            "initial_password": "InitialSecurePassword2026!",
            "is_test_data": True,
        },
        headers=csrf_headers(),
    )
    challenge_id_1 = res.json()["details"]["challenge_id"]

    # 3. Verify with recovery code
    verify_res = client.post(
        "/api/auth/step-up/verify",
        json={
            "challenge_id": challenge_id_1,
            "method": "RECOVERY_CODE",
            "code": first_code,
        },
        headers=csrf_headers(),
    )
    assert verify_res.status_code == 200

    # 4. Trigger second step-up and try reusing the SAME recovery code -> MUST FAIL
    # The first code is marked used_at and cannot be reused
    bad_reuse_res = client.post(
        "/api/auth/step-up/verify",
        json={
            "challenge_id": challenge_id_1,
            "method": "RECOVERY_CODE",
            "code": first_code,
        },
        headers=csrf_headers(),
    )
    assert bad_reuse_res.status_code == 422


def test_rbac_403_before_step_up(client: TestClient):
    seed_demo.run_seed()
    # Login as WAREHOUSE operator (no permission for users.roles.assign)
    login_client(client, "almacen.demo@logistica.local")

    # users.roles.assign is CRITICAL risk, but WAREHOUSE lacks permission
    res = client.put(
        f"/api/logistics/users/{uuid.uuid4()}/roles",
        json={"role_codes": ["MANAGEMENT"]},
        headers=csrf_headers(),
    )
    # Order requirement: MUST FAIL WITH 403 PERMISSION_DENIED, NOT 428!
    assert res.status_code == 403
    assert res.json()["code"] == "PERMISSION_DENIED"


def test_step_up_max_attempts_lock(client: TestClient):
    seed_demo.run_seed()
    user_info = login_client(client, "gerencia.demo@logistica.local")
    org_id = user_info["organization_id"]

    # 1. Activate MFA
    enroll_and_activate_mfa(client)

    # 2. Trigger step-up
    res = client.post(
        "/api/logistics/users",
        json={
            "organization_id": org_id,
            "email": f"lock-{uuid.uuid4().hex[:6]}@logistica.local",
            "display_name": "Lock User",
            "initial_password": "InitialSecurePassword2026!",
            "is_test_data": True,
        },
        headers=csrf_headers(),
    )
    challenge_id = res.json()["details"]["challenge_id"]

    # 3. Fail 5 times
    for _ in range(5):
        client.post(
            "/api/auth/step-up/verify",
            json={
                "challenge_id": challenge_id,
                "method": "TOTP",
                "code": "111111",
            },
            headers=csrf_headers(),
        )

    # 4. Next attempt must return CHALLENGE_LOCKED
    locked_res = client.post(
        "/api/auth/step-up/verify",
        json={
            "challenge_id": challenge_id,
            "method": "TOTP",
            "code": "111111",
        },
        headers=csrf_headers(),
    )
    assert locked_res.status_code == 422
    assert locked_res.json()["code"] == "CHALLENGE_LOCKED"
