import csv
import io
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.connection import SessionLocal
from app.main import app
from app.modules.auth.csrf import generate_csrf_token
from app.scripts import seed_demo
from app.shared.audit.contracts import AuditContext
from app.shared.audit.sanitizer import sanitize_sensitive_data
from app.shared.audit.service import AuditService


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


def test_audit_event_creation_and_timezone_aware():
    db = SessionLocal()
    service = AuditService()
    corr_id = uuid.uuid4()
    context = AuditContext(
        correlation_id=corr_id,
        actor_type="SYSTEM",
        ip_address="127.0.0.1",
        user_agent="pytest-client",
        is_test_data=True,
    )
    try:
        event = service.record_event(
            db=db,
            context=context,
            resource_type="warehouse",
            action="warehouse.create",
            result="SUCCESS",
            before_data=None,
            after_data={"name": "Test Warehouse", "code": "WH-TEST-01"},
            metadata={"source": "test_runner"},
        )
        db.commit()

        assert event.id is not None
        assert event.occurred_at.tzinfo is not None
        assert event.actor_type == "SYSTEM"
        assert event.result == "SUCCESS"
        assert event.correlation_id == corr_id
        assert event.is_test_data is True
    finally:
        db.close()


def test_correlation_id_propagation(client: TestClient):
    test_corr_id = str(uuid.uuid4())
    res = client.get("/api/system/info", headers={"X-Correlation-ID": test_corr_id})
    assert res.status_code == 200
    assert res.headers.get("X-Correlation-ID") == test_corr_id

    res_no_header = client.get("/api/system/info")
    assert res_no_header.status_code == 200
    auto_id = res_no_header.headers.get("X-Correlation-ID")
    assert auto_id is not None
    assert uuid.UUID(auto_id)


def test_audit_secret_redaction():
    payload = {
        "user": "admin",
        "password": "ClearTextPassword123!",
        "api_key": "sk_test_123456789",
        "nested": {
            "token": "bearer-xyz",
            "service_role": "secret_role_key",
            "database_url": "postgresql://user:pass@host:5432/db",
            "safe_metric": 42,
        },
    }
    sanitized = sanitize_sensitive_data(payload)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["service_role"] == "[REDACTED]"
    assert sanitized["nested"]["database_url"] == "[REDACTED]"
    assert sanitized["nested"]["safe_metric"] == 42


def test_database_audit_immutability():
    db = SessionLocal()
    service = AuditService()
    try:
        context = AuditContext(actor_type="SYSTEM", is_test_data=True)
        event = service.record_event(
            db=db,
            context=context,
            resource_type="organization",
            action="organization.create",
            result="SUCCESS",
        )
        db.commit()

        # Direct UPDATE attempt must fail via Postgres trigger
        with pytest.raises(Exception, match="audit_events is append-only"):
            from sqlalchemy import text

            db.execute(
                text("UPDATE audit_events SET reason = 'tampered' WHERE id = :id"),
                {"id": event.id},
            )
            db.commit()
        db.rollback()

        # Direct DELETE attempt must fail via Postgres trigger
        with pytest.raises(Exception, match="audit_events is append-only"):
            from sqlalchemy import text

            db.execute(
                text("DELETE FROM audit_events WHERE id = :id"),
                {"id": event.id},
            )
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_f004_warehouse_lifecycle_audited(client: TestClient):
    struct_res = client.get("/api/logistics/structure")
    assert struct_res.status_code == 200
    orgs = struct_res.json()["organizations"]
    demo_org = next(o for o in orgs if o["code"] == "DEMO-ORG-001")
    branch = demo_org["branches"][0]
    branch_id = branch["id"]

    correlation_id = str(uuid.uuid4())
    wh_code = f"TEST-WH-{uuid.uuid4().hex[:6]}"

    # Create Warehouse
    headers = csrf_headers()
    headers["X-Correlation-ID"] = correlation_id
    create_res = client.post(
        f"/api/logistics/branches/{branch_id}/warehouses",
        json={
            "code": wh_code,
            "name": "Audit Test Warehouse",
            "use_branch_location": True,
            "is_test_data": True,
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    wh_id = create_res.json()["id"]

    audit_create_res = client.get(
        f"/api/logistics/audit-events?correlation_id={correlation_id}&action=warehouse.create"
    )
    assert audit_create_res.status_code == 200
    items = audit_create_res.json()["items"]
    assert len(items) == 1
    assert items[0]["resource_id"] == wh_id
    assert items[0]["result"] == "SUCCESS"
    assert items[0]["actor_type"] == "AUTHENTICATED"

    # Update Warehouse
    update_res = client.patch(
        f"/api/logistics/warehouses/{wh_id}",
        json={"name": "Updated Audit Test Warehouse"},
        headers=headers,
    )
    assert update_res.status_code == 200

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

    # Delete Warehouse
    del_res = client.delete(
        f"/api/logistics/warehouses/{wh_id}",
        headers=headers,
    )
    assert del_res.status_code == 204


def test_f006_permission_assignment_audited(client: TestClient):
    roles_res = client.get("/api/logistics/roles")
    roles = roles_res.json()
    demo_role = next(r for r in roles if r["code"] == "DEMO-ROLE-QC")
    role_id = demo_role["id"]

    correlation_id = str(uuid.uuid4())
    headers = csrf_headers()
    headers["X-Correlation-ID"] = correlation_id
    assign_res = client.put(
        f"/api/logistics/roles/{role_id}/permissions",
        json={"permission_codes": ["organization.read", "warehouse.read"]},
        headers=headers,
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
    roles_res = client.get("/api/logistics/roles")
    roles = roles_res.json()
    auditor_role = next(r for r in roles if r["code"] == "AUDITOR")
    auditor_id = auditor_role["id"]

    correlation_id = str(uuid.uuid4())
    headers = csrf_headers()
    headers["X-Correlation-ID"] = correlation_id
    bad_res = client.put(
        f"/api/logistics/roles/{auditor_id}/permissions",
        json={"permission_codes": ["inventory.adjust", "audit.read"]},
        headers=headers,
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
    assert "text/csv" in res.headers["content-type"]
    assert "attachment; filename=" in res.headers["content-disposition"]

    content = res.text
    reader = csv.reader(io.StringIO(content))
    header = next(reader)
    assert "id" in header
    assert "occurred_at" in header
    assert "actor_type" in header
    assert "action" in header
    assert "result" in header
