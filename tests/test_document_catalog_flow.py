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
    confirm_code = totp.at(int(time.time()) - 30)
    confirm_res = c.post(
        "/api/auth/mfa/totp/confirm",
        json={"enrollment_id": enrollment_id, "code": confirm_code},
        headers=csrf_headers(),
    )
    assert confirm_res.status_code == 200
    return manual_key, confirm_res.json()["recovery_codes"]


def test_document_families_canonical_completeness(client: TestClient):
    """Verify that all 9 canonical families exist and are active."""
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    res = client.get("/api/logistics/document-families")
    assert res.status_code == 200
    families = res.json()
    assert len(families) >= 9
    codes = {f["code"] for f in families}
    expected = {
        "PURCHASING",
        "RECEIVING",
        "INVENTORY",
        "OUTBOUND",
        "TRANSPORT",
        "DELIVERY",
        "QUALITY",
        "RETURN",
        "SYSTEM",
    }
    assert expected.issubset(codes)


def test_document_retention_policies_completeness(client: TestClient):
    """Verify that all 5 canonical retention policies exist."""
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    res = client.get("/api/logistics/document-retention-policies")
    assert res.status_code == 200
    policies = res.json()
    assert len(policies) >= 5
    codes = {p["code"] for p in policies}
    expected = {
        "OPERATIONAL_STANDARD",
        "AUDIT_RELEVANT",
        "LEGAL_LONG_TERM",
        "PERMANENT",
        "UNDEFINED_PENDING_POLICY",
    }
    assert expected.issubset(codes)


def test_document_types_internal_and_external_scopes(client: TestClient):
    """Verify INTERNAL and EXTERNAL document scopes and rules."""
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    res = client.get("/api/logistics/document-types")
    assert res.status_code == 200
    types = res.json()
    assert len(types) >= 30

    po = next((t for t in types if t["code"] == "PO"), None)
    assert po is not None
    assert po["document_scope"] == "INTERNAL"

    psc = next((t for t in types if t["code"] == "PSC"), None)
    assert psc is not None
    assert psc["document_scope"] == "EXTERNAL"


