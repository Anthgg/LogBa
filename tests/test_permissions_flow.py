import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.rbac import AuthorizationContext
from app.main import app
from app.modules.auth.csrf import generate_csrf_token
from app.modules.organization.permissions_catalog import (
    CANONICAL_PERMISSIONS_CATALOG,
    CANONICAL_ROLE_BASELINES,
    ENDPOINT_PERMISSION_MATRIX,
)
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


def test_permission_catalog_completeness(client: TestClient):
    response = client.get("/api/logistics/permissions")
    assert response.status_code == 200
    perms = response.json()
    assert len(perms) >= len(CANONICAL_PERMISSIONS_CATALOG)

    perm_codes = {p["code"] for p in perms}
    for catalog_item in CANONICAL_PERMISSIONS_CATALOG:
        assert catalog_item["code"] in perm_codes
        item = next(p for p in perms if p["code"] == catalog_item["code"])
        assert item["is_system"] is True
        assert item["is_active"] is True
        assert item["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert len(item["category"]) > 0
        assert len(item["resource"]) > 0
        assert len(item["action"]) > 0


def test_permission_filtering_by_category(client: TestClient):
    response = client.get("/api/logistics/permissions?category=ORGANIZATION")
    assert response.status_code == 200
    org_perms = response.json()
    assert len(org_perms) >= 4
    for p in org_perms:
        assert p["category"] == "ORGANIZATION"


def test_canonical_role_baselines_integrity(client: TestClient):
    roles_res = client.get("/api/logistics/roles")
    assert roles_res.status_code == 200
    roles = roles_res.json()
    sys_roles = {r["code"]: r for r in roles if r["is_system"]}

    for role_code, expected_baseline in CANONICAL_ROLE_BASELINES.items():
        assert role_code in sys_roles
        role_id = sys_roles[role_code]["id"]
        perm_res = client.get(f"/api/logistics/roles/{role_id}/permissions")
        assert perm_res.status_code == 200
        data = perm_res.json()
        effective_codes = set(data["effective_codes"])
        for exp_code in expected_baseline:
            assert exp_code in effective_codes, f"Role {role_code} missing {exp_code}"


def test_auditor_profile_least_privilege_and_no_mutations(client: TestClient):
    roles_res = client.get("/api/logistics/roles")
    roles = roles_res.json()
    auditor_role = next(r for r in roles if r["code"] == "AUDITOR")

    perm_res = client.get(f"/api/logistics/roles/{auditor_role['id']}/permissions")
    assert perm_res.status_code == 200
    auditor_perms = perm_res.json()["permissions"]

    dangerous_actions = {"create", "update", "delete", "adjust", "release", "assign", "void"}
    for p in auditor_perms:
        assert p["action"] not in dangerous_actions, f"Auditor has dangerous mutation: {p['code']}"

    assign_res = client.put(
        f"/api/logistics/roles/{auditor_role['id']}/permissions",
        json={"permission_codes": ["inventory.adjust", "audit.read"]},
        headers=csrf_headers(),
    )
    assert assign_res.status_code == 409
    assert assign_res.json()["code"] == "AUDITOR_MUTATION_FORBIDDEN"


def test_custom_role_permission_assignment_and_replacement(client: TestClient):
    code = f"CUSTOM-RBAC-{uuid.uuid4().hex[:6]}"
    create_res = client.post(
        "/api/logistics/roles",
        json={
            "code": code,
            "name": "Custom RBAC Operator",
            "description": "Role for testing RBAC assignment",
            "is_system": False,
            "is_test_data": True,
        },
        headers=csrf_headers(),
    )
    assert create_res.status_code == 201
    custom_role_id = create_res.json()["id"]

    initial_perms = ["organization.read", "warehouse.read", "warehouse.update"]
    assign_res = client.put(
        f"/api/logistics/roles/{custom_role_id}/permissions",
        json={"permission_codes": initial_perms},
        headers=csrf_headers(),
    )
    assert assign_res.status_code == 200
    res_data = assign_res.json()
    assert set(res_data["effective_codes"]) == set(initial_perms)

    updated_perms = ["organization.read", "branch.read"]
    replace_res = client.put(
        f"/api/logistics/roles/{custom_role_id}/permissions",
        json={"permission_codes": updated_perms},
        headers=csrf_headers(),
    )
    assert replace_res.status_code == 200
    assert set(replace_res.json()["effective_codes"]) == set(updated_perms)

    bad_res = client.put(
        f"/api/logistics/roles/{custom_role_id}/permissions",
        json={"permission_codes": ["non_existent.action"]},
        headers=csrf_headers(),
    )
    assert bad_res.status_code == 422
    assert bad_res.json()["code"] == "PERMISSION_NOT_FOUND"

    client.delete(
        f"/api/logistics/roles/{custom_role_id}",
        headers=csrf_headers(),
    )


def test_rbac_default_deny_engine():
    ctx_inactive = AuthorizationContext(
        role_codes=["WAREHOUSE"],
        permissions={"warehouse.read", "warehouse.putaway"},
        is_active=False,
    )
    assert ctx_inactive.has_permission("warehouse.read") is False
    with pytest.raises(Exception, match="missing required permission"):
        ctx_inactive.require_permission("warehouse.read")

    ctx_active = AuthorizationContext(
        role_codes=["WAREHOUSE"],
        permissions={"warehouse.read", "warehouse.putaway"},
        is_active=True,
    )
    assert ctx_active.has_permission("warehouse.read") is True
    assert ctx_active.has_permission("warehouse.putaway") is True

    assert ctx_active.has_permission("inventory.adjust") is False
    with pytest.raises(Exception, match="missing required permission"):
        ctx_active.require_permission("inventory.adjust")


def test_endpoint_permission_matrix_endpoint(client: TestClient):
    response = client.get("/api/logistics/permissions/endpoint-matrix")
    assert response.status_code == 200
    matrix = response.json()
    assert len(matrix) == len(ENDPOINT_PERMISSION_MATRIX)


def test_production_seed_protection(monkeypatch):
    monkeypatch.setattr(seed_demo.settings, "APP_ENV", "production")
    with pytest.raises(RuntimeError, match="CRITICAL ERROR"):
        seed_demo.run_seed()
