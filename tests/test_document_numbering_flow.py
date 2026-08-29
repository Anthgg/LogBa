import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.connection import SessionLocal
from app.main import app
from app.modules.auth.csrf import generate_csrf_token
from app.modules.documents.numbering_standard import (
    DECISION_F012_CORRELATIVE_WIDTH,
    DOCUMENT_NUMBERING_PATTERN,
    DOCUMENT_NUMBERING_STANDARD,
    REUSE_POLICY,
    format_canonical_document_code,
)
from app.modules.organization.models import Branch, OperationalLocation, Organization
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


def test_format_canonical_document_code_direct():
    """Verify direct string formatting logic for canonical standard."""
    # 1. PO + LIM + 2026 + 1 -> PO-LIM-2026-000001
    assert format_canonical_document_code("PO", "LIM", 2026, 1) == "PO-LIM-2026-000001"

    # 2. REQ + AQP + 2026 + 42 -> REQ-AQP-2026-000042
    assert format_canonical_document_code("REQ", "AQP", 2026, 42) == "REQ-AQP-2026-000042"

    # 3. ODS + LIM + 2026 + 1527 -> ODS-LIM-2026-001527
    assert format_canonical_document_code("ODS", "LIM", 2026, 1527) == "ODS-LIM-2026-001527"

    # 4. GRN + DEMO-LIM + 2026 + 100 -> GRN-DEMO-LIM-2026-000100 (branch with hyphen)
    assert (
        format_canonical_document_code("GRN", "DEMO-LIM", 2026, 100) == "GRN-DEMO-LIM-2026-000100"
    )


def test_get_document_numbering_standard_spec(client: TestClient):
    """Verify endpoint returning canonical standard specification."""
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    res = client.get("/api/logistics/document-numbering/standard")
    assert res.status_code == 200
    data = res.json()
    assert data["standard"] == DOCUMENT_NUMBERING_STANDARD
    assert data["pattern"] == DOCUMENT_NUMBERING_PATTERN
    assert data["correlative_width"] == DECISION_F012_CORRELATIVE_WIDTH
    assert data["reuse_policy"] == REUSE_POLICY
    assert data["uniqueness_scope"] == "ORGANIZATION"
    assert data["allocation_phase"] == "FUTURE_PHASE_OWNER_F013"
    assert data["official_number_preservation"] is True
    assert len(data["segments"]) == 4


def test_preview_numbering_success_flow(client: TestClient):
    """Verify preview generation flow for internal document."""
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    # 1. Get PO document type
    types_res = client.get("/api/logistics/document-types")
    po_item = next(t for t in types_res.json() if t["code"] == "PO")
    po_id = po_item["id"]

    # 2. Get user branch
    struct_res = client.get("/api/logistics/structure")
    branch = struct_res.json()["organizations"][0]["branches"][0]
    branch_id = branch["id"]
    branch_code = branch["code"]

    # 3. Request preview for PO with sample correlative 42
    payload = {
        "document_type_id": po_id,
        "branch_id": branch_id,
        "period_year": 2026,
        "sample_correlative": 42,
    }
    preview_res = client.post(
        "/api/logistics/document-numbering/preview",
        json=payload,
        headers=csrf_headers(),
    )
    assert preview_res.status_code == 200
    p_data = preview_res.json()
    expected_code = f"PO-{branch_code}-2026-000042"
    assert p_data["preview"] == expected_code
    assert p_data["reserved"] is False
    assert p_data["allocated"] is False

    identity = p_data["structured_identity"]
    assert identity["document_type_code"] == "PO"
    assert identity["branch_code"] == branch_code
    assert identity["period_year"] == 2026
    assert identity["correlative"] == 42
    assert identity["display_code"] == expected_code


def test_preview_with_hyphenated_branch_code(client: TestClient):
    """Verify branch code containing hyphens (e.g. DEMO-LIM) formats correctly."""
    seed_demo.run_seed()
    user_info = login_client(client, "gerencia.demo@logistica.local")
    org_id = user_info["organization_id"]

    db = SessionLocal()
    try:
        loc = OperationalLocation(
            label="Hub Norte Test",
            address_line1="Av. Panamericana Norte Km 28",
            country_code="PE",
        )
        db.add(loc)
        db.flush()

        # Create a branch with hyphens in code
        hyphen_branch = Branch(
            organization_id=uuid.UUID(org_id),
            code=f"HUB-NORTH-{uuid.uuid4().hex[:4].upper()}",
            name="Hub Norte Almacenamiento",
            location_id=loc.id,
            is_active=True,
        )
        db.add(hyphen_branch)
        db.commit()
        db.refresh(hyphen_branch)
        branch_id = str(hyphen_branch.id)
        branch_code = hyphen_branch.code
    finally:
        db.close()

    # Get REQ document type
    types_res = client.get("/api/logistics/document-types")
    req_item = next(t for t in types_res.json() if t["code"] == "REQ")

    payload = {
        "document_type_id": req_item["id"],
        "branch_id": branch_id,
        "period_year": 2026,
        "sample_correlative": 1527,
    }
    preview_res = client.post(
        "/api/logistics/document-numbering/preview",
        json=payload,
        headers=csrf_headers(),
    )
    assert preview_res.status_code == 200
    p_data = preview_res.json()
    assert p_data["preview"] == f"REQ-{branch_code}-2026-001527"


