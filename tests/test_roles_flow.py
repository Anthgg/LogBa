import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.csrf import generate_csrf_token
from app.scripts import seed_demo


@pytest.fixture
def client():
    c = TestClient(app)
    seed_demo.run_seed()
    csrf = generate_csrf_token()
    login_res = c.post(
        "/api/auth/login",
        json={
            "email": "gerencia.demo@logistica.local",
            "password": "DemoLogistics2026!Secure",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert login_res.status_code == 200
    return c


def csrf_headers():
    return {"X-CSRF-Token": generate_csrf_token()}


def test_10_canonical_logistics_profiles_present(client: TestClient):
    response = client.get("/api/logistics/roles")
    assert response.status_code == 200
    roles = response.json()

    expected_codes = {
        "PURCHASING",
        "RECEIVING",
        "QUALITY",
        "WAREHOUSE",
        "INVENTORY",
        "DISPATCH",
        "TRANSPORT",
        "DRIVER",
        "AUDITOR",
        "MANAGEMENT",
    }
    actual_codes = {r["code"] for r in roles if r["is_system"]}
    assert expected_codes.issubset(actual_codes)


def test_role_matrix_and_responsibilities_endpoint(client: TestClient):
    response = client.get("/api/logistics/roles/matrix")
    assert response.status_code == 200
    data = response.json()
    assert "canonical_profiles" in data
    assert "sod_conflicts" in data
    assert len(data["canonical_profiles"]) == 10


def test_system_role_deletion_protection(client: TestClient):
    roles = client.get("/api/logistics/roles").json()
    sys_role = next(r for r in roles if r["is_system"])

    del_res = client.delete(
        f"/api/logistics/roles/{sys_role['id']}",
        headers=csrf_headers(),
    )
    assert del_res.status_code == 409
    assert del_res.json()["code"] == "SYSTEM_ROLE_PROTECTED"


def test_custom_role_lifecycle(client: TestClient):
    code = f"CUSTOM-ROLE-{uuid.uuid4().hex[:6]}"
    create_res = client.post(
        "/api/logistics/roles",
        json={
            "code": code,
            "name": "Custom Operator",
            "description": "Custom role description",
            "is_system": False,
            "is_test_data": True,
        },
        headers=csrf_headers(),
    )
    assert create_res.status_code == 201
    role_id = create_res.json()["id"]

    patch_res = client.patch(
        f"/api/logistics/roles/{role_id}",
        json={"name": "Updated Custom Operator"},
        headers=csrf_headers(),
    )
    assert patch_res.status_code == 200

    del_res = client.delete(
        f"/api/logistics/roles/{role_id}",
        headers=csrf_headers(),
    )
    assert del_res.status_code == 204


def test_role_organization_scoping(client: TestClient):
    struct = client.get("/api/logistics/structure").json()
    org_id = struct["organizations"][0]["id"]

    org_role_code = f"ORG-ROLE-{uuid.uuid4().hex[:6]}"
    res = client.post(
        "/api/logistics/roles",
        json={
            "code": org_role_code,
            "name": "Org Scoped Role",
            "organization_id": org_id,
            "is_system": False,
            "is_test_data": True,
        },
        headers=csrf_headers(),
    )
    assert res.status_code == 201
    role_id = res.json()["id"]

    client.delete(
        f"/api/logistics/roles/{role_id}",
        headers=csrf_headers(),
    )


def test_production_seed_protection(monkeypatch):
    monkeypatch.setattr(seed_demo.settings, "APP_ENV", "production")
    with pytest.raises(RuntimeError, match="CRITICAL ERROR"):
        seed_demo.run_seed()