def test_document_type_version_creation_and_immutability(client: TestClient):
    """Verify version increment, historical immutability, and single current version."""
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")
    manual_key, _ = enroll_and_activate_mfa(client)

    # 1. Get PO document type
    types_res = client.get("/api/logistics/document-types")
    po_item = next(t for t in types_res.json() if t["code"] == "PO")
    po_id = po_item["id"]

    # 2. Detail of PO
    detail_res = client.get(f"/api/logistics/document-types/{po_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    initial_version = detail_data["current_version_number"] or 1
    retention_id = detail_data["current_version"]["retention_policy_id"]

    # 3. Post new version without Step-Up -> triggers 428
    payload = {
        "schema_definition": [
            {"key": "supplier_id", "label": "Proveedor", "type": "uuid", "required": True},
            {"key": "total_amount", "label": "Monto Total", "type": "decimal", "required": True},
            {
                "key": "approved_by_board",
                "label": "Aprobado por Directorio",
                "type": "boolean",
                "required": True,
            },
        ],
        "emission_rules": {
            "requires_organization": True,
            "requires_branch": True,
            "requires_warehouse": True,
            "requires_approval": True,
            "requires_step_up": True,
            "future_numbering_policy": "SYSTEM_INTERNAL",
        },
        "status_definition": ["DRAFT", "PENDING", "APPROVED", "ISSUED", "COMPLETED", "VOID"],
        "template_key": f"purchase_order_v{initial_version + 1}",
        "retention_policy_id": retention_id,
        "read_permission": "documents.read",
        "emit_permission": "documents.emit",
        "download_permission": "documents.download",
        "reprint_permission": "documents.reprint",
        "void_permission": "documents.void",
    }

    res_428 = client.post(
        f"/api/logistics/document-types/{po_id}/versions",
        json=payload,
        headers=csrf_headers(),
    )
    assert res_428.status_code == 428
    challenge_id = res_428.json()["details"]["challenge_id"]

    # 4. Verify Step-Up challenge to obtain Grant
    totp = pyotp.TOTP(manual_key)
    verify_res = client.post(
        "/api/auth/step-up/verify",
        json={"challenge_id": challenge_id, "code": totp.now(), "method": "TOTP"},
        headers=csrf_headers(),
    )
    assert verify_res.status_code == 200
    grant_id = verify_res.json()["grant_id"]

    headers_stepup = csrf_headers()
    headers_stepup["X-Step-Up-Grant"] = grant_id

    # 5. Retry post new version with Grant -> 201 Created
    res_next = client.post(
        f"/api/logistics/document-types/{po_id}/versions",
        json=payload,
        headers=headers_stepup,
    )
    assert res_next.status_code == 201
    next_data = res_next.json()
    assert next_data["version_number"] == initial_version + 1
    assert next_data["is_current"] is True

    # 6. Check version history
    versions_res = client.get(f"/api/logistics/document-types/{po_id}/versions")
    assert versions_res.status_code == 200
    versions = versions_res.json()
    assert len(versions) >= 2
    assert versions[0]["version_number"] == initial_version + 1
    assert versions[0]["is_current"] is True
    assert versions[1]["version_number"] == initial_version
    assert versions[1]["is_current"] is False
    assert versions[1]["effective_to"] is not None

    # 7. Verify single current version
    current_versions = [v for v in versions if v["is_current"]]
    assert len(current_versions) == 1


def test_invalid_field_type_rejected(client: TestClient):
    """Verify that invalid field types in schema definition are strictly rejected."""
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")
    manual_key, _ = enroll_and_activate_mfa(client)

    types_res = client.get("/api/logistics/document-types")
    po_item = next(t for t in types_res.json() if t["code"] == "REQ")
    po_id = po_item["id"]

    retentions = client.get("/api/logistics/document-retention-policies").json()
    retention_id = retentions[0]["id"]

    payload = {
        "schema_definition": [
            {
                "key": "bad_field",
                "label": "Campo Invalido",
                "type": "executable_code_or_dsl",
                "required": True,
            },
        ],
        "retention_policy_id": retention_id,
    }

    # 1. Trigger 428 challenge
    res_428 = client.post(
        f"/api/logistics/document-types/{po_id}/versions",
        json={"retention_policy_id": retention_id},
        headers=csrf_headers(),
    )
    assert res_428.status_code == 428
    challenge_id = res_428.json()["details"]["challenge_id"]

    # 2. Verify challenge
    totp = pyotp.TOTP(manual_key)
    verify_res = client.post(
        "/api/auth/step-up/verify",
        json={"challenge_id": challenge_id, "code": totp.now(), "method": "TOTP"},
        headers=csrf_headers(),
    )
    assert verify_res.status_code == 200
    grant_id = verify_res.json()["grant_id"]

    headers_stepup = csrf_headers()
    headers_stepup["X-Step-Up-Grant"] = grant_id

    # 3. Submit invalid field type
    res = client.post(
        f"/api/logistics/document-types/{po_id}/versions",
        json=payload,
        headers=headers_stepup,
    )
    assert res.status_code == 422  # Pydantic validation error


def test_step_up_required_on_catalog_manage(client: TestClient):
    """Verify that document catalog mutation endpoints enforce HTTP 428 Step-Up challenge."""
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")
    enroll_and_activate_mfa(client)

    types_res = client.get("/api/logistics/document-types")
    po_item = next(t for t in types_res.json() if t["code"] == "PO")
    po_id = po_item["id"]

    retentions = client.get("/api/logistics/document-retention-policies").json()
    retention_id = retentions[0]["id"]

    payload = {
        "schema_definition": [],
        "retention_policy_id": retention_id,
    }

    # No X-Step-Up-Grant header provided -> Must return HTTP 428
    res = client.post(
        f"/api/logistics/document-types/{po_id}/versions",
        json=payload,
        headers=csrf_headers(),
    )
    assert res.status_code == 428
    err = res.json()
    assert err["code"] == "STEP_UP_REQUIRED" or "MFA" in err.get("code", "")


def test_auditor_read_only_access(client: TestClient):
    """Verify that AUDITOR role has read access but is blocked from mutating the catalog."""
    seed_demo.run_seed()
    login_client(client, "auditor.demo@logistica.local")

    # 1. Read catalog -> 200 OK
    res = client.get("/api/logistics/document-types")
    assert res.status_code == 200
    po_item = next(t for t in res.json() if t["code"] == "PO")

    # 2. Mutate catalog -> 403 Forbidden
    retentions = client.get("/api/logistics/document-retention-policies").json()
    payload = {
        "schema_definition": [],
        "retention_policy_id": retentions[0]["id"],
    }

    res_post = client.post(
        f"/api/logistics/document-types/{po_item['id']}/versions",
        json=payload,
        headers=csrf_headers(),
    )
    assert res_post.status_code == 403


def test_version_delete_api_absent(client: TestClient):
    """Verify that there is no destructive DELETE endpoint for document type versions."""
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    dummy_uuid = str(uuid.uuid4())
    res = client.delete(
        f"/api/logistics/document-types/{dummy_uuid}/versions/{dummy_uuid}", headers=csrf_headers()
    )
    assert res.status_code in [404, 405]

    res2 = client.delete(f"/api/logistics/document-types/{dummy_uuid}", headers=csrf_headers())
    assert res2.status_code in [404, 405]
