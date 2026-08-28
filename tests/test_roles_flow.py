import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scripts import seed_demo


@pytest.fixture
def client():
    return TestClient(app)


def test_system_roles_seeded_and_listed(client: TestClient):
    seed_demo.run_seed()
    response = client.get("/api/logistics/roles")
    assert response.status_code == 200
    roles = response.json()
    assert len(roles) >= 8

    sys_codes = {r["code"] for r in roles if r["is_system"]}
    expected_codes = {
        "SUPER_ADMIN",
        "LOGISTICS_ADMIN",
        "WAREHOUSE_SUPERVISOR",
        "WAREHOUSE_OPERATOR",
        "PURCHASING_OFFICER",
        "TRANSPORT_COORDINATOR",
        "DRIVER",
        "AUDITOR",
    }
    assert expected_codes.issubset(sys_codes)


def test_system_role_deletion_protection(client: TestClient):
    seed_demo.run_seed()
    response = client.get("/api/logistics/roles")
    roles = response.json()
    sys_role = next(r for r in roles if r["is_system"])

    del_res = client.delete(f"/api/logistics/roles/{sys_role['id']}")
    assert del_res.status_code == 409
    assert del_res.json()["code"] == "SYSTEM_ROLE_PROTECTED"


def test_custom_role_lifecycle(client: TestClient):
    # 1. Create custom role
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

    # 2. Reject duplicate code
    dup_res = client.post(
        "/api/logistics/roles",
        json={
            "code": code,
            "name": "Duplicate Code",
        },
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["code"] == "DUPLICATE_ROLE_CODE"

    # 3. Get role detail
    get_res = client.get(f"/api/logistics/roles/{role_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Custom Logistics Specialist"

    # 4. Update role
    patch_res = client.patch(
        f"/api/logistics/roles/{role_id}",
        json={"name": "Senior Logistics Specialist", "description": "Updated desc"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Senior Logistics Specialist"

    # 5. Delete custom role
    del_res = client.delete(f"/api/logistics/roles/{role_id}")
    assert del_res.status_code == 204

    # 6. Confirm Not Found
    confirm_res = client.get(f"/api/logistics/roles/{role_id}")
    assert confirm_res.status_code == 404
    assert confirm_res.json()["code"] == "ROLE_NOT_FOUND"


def test_role_organization_scoping(client: TestClient):
    # Organization not found for scoping
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
