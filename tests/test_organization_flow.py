import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scripts import seed_demo


@pytest.fixture
def client():
    return TestClient(app)


def test_structure_endpoint(client: TestClient):
    seed_demo.run_seed()
    response = client.get("/api/logistics/structure")
    assert response.status_code == 200
    data = response.json()
    assert "organizations" in data
    assert len(data["organizations"]) >= 1

    demo_org = next((o for o in data["organizations"] if o["code"] == "DEMO-ORG-001"), None)
    assert demo_org is not None
    assert demo_org["name"] == "Organización Logística Demo"
    assert demo_org["is_test_data"] is True
    assert len(demo_org["branches"]) >= 2


def test_organization_crud_lifecycle(client: TestClient):
    unique_code = f"TEST-ORG-{uuid.uuid4().hex[:6]}"
    create_res = client.post(
        "/api/logistics/organizations",
        json={"code": unique_code, "name": "Test Lifecycle Org", "is_active": True},
    )
    assert create_res.status_code == 201
    org_data = create_res.json()
    org_id = org_data["id"]

    # Duplicate code rejection (409)
    dup_res = client.post(
        "/api/logistics/organizations",
        json={"code": unique_code, "name": "Duplicate Code Org"},
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["code"] == "DUPLICATE_ORGANIZATION_CODE"

    # Get Organization
    get_res = client.get(f"/api/logistics/organizations/{org_id}")
    assert get_res.status_code == 200
    assert get_res.json()["code"] == unique_code

    # Update Organization
    patch_res = client.patch(
        f"/api/logistics/organizations/{org_id}",
        json={"name": "Updated Org Name"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Updated Org Name"

    # Delete Organization
    del_res = client.delete(f"/api/logistics/organizations/{org_id}")
    assert del_res.status_code == 204

    # Confirm Not Found (404)
    confirm_res = client.get(f"/api/logistics/organizations/{org_id}")
    assert confirm_res.status_code == 404
    assert confirm_res.json()["code"] == "ORGANIZATION_NOT_FOUND"


def test_branch_and_warehouse_dependency_gates(client: TestClient):
    org_code = f"DEP-ORG-{uuid.uuid4().hex[:6]}"
    org_res = client.post(
        "/api/logistics/organizations",
        json={"code": org_code, "name": "Dependency Gate Org"},
    )
    org_id = org_res.json()["id"]

    # Create Branch
    branch_res = client.post(
        f"/api/logistics/organizations/{org_id}/branches",
        json={
            "code": "DEP-BR-01",
            "name": "Dependency Branch",
            "location": {
                "label": "Dep Loc",
                "address_line1": "Av. Central 123",
                "country_code": "PE",
            },
        },
    )
    assert branch_res.status_code == 201
    branch_id = branch_res.json()["id"]

    # Try to delete Org while it has Branch -> blocked with 409
    org_del_res = client.delete(f"/api/logistics/organizations/{org_id}")
    assert org_del_res.status_code == 409
    assert org_del_res.json()["code"] == "ORGANIZATION_HAS_BRANCHES"

    # Create Warehouse
    wh_res = client.post(
        f"/api/logistics/branches/{branch_id}/warehouses",
        json={
            "code": "DEP-WH-01",
            "name": "Dependency Warehouse",
            "use_branch_location": True,
        },
    )
    assert wh_res.status_code == 201
    wh_id = wh_res.json()["id"]

    # Try to delete Branch while it has Warehouse -> blocked with 409
    br_del_res = client.delete(f"/api/logistics/branches/{branch_id}")
    assert br_del_res.status_code == 409
    assert br_del_res.json()["code"] == "BRANCH_HAS_WAREHOUSES"

    # Clean up warehouse first
    del_wh = client.delete(f"/api/logistics/warehouses/{wh_id}")
    assert del_wh.status_code == 204

    # Now branch can be deleted
    del_br = client.delete(f"/api/logistics/branches/{branch_id}")
    assert del_br.status_code == 204

    # Now org can be deleted
    del_org = client.delete(f"/api/logistics/organizations/{org_id}")
    assert del_org.status_code == 204


def test_coordinate_validation_bounds(client: TestClient):
    org_res = client.post(
        "/api/logistics/organizations",
        json={"code": f"GEO-ORG-{uuid.uuid4().hex[:6]}", "name": "Geo Org"},
    )
    org_id = org_res.json()["id"]

    # Invalid latitude (-95)
    bad_lat = client.post(
        f"/api/logistics/organizations/{org_id}/branches",
        json={
            "code": "GEO-BR-BADLAT",
            "name": "Bad Lat Branch",
            "location": {
                "label": "Bad Lat",
                "address_line1": "Street 1",
                "latitude": -95.0,
            },
        },
    )
    assert bad_lat.status_code == 422
    assert bad_lat.json()["code"] == "REQUEST_VALIDATION_ERROR"

    # Invalid longitude (200)
    bad_lon = client.post(
        f"/api/logistics/organizations/{org_id}/branches",
        json={
            "code": "GEO-BR-BADLON",
            "name": "Bad Lon Branch",
            "location": {
                "label": "Bad Lon",
                "address_line1": "Street 1",
                "longitude": 200.0,
            },
        },
    )
    assert bad_lon.status_code == 422
    assert bad_lon.json()["code"] == "REQUEST_VALIDATION_ERROR"

    # Clean up org
    client.delete(f"/api/logistics/organizations/{org_id}")


def test_production_seed_protection(monkeypatch):
    monkeypatch.setattr(seed_demo.settings, "APP_ENV", "production")

    with pytest.raises(RuntimeError, match="CRITICAL ERROR"):
        seed_demo.run_seed()
