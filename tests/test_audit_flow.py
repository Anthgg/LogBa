import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.connection import SessionLocal
from app.main import app
from app.scripts import seed_demo
from app.shared.audit.contracts import AuditContext
from app.shared.audit.sanitizer import sanitize_sensitive_data
from app.shared.audit.service import AuditService


@pytest.fixture
def client():
    return TestClient(app)


def test_audit_event_creation_and_timezone_aware():
    db = SessionLocal()
    service = AuditService()
    ctx = AuditContext(
        actor_type="SYSTEM",
        ip_address="127.0.0.1",
        user_agent="PyTest/1.0",
        is_test_data=True,
    )
    event = service.record_event(
        db=db,
        context=ctx,
        resource_type="system",
        action="system.health_check",
        result="SUCCESS",
        before_data=None,
        after_data={"status": "ok"},
    )
    db.commit()
    db.refresh(event)

    assert event.id is not None
    assert event.occurred_at is not None
    assert event.occurred_at.tzinfo is not None
    assert event.actor_type == "SYSTEM"
    assert event.actor_id is None
    assert event.session_id is None
    assert event.result == "SUCCESS"
    assert event.after_data == {"status": "ok"}
    db.close()


def test_correlation_id_propagation(client: TestClient):
    custom_correlation = str(uuid.uuid4())
    res = client.get(
        "/api/logistics/structure",
        headers={"X-Correlation-ID": custom_correlation},
    )
    assert res.status_code == 200
    assert res.headers.get("X-Correlation-ID") == custom_correlation


def test_audit_secret_redaction():
    raw_payload = {
        "user_email": "operator@logba.pe",
        "password": "SuperSecretPassword123!",
        "api_key": "sk_live_9988776655",
        "nested": {
            "token": "bearer_jwt_token",
            "safe_field": "safe_value",
        },
        "list_items": [
            {"csrf_token": "csrf_12345", "name": "Item A"},
        ],
    }
    sanitized = sanitize_sensitive_data(raw_payload)

    assert sanitized["user_email"] == "operator@logba.pe"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["safe_field"] == "safe_value"
    assert sanitized["list_items"][0]["csrf_token"] == "[REDACTED]"
    assert sanitized["list_items"][0]["name"] == "Item A"


def test_database_audit_immutability():
    db = SessionLocal()
    service = AuditService()
    ctx = AuditContext(actor_type="SYSTEM", is_test_data=True)
    event = service.record_event(
        db=db,
        context=ctx,
        resource_type="warehouse",
        action="warehouse.test_immutable",
        result="SUCCESS",
    )
    db.commit()
    event_id = event.id

    # 1. Attempt UPDATE via raw SQL -> Must be blocked by PostgreSQL trigger
    with pytest.raises(Exception, match="audit_events is append-only"):
        db.execute(
            text("UPDATE audit_events SET reason = 'tampered' WHERE id = :event_id"),
            {"event_id": event_id},
        )
        db.commit()
    db.rollback()

    # 2. Attempt DELETE via raw SQL -> Must be blocked by PostgreSQL trigger
    with pytest.raises(Exception, match="audit_events is append-only"):
        db.execute(
            text("DELETE FROM audit_events WHERE id = :event_id"),
            {"event_id": event_id},
        )
        db.commit()
    db.rollback()
    db.close()


