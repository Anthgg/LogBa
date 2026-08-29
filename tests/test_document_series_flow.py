import concurrent.futures
import csv
import io
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.connection import SessionLocal
from app.main import app
from app.modules.auth.csrf import generate_csrf_token
from app.modules.documents.series_models import DocumentSeries
from app.modules.documents.series_schemas import DocumentSeriesReservationCreate
from app.modules.documents.series_service import DocumentSeriesService
from app.scripts import seed_demo
from app.shared.audit.contracts import AuditContext
from tests.conftest import enable_step_up_for_client

settings = get_settings()


@pytest.fixture
def client():
    c = TestClient(app)
    seed_demo.run_seed()
    csrf = generate_csrf_token()
    login_res = c.post(
        "/api/auth/login",
        json={
            "email": "gerencia.demo@logistica.local",
            "password": settings.DEMO_USER_PASSWORD,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert login_res.status_code == 200
    enable_step_up_for_client(c)
    return c


def csrf_headers():
    return {"X-CSRF-Token": generate_csrf_token()}


def test_create_and_list_document_series(client: TestClient):
    """Verify digital series creation and listing with realtime counters."""
    # 1. Get PO document type and branch
    types_res = client.get("/api/logistics/document-types")
    po_item = next(t for t in types_res.json() if t["code"] == "PO")

    struct_res = client.get("/api/logistics/structure")
    branch = struct_res.json()["organizations"][0]["branches"][0]

    # 2. Create Series for PO, branch, year 2026
    payload = {
        "document_type_id": po_item["id"],
        "branch_id": branch["id"],
        "period_year": 2026,
    }
    create_res = client.post(
        "/api/logistics/document-series",
        json=payload,
        headers=csrf_headers(),
    )
    assert create_res.status_code == 201
    s_data = create_res.json()
    assert s_data["document_type_code"] == "PO"
    assert s_data["branch_code"] == branch["code"]
    assert s_data["period_year"] == 2026
    assert s_data["next_correlative"] == 1
    assert s_data["correlative_width"] == 6
    assert s_data["is_active"] is True
    assert s_data["reserved_count"] == 0
    assert s_data["voided_count"] == 0

    # 3. List Series
    list_res = client.get("/api/logistics/document-series")
    assert list_res.status_code == 200
    series_list = list_res.json()
    assert len(series_list) >= 1
    found = next((s for s in series_list if s["id"] == s_data["id"]), None)
    assert found is not None


def test_duplicate_series_creation_conflict(client: TestClient):
    """Verify that attempting to create a series for the same scope raises 409 DUPLICATE_SERIES."""
    types_res = client.get("/api/logistics/document-types")
    req_item = next(t for t in types_res.json() if t["code"] == "REQ")
    struct_res = client.get("/api/logistics/structure")
    branch = struct_res.json()["organizations"][0]["branches"][0]

    payload = {
        "document_type_id": req_item["id"],
        "branch_id": branch["id"],
        "period_year": 2026,
    }
    res1 = client.post(
        "/api/logistics/document-series",
        json=payload,
        headers=csrf_headers(),
    )
    assert res1.status_code == 201

    # Try second creation for identical scope
    res2 = client.post(
        "/api/logistics/document-series",
        json=payload,
        headers=csrf_headers(),
    )
    assert res2.status_code == 409
    assert res2.json()["code"] == "DUPLICATE_SERIES"


def test_create_series_external_type_blocked(client: TestClient):
    """Verify that EXTERNAL document types cannot have digital series created."""
    types_res = client.get("/api/logistics/document-types")
    psc_item = next(t for t in types_res.json() if t["code"] == "PSC")
    assert psc_item["document_scope"] == "EXTERNAL"

    struct_res = client.get("/api/logistics/structure")
    branch = struct_res.json()["organizations"][0]["branches"][0]

    res = client.post(
        "/api/logistics/document-series",
        json={
            "document_type_id": psc_item["id"],
            "branch_id": branch["id"],
            "period_year": 2026,
        },
        headers=csrf_headers(),
    )
    assert res.status_code == 400
    assert res.json()["code"] == "EXTERNAL_DOCUMENT_SERIES_FORBIDDEN"


def test_reserve_correlatives_and_numbers_lifecycle(client: TestClient):
    """Verify range reservation (1..10), individual numbers generation, and counters."""
    types_res = client.get("/api/logistics/document-types")
    grn_item = next(t for t in types_res.json() if t["code"] == "GRN")
    struct_res = client.get("/api/logistics/structure")
    branch = struct_res.json()["organizations"][0]["branches"][0]

    # Create series
    series_res = client.post(
        "/api/logistics/document-series",
        json={
            "document_type_id": grn_item["id"],
            "branch_id": branch["id"],
            "period_year": 2026,
        },
        headers=csrf_headers(),
    )
    series_id = series_res.json()["id"]

    # 1. Reserve 10 numbers (1..10)
    resv_res = client.post(
        f"/api/logistics/document-series/{series_id}/reservations",
        json={"quantity": 10, "reason": "Lote inicial de recepción de almacén"},
        headers=csrf_headers(),
    )
    assert resv_res.status_code == 201
    r_data = resv_res.json()
    assert r_data["start_correlative"] == 1
    assert r_data["end_correlative"] == 10
    assert r_data["quantity"] == 10
    assert r_data["first_display_code"] == f"GRN-{branch['code']}-2026-000001"
    assert r_data["last_display_code"] == f"GRN-{branch['code']}-2026-000010"

    # 2. Check series next_correlative is updated to 11
    detail_res = client.get(f"/api/logistics/document-series/{series_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["next_correlative"] == 11
    assert detail_res.json()["reserved_count"] == 10
    assert detail_res.json()["voided_count"] == 0

    # 3. Query numbers list
    numbers_res = client.get(f"/api/logistics/document-series/{series_id}/numbers")
    assert numbers_res.status_code == 200
    numbers = numbers_res.json()
    assert len(numbers) == 10
    assert numbers[0]["correlative"] == 1
    assert numbers[9]["correlative"] == 10


def test_void_number_and_strict_no_reuse(client: TestClient):
    """Verify voiding a number and ensuring next reservation does not reuse it."""
    types_res = client.get("/api/logistics/document-types")
    dsp_item = next(t for t in types_res.json() if t["code"] == "DSP")
    struct_res = client.get("/api/logistics/structure")
    branch = struct_res.json()["organizations"][0]["branches"][0]

    series_res = client.post(
        "/api/logistics/document-series",
        json={
            "document_type_id": dsp_item["id"],
            "branch_id": branch["id"],
            "period_year": 2026,
        },
        headers=csrf_headers(),
    )
    series_id = series_res.json()["id"]

    # Reserve 5 numbers (1..5)
    client.post(
        f"/api/logistics/document-series/{series_id}/reservations",
        json={"quantity": 5, "reason": "Despachos turno mañana"},
        headers=csrf_headers(),
    )

    # Get number 3
    numbers_res = client.get(f"/api/logistics/document-series/{series_id}/numbers")
    num3 = next(n for n in numbers_res.json() if n["correlative"] == 3)
    assert num3["status"] == "RESERVED"

    # Void number 3
    void_res = client.post(
        f"/api/logistics/document-series/numbers/{num3['id']}/void",
        json={"reason": "Error en datos del transportista - Anulación formal"},
        headers=csrf_headers(),
    )
    assert void_res.status_code == 200
    v_data = void_res.json()
    assert v_data["status"] == "VOIDED"
    assert v_data["void_reason"] == "Error en datos del transportista - Anulación formal"
    assert v_data["voided_at"] is not None

    # Check series counters: 4 RESERVED, 1 VOIDED, next=6
    s_detail = client.get(f"/api/logistics/document-series/{series_id}").json()
    assert s_detail["reserved_count"] == 4
    assert s_detail["voided_count"] == 1
    assert s_detail["next_correlative"] == 6

    # Reserve 2 new numbers -> should receive 6..7, NEVER 3
    new_resv = client.post(
        f"/api/logistics/document-series/{series_id}/reservations",
        json={"quantity": 2, "reason": "Despachos turno tarde"},
        headers=csrf_headers(),
    ).json()
    assert new_resv["start_correlative"] == 6
    assert new_resv["end_correlative"] == 7

    # Double void conflict test
    double_void_res = client.post(
        f"/api/logistics/document-series/numbers/{num3['id']}/void",
        json={"reason": "Intento de doble anulación"},
        headers=csrf_headers(),
    )
    assert double_void_res.status_code == 409
    assert double_void_res.json()["code"] == "DOCUMENT_NUMBER_ALREADY_VOIDED"


def test_download_booklet_csv(client: TestClient):
    """Verify backend generation of technical numbering booklet CSV without secret leaks."""
    types_res = client.get("/api/logistics/document-types")
    trf_item = next(t for t in types_res.json() if t["code"] == "TRF")
    struct_res = client.get("/api/logistics/structure")
    branch = struct_res.json()["organizations"][0]["branches"][0]

    series_res = client.post(
        "/api/logistics/document-series",
        json={
            "document_type_id": trf_item["id"],
            "branch_id": branch["id"],
            "period_year": 2026,
        },
        headers=csrf_headers(),
    )
    series_id = series_res.json()["id"]

    resv_res = client.post(
        f"/api/logistics/document-series/{series_id}/reservations",
        json={"quantity": 10, "reason": "Transferencias internas"},
        headers=csrf_headers(),
    )
    resv_id = resv_res.json()["id"]

    # Void correlative 2
    numbers = client.get(f"/api/logistics/document-series/{series_id}/numbers").json()
    num2 = next(n for n in numbers if n["correlative"] == 2)
    client.post(
        f"/api/logistics/document-series/numbers/{num2['id']}/void",
        json={"reason": "Cancelación de transferencia"},
        headers=csrf_headers(),
    )

    # Download CSV booklet
    booklet_res = client.get(
        f"/api/logistics/document-series/reservations/{resv_id}/booklet?format=csv"
    )
    assert booklet_res.status_code == 200
    assert "text/csv" in booklet_res.headers["content-type"]
    assert f"talonario_reserva_{resv_id}.csv" in booklet_res.headers["content-disposition"]

    csv_text = booklet_res.text
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) == 10
    assert rows[0]["CORRELATIVE"] == "1"
    assert rows[0]["STATUS"] == "RESERVED"
    assert rows[1]["CORRELATIVE"] == "2"
    assert rows[1]["STATUS"] == "VOIDED"
    assert rows[1]["VOID_REASON"] == "Cancelación de transferencia"

    # Verify no secret keywords leaked
    assert "password" not in csv_text.lower()
    assert "secret" not in csv_text.lower()
    assert "token" not in csv_text.lower()


def test_multiworker_concurrent_reservations(client: TestClient):
    """Verify concurrent reservations with parallel workers on same series (zero duplicates)."""
    types_res = client.get("/api/logistics/document-types")
    po_item = next(t for t in types_res.json() if t["code"] == "PO")
    struct_res = client.get("/api/logistics/structure")
    branch = struct_res.json()["organizations"][0]["branches"][0]

    series_res = client.post(
        "/api/logistics/document-series",
        json={
            "document_type_id": po_item["id"],
            "branch_id": branch["id"],
            "period_year": 2027,
        },
        headers=csrf_headers(),
    )
    series_id = uuid.UUID(series_res.json()["id"])
    me_data = client.get("/api/auth/me").json()
    user_id = uuid.UUID(me_data["user"]["id"])
    org_id = uuid.UUID(me_data["organization_id"])

    # Worker function executing direct database service with SELECT FOR UPDATE
    def worker_reserve(batch_size: int):
        db = SessionLocal()
        try:
            from app.core.rbac import AuthenticatedPrincipal

            principal = AuthenticatedPrincipal(
                user_id=user_id,
                email="worker@logistica.local",
                organization_id=org_id,
                session_id=uuid.uuid4(),
                display_name="Worker",
                role_ids=[],
                role_codes=["MANAGEMENT"],
                permissions={"document_series.reserve"},
                is_active=True,
            )
            ctx = AuditContext(
                actor_id=user_id,
                correlation_id=uuid.uuid4(),
            )
            payload = DocumentSeriesReservationCreate(
                quantity=batch_size,
                reason="Concurrent worker reservation",
            )
            resv = DocumentSeriesService.reserve_correlatives(
                db=db,
                series_id=series_id,
                payload=payload,
                principal=principal,
                context=ctx,
            )
            return [n.correlative for n in resv.numbers]
        finally:
            db.close()

    # Run 10 parallel workers with 10 correlatives each = 100 correlatives total
    workers_count = 10
    batch_size = 10
    total_expected = workers_count * batch_size

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers_count) as executor:
        futures = [executor.submit(worker_reserve, batch_size) for _ in range(workers_count)]
        results = [f.result() for f in futures]

    all_correlatives = [c for batch in results for c in batch]
    assert len(all_correlatives) == total_expected
    assert len(set(all_correlatives)) == total_expected
    assert min(all_correlatives) == 1
    assert max(all_correlatives) == total_expected

    # Verify final series counter
    db = SessionLocal()
    try:
        final_series = db.get(DocumentSeries, series_id)
        assert final_series.next_correlative == total_expected + 1
    finally:
        db.close()


def test_destructive_delete_endpoints_absent(client: TestClient):
    """Verify absence of destructive deletion endpoints for series, reservations, or numbers."""
    fake_id = str(uuid.uuid4())
    assert client.delete(f"/api/logistics/document-series/{fake_id}").status_code in [404, 405]
    assert client.delete(f"/api/logistics/document-series/reservations/{fake_id}").status_code in [
        404,
        405,
    ]
    assert client.delete(f"/api/logistics/document-series/numbers/{fake_id}").status_code in [
        404,
        405,
    ]