def test_preview_external_document_scope_blocked(client: TestClient):
    """Verify that EXTERNAL scope documents are strictly blocked from internal numbering preview."""
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    # Get PSC (Proveedor Guia Remision - EXTERNAL scope)
    types_res = client.get("/api/logistics/document-types")
    psc_item = next(t for t in types_res.json() if t["code"] == "PSC")
    assert psc_item["document_scope"] == "EXTERNAL"

    struct_res = client.get("/api/logistics/structure")
    branch = struct_res.json()["organizations"][0]["branches"][0]

    payload = {
        "document_type_id": psc_item["id"],
        "branch_id": branch["id"],
        "period_year": 2026,
        "sample_correlative": 1,
    }
    res = client.post(
        "/api/logistics/document-numbering/preview",
        json=payload,
        headers=csrf_headers(),
    )
    assert res.status_code == 400
    err = res.json()
    assert err["code"] == "EXTERNAL_OFFICIAL_NUMBER_MUST_BE_PRESERVED"


def test_preview_branch_organization_mismatch_blocked(client: TestClient):
    """Verify that a branch belonging to another organization is rejected."""
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    db = SessionLocal()
    try:
        loc = OperationalLocation(
            label="Sede Trujillo Test",
            address_line1="Av. Larco 500",
            country_code="PE",
        )
        db.add(loc)
        db.flush()

        foreign_org = Organization(
            code=f"EXT-{uuid.uuid4().hex[:4].upper()}",
            name="Empresa Tercera S.A.C.",
            is_active=True,
        )
        db.add(foreign_org)
        db.flush()

        foreign_branch = Branch(
            organization_id=foreign_org.id,
            code="TRJ",
            name="Sede Trujillo Terceros",
            location_id=loc.id,
            is_active=True,
        )
        db.add(foreign_branch)
        db.commit()
        db.refresh(foreign_branch)
        foreign_branch_id = str(foreign_branch.id)
    finally:
        db.close()

    types_res = client.get("/api/logistics/document-types")
    po_item = next(t for t in types_res.json() if t["code"] == "PO")

    payload = {
        "document_type_id": po_item["id"],
        "branch_id": foreign_branch_id,
        "period_year": 2026,
        "sample_correlative": 1,
    }
    res = client.post(
        "/api/logistics/document-numbering/preview",
        json=payload,
        headers=csrf_headers(),
    )
    assert res.status_code == 400
    err = res.json()
    assert err["code"] == "BRANCH_ORGANIZATION_MISMATCH"


def test_preview_validation_errors(client: TestClient):
    """Verify controlled validation errors for invalid year, correlative, or missing IDs."""
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    types_res = client.get("/api/logistics/document-types")
    po_item = next(t for t in types_res.json() if t["code"] == "PO")
    struct_res = client.get("/api/logistics/structure")
    branch = struct_res.json()["organizations"][0]["branches"][0]

    # 1. Invalid Year < 2000
    res_bad_year = client.post(
        "/api/logistics/document-numbering/preview",
        json={
            "document_type_id": po_item["id"],
            "branch_id": branch["id"],
            "period_year": 1999,
            "sample_correlative": 1,
        },
        headers=csrf_headers(),
    )
    assert res_bad_year.status_code == 400
    assert res_bad_year.json()["code"] == "INVALID_DOCUMENT_PERIOD_YEAR"

    # 2. Invalid Correlative <= 0
    res_bad_seq = client.post(
        "/api/logistics/document-numbering/preview",
        json={
            "document_type_id": po_item["id"],
            "branch_id": branch["id"],
            "period_year": 2026,
            "sample_correlative": 0,
        },
        headers=csrf_headers(),
    )
    assert res_bad_seq.status_code == 422  # Pydantic ge=1 validation

    # 3. Non-existent document type
    res_not_found = client.post(
        "/api/logistics/document-numbering/preview",
        json={
            "document_type_id": str(uuid.uuid4()),
            "branch_id": branch["id"],
            "period_year": 2026,
            "sample_correlative": 1,
        },
        headers=csrf_headers(),
    )
    assert res_not_found.status_code == 404
    assert res_not_found.json()["code"] == "DOCUMENT_TYPE_NOT_FOUND"


def test_number_allocation_endpoints_absent(client: TestClient):
    """Verify that allocation/reservation endpoints do not exist in F012.

    (FUTURE_PHASE_OWNER_F013).
    """
    seed_demo.run_seed()
    login_client(client, "gerencia.demo@logistica.local")

    res1 = client.post("/api/logistics/allocate-number", json={}, headers=csrf_headers())
    assert res1.status_code in [404, 405]

    res2 = client.post("/api/logistics/reserve-number", json={}, headers=csrf_headers())
    assert res2.status_code in [404, 405]

    res3 = client.get("/api/logistics/next-number", headers=csrf_headers())
    assert res3.status_code in [404, 405]