def test_f004_warehouse_lifecycle_audited(client: TestClient):
    seed_demo.run_seed()
    # 1. Get demo organization and branch
    struct_res = client.get("/api/logistics/structure")
    assert struct_res.status_code == 200
    orgs = struct_res.json()["organizations"]
    demo_org = next(o for o in orgs if o["code"] == "DEMO-ORG-001")
    branch = demo_org["branches"][0]
    branch_id = branch["id"]

    correlation_id = str(uuid.uuid4())
    wh_code = f"TEST-WH-{uuid.uuid4().hex[:6]}"

    # 2. Create Warehouse
    create_res = client.post(
        f"/api/logistics/branches/{branch_id}/warehouses",
        json={
            "code": wh_code,
            "name": "Audit Test Warehouse",
            "use_branch_location": True,
            "is_test_data": True,
        },
        headers={"X-Correlation-ID": correlation_id},
    )
    assert create_res.status_code == 201
    wh_id = create_res.json()["id"]

    # Verify audit event for create
    audit_create_res = client.get(
        f"/api/logistics/audit-events?correlation_id={correlation_id}&action=warehouse.create"
    )
    assert audit_create_res.status_code == 200
    items = audit_create_res.json()["items"]
    assert len(items) == 1
    assert items[0]["resource_id"] == wh_id
    assert items[0]["result"] == "SUCCESS"
    assert items[0]["actor_type"] == "UNAUTHENTICATED"

    # 3. Update Warehouse
    update_res = client.patch(
        f"/api/logistics/warehouses/{wh_id}",
        json={"name": "Updated Audit Test Warehouse"},
        headers={"X-Correlation-ID": correlation_id},
    )
    assert update_res.status_code == 200

    # Verify audit event for update
    query_url = (
        f"/api/logistics/audit-events?correlation_id={correlation_id}&action=warehouse.update"
    )
    detail_res = client.get(query_url)
    assert detail_res.status_code == 200
    update_event = detail_res.json()["items"][0]

    event_detail_res = client.get(f"/api/logistics/audit-events/{update_event['id']}")
    assert event_detail_res.status_code == 200
    detail_data = event_detail_res.json()
    assert detail_data["before_data"]["name"] == "Audit Test Warehouse"
    assert detail_data["after_data"]["name"] == "Updated Audit Test Warehouse"

    # 4. Delete Warehouse
    del_res = client.delete(
        f"/api/logistics/warehouses/{wh_id}",
        headers={"X-Correlation-ID": correlation_id},
    )
    assert del_res.status_code == 204

    # Verify audit event for delete
    del_url = f"/api/logistics/audit-events?correlation_id={correlation_id}&action=warehouse.delete"
    del_audit_res = client.get(del_url)
    assert del_audit_res.status_code == 200
    assert len(del_audit_res.json()["items"]) == 1


def test_f006_permission_assignment_audited(client: TestClient):
    seed_demo.run_seed()
    roles_res = client.get("/api/logistics/roles")
    roles = roles_res.json()
    demo_role = next(r for r in roles if r["code"] == "DEMO-ROLE-QC")
    role_id = demo_role["id"]

    correlation_id = str(uuid.uuid4())
    assign_res = client.put(
        f"/api/logistics/roles/{role_id}/permissions",
        json={"permission_codes": ["organization.read", "warehouse.read"]},
        headers={"X-Correlation-ID": correlation_id},
    )
    assert assign_res.status_code == 200

    assign_query = (
        f"/api/logistics/audit-events?correlation_id={correlation_id}&action=permissions.assign"
    )
    audit_res = client.get(assign_query)
    assert audit_res.status_code == 200
    items = audit_res.json()["items"]
    assert len(items) == 1
    assert items[0]["result"] == "SUCCESS"


def test_auditor_mutation_denied_audited(client: TestClient):
    seed_demo.run_seed()
    roles_res = client.get("/api/logistics/roles")
    roles = roles_res.json()
    auditor_role = next(r for r in roles if r["code"] == "AUDITOR")
    auditor_id = auditor_role["id"]

    correlation_id = str(uuid.uuid4())
    bad_res = client.put(
        f"/api/logistics/roles/{auditor_id}/permissions",
        json={"permission_codes": ["inventory.adjust", "audit.read"]},
        headers={"X-Correlation-ID": correlation_id},
    )
    assert bad_res.status_code == 409

    assign_query = (
        f"/api/logistics/audit-events?correlation_id={correlation_id}&action=permissions.assign"
    )
    audit_res = client.get(assign_query)
    assert audit_res.status_code == 200
    items = audit_res.json()["items"]
    assert len(items) == 1
    assert items[0]["result"] == "DENIED"
    assert items[0]["reason"] == "AUDITOR_MUTATION_FORBIDDEN"


def test_audit_export_csv_endpoint(client: TestClient):
    res = client.get("/api/logistics/audit-events/export")
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
    assert "attachment; filename=" in res.headers.get("content-disposition", "")
    csv_content = res.text
    assert "id,occurred_at,actor_type,actor_id" in csv_content
    assert len(csv_content.splitlines()) >= 2
