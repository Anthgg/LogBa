import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scripts import seed_demo

CANONICAL_PROFILES_SET = {
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


@pytest.fixture
def client():
    return TestClient(app)


def test_10_canonical_logistics_profiles_present(client: TestClient):
    seed_demo.run_seed()
    response = client.get("/api/logistics/roles")
    assert response.status_code == 200
    roles = response.json()

    sys_roles_map = {r["code"]: r for r in roles if r["is_system"]}
    for profile in CANONICAL_PROFILES_SET:
        assert profile in sys_roles_map, f"Missing canonical profile: {profile}"
        assert sys_roles_map[profile]["is_system"] is True
        assert sys_roles_map[profile]["is_active"] is True
        assert sys_roles_map[profile]["organization_id"] is None


def test_role_matrix_and_responsibilities_endpoint(client: TestClient):
    response = client.get("/api/logistics/roles/matrix")
    assert response.status_code == 200
    data = response.json()

    # 1. Canonical profiles in matrix
    assert "canonical_profiles" in data
    profiles = data["canonical_profiles"]
    assert len(profiles) == 10
    profile_codes = {p["role_code"] for p in profiles}
    assert profile_codes == CANONICAL_PROFILES_SET

    for p in profiles:
        assert len(p["responsibilities"]) >= 3
        assert len(p["operational_scope"]) > 0

    # 2. SoD conflicts in matrix
    assert "sod_conflicts" in data
    conflicts = data["sod_conflicts"]
    assert len(conflicts) >= 7

    for c in conflicts:
        assert c["role_a"] in CANONICAL_PROFILES_SET
        assert c["role_b"] in CANONICAL_PROFILES_SET
        assert c["conflict_level"] in {"HIGH_RISK", "REVIEW_REQUIRED", "NONE"}
        assert len(c["reason"]) > 10
        assert len(c["policy"]) > 10


def test_system_role_deletion_protection(client: TestClient):
    seed_demo.run_seed()
    response = client.get("/api/logistics/roles")
    roles = response.json()
    sys_role = next(r for r in roles if r["code"] == "WAREHOUSE")

    del_res = client.delete(f"/api/logistics/roles/{sys_role['id']}")
    assert del_res.status_code == 409
    assert del_res.json()["code"] == "SYSTEM_ROLE_PROTECTED"


def test_custom_role_lifecycle(client: TestClient):
    code = f"TEST-ROLE-{uuid.uuid4().hex[:6]}"
    create_res = client.post(
        "/api/logistics/roles",
        json={
            "code": code,
            "name": "Custom Logistics Specialist",
            "description": "Specialist in reverse logistics",
            "is_system": False,
            "is_test_data": True,
        },
    )
    assert create_res.status_code == 201
    role_data = create_res.json()
    role_id = role_data["id"]
    assert role_data["code"] == code
    assert role_data["is_system"] is False

    # Duplicate code rejection
    dup_res = client.post(
        "/api/logistics/roles",
        json={"code": code, "name": "Duplicate Code"},
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["code"] == "DUPLICATE_ROLE_CODE"

    # Get role
    get_res = client.get(f"/api/logistics/roles/{role_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Custom Logistics Specialist"

    # Update role
    patch_res = client.patch(
        f"/api/logistics/roles/{role_id}",
        json={"name": "Senior Logistics Specialist", "description": "Updated desc"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Senior Logistics Specialist"

    # Delete custom role
    del_res = client.delete(f"/api/logistics/roles/{role_id}")
    assert del_res.status_code == 204

    # Confirm Not Found
    confirm_res = client.get(f"/api/logistics/roles/{role_id}")
    assert confirm_res.status_code == 404
    assert confirm_res.json()["code"] == "ROLE_NOT_FOUND"


def test_role_organization_scoping(client: TestClient):
    # Invalid organization scoping
    random_org_id = str(uuid.uuid4())
    bad_res = client.post(
        "/api/logistics/roles",
        json={
            "code": f"ORG-ROLE-{uuid.uuid4().hex[:6]}",
            "name": "Org Role",
            "organization_id": random_org_id,
        },
    )
    assert bad_res.status_code == 404
    assert bad_res.json()["code"] == "ORGANIZATION_NOT_FOUND"


def test_production_seed_protection(monkeypatch):
    monkeypatch.setattr(seed_demo.settings, "APP_ENV", "production")
    with pytest.raises(RuntimeError, match="CRITICAL ERROR"):
        seed_demo.run_seed()
