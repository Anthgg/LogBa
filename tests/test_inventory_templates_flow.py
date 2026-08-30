"""Automated Tests for Inventory Document Package (F017).

Tests schemas, Jinja2 rendering, WeasyPrint compilation, QR decoding,
SHA-256 dual-stage hashing, multipage pagination, blind count support,
security autoescape, concurrency isolation, and FastAPI REST endpoints for the 7 inventory types.
"""

import base64
import concurrent.futures
import io
import json
import re

import pytest
import zxingcpp
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.db.connection import SessionLocal
from app.main import app
from app.modules.auth.csrf import generate_csrf_token
from app.modules.documents.models import DocumentType
from app.modules.documents.router import build_inventory_sample_context
from app.scripts import seed_demo
from app.shared.documents.service import DocumentRenderingService
from app.shared.documents.templates.registry import TemplateRegistry
from tests.conftest import enable_step_up_for_client

settings = get_settings()


@pytest.fixture
def client() -> TestClient:
    seed_demo.run_seed()
    c = TestClient(app)
    csrf = generate_csrf_token()
    login_res = c.post(
        "/api/auth/login",
        json={"email": "gerencia.demo@logistica.local", "password": settings.DEMO_USER_PASSWORD},
        headers={"X-CSRF-Token": csrf},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    enable_step_up_for_client(c)
    return c


def test_01_all_7_inventory_templates_registered():
    """Verify that all 7 inventory document templates and aliases are registered."""
    inv_manifests = TemplateRegistry.list_templates(family="inventory")
    keys = {m.template_key for m in inv_manifests}

    expected = {
        "location_label_v1",
        "inventory_movement_v1",
        "inventory_adjustment_v1",
        "physical_count_v1",
        "count_difference_v1",
        "warehouse_transfer_v1",
        "transfer_receipt_v1",
    }
    assert expected.issubset(keys), f"Missing manifests: {expected - keys}"

    # Verify alias resolution
    assert TemplateRegistry.get_manifest("stock_count_v1").template_key == "physical_count_v1"
    assert (
        TemplateRegistry.get_manifest("transfer_request_v1").template_key == "warehouse_transfer_v1"
    )


def test_02_catalog_mapping_and_zero_collisions():
    """Verify that the 7 inventory types in PostgreSQL catalog have valid template bindings."""
    db: Session = SessionLocal()
    try:
        inv_codes = ["LBL", "MOV", "INV_ADJ", "CNT", "CDIFF", "TRF", "TRF_REC"]
        types = db.query(DocumentType).filter(DocumentType.code.in_(inv_codes)).all()
        assert len(types) == 7

        for dt in types:
            assert dt.family.code == "INVENTORY"
            assert dt.document_scope == "INTERNAL"
            assert dt.is_active is True
    finally:
        db.close()


def test_03_location_label_rendering_and_qr():
    """Verify rendering of Location Label (100x150mm) with QR decoding and hierarchy."""
    service = DocumentRenderingService()
    ctx, tpl_key = build_inventory_sample_context("LBL", scenario="basic")

    pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(ctx, tpl_key)

    assert len(pdf_bytes) > 2000
    assert "ALM01" in html_content
    assert "UBICACIÓN CANÓNICA WMS" in html_content
    assert "data:image/png;base64," in html_content
    assert len(snapshot_hash) == 64
    assert len(pdf_hash) == 64

    # Extract and decode QR code
    m = re.search(r"data:image/png;base64,([A-Za-z0-9+/=]+)", html_content)
    assert m, "QR code image data uri not found in HTML"
    qr_bytes = base64.b64decode(m.group(1))
    img = Image.open(io.BytesIO(qr_bytes))
    results = zxingcpp.read_barcodes(img)
    assert len(results) > 0
    qr_payload = json.loads(results[0].text)
    assert qr_payload["document_type"] == "LBL"
    assert "display_code" in qr_payload
    assert qr_payload["snapshot_hash"] == snapshot_hash


def test_04_inventory_movement_rendering():
    """Verify rendering of internal inventory movement document."""
    service = DocumentRenderingService()
    ctx, tpl_key = build_inventory_sample_context("MOV", scenario="basic")

    pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(ctx, tpl_key)

    assert len(pdf_bytes) > 3000
    assert "Movimiento Interno de Inventario" in html_content
    assert "Origen" in html_content
    assert "Destino" in html_content
    assert len(snapshot_hash) == 64


def test_05_inventory_adjustment_rendering():
    """Verify rendering of inventory adjustment document with step-up banner."""
    service = DocumentRenderingService()
    ctx, tpl_key = build_inventory_sample_context("INV_ADJ", scenario="basic")

    pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(ctx, tpl_key)

    assert len(pdf_bytes) > 3000
    assert "Acta Oficial de Ajuste de Inventario" in html_content
    assert "Autorización Step-Up" in html_content
    assert "Impacto Valorizado Total" in html_content


def test_06_blind_count_omits_system_qty():
    """CRITICAL: Verify that Blind Count mode completely omits system_qty from context & output."""
    service = DocumentRenderingService()

    # 1. Normal count
    ctx_normal, tpl_normal = build_inventory_sample_context("CNT", scenario="basic")
    _, html_normal, _, _ = service.process_and_render(ctx_normal, tpl_normal)
    assert "Teórico" in html_normal

    # 2. Blind count
    ctx_blind, tpl_blind = build_inventory_sample_context("CNT", scenario="blind")
    _, html_blind, _, _ = service.process_and_render(ctx_blind, tpl_blind)

    assert "MODO CONTEO CIEGO (BLIND COUNT)" in html_blind
    assert "Teórico" not in html_blind, (
        "system_qty / Teórico MUST NOT be present in blind count output"
    )


def test_07_count_difference_and_transfer_rendering():
    """Verify count difference, warehouse transfer, and transfer receipt rendering."""
    service = DocumentRenderingService()

    # CDIFF
    ctx, tpl = build_inventory_sample_context("CDIFF", scenario="basic")
    pdf_bytes, html, _, _ = service.process_and_render(ctx, tpl)
    assert len(pdf_bytes) > 3000
    assert "Acta de Diferencias de Conteo Físico" in html

    # TRF
    ctx, tpl = build_inventory_sample_context("TRF", scenario="basic")
    pdf_bytes, html, _, _ = service.process_and_render(ctx, tpl)
    assert len(pdf_bytes) > 3000
    assert "Solicitud de Transferencia entre Almacenes" in html

    # TRF_REC with differences
    ctx, tpl = build_inventory_sample_context("TRF_REC", scenario="difference")
    pdf_bytes, html, _, _ = service.process_and_render(ctx, tpl)
    assert len(pdf_bytes) > 3000
    assert "Acta de Recepción de Transferencia" in html
    assert "Desviaciones Encontradas" in html


def test_08_multipage_pagination():
    """Verify multipage (50 rows) rendering spans multiple pages cleanly."""
    service = DocumentRenderingService()
    ctx, tpl = build_inventory_sample_context("MOV", scenario="multipage")

    pdf_bytes, html, _, _ = service.process_and_render(ctx, tpl)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    assert page_count >= 2, f"Multipage scenario should produce at least 2 pages, got {page_count}"
    assert "MAT-REF-0050" in html


def test_09_security_autoescaping_and_traversal_rejection():
    """Verify autoescape against XSS and path traversal protection."""
    service = DocumentRenderingService()

    # XSS Autoescaping
    ctx_xss, tpl_xss = build_inventory_sample_context("LBL", scenario="basic")
    ctx_xss.organization.name = "<script>alert('xss')</script> Organizacion Segura"
    _, html_xss, _, _ = service.process_and_render(ctx_xss, tpl_xss)
    assert "<script>" not in html_xss
    assert "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;" in html_xss

    # Path traversal rejection
    with pytest.raises(DomainError):
        TemplateRegistry.get_manifest("../../../../etc/passwd")


def test_10_concurrency_isolation():
    """Verify concurrent rendering isolation across different inventory templates."""
    service = DocumentRenderingService()

    def render_task(doc_code: str):
        ctx, tpl_key = build_inventory_sample_context(doc_code, scenario="basic")
        pdf_bytes, html, snap_hash, pdf_hash = service.process_and_render(ctx, tpl_key)
        return doc_code, len(pdf_bytes), snap_hash, pdf_hash

    codes = ["LBL", "MOV", "INV_ADJ", "CNT", "CDIFF", "TRF", "TRF_REC"] * 3
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(render_task, codes))

    assert len(results) == 21
    for code, pdf_len, snap_hash, pdf_hash in results:
        assert pdf_len > 2000
        assert len(snap_hash) == 64
        assert len(pdf_hash) == 64


def test_11_fastapi_inventory_sample_endpoints_e2e(client: TestClient):
    """Verify E2E execution of POST /api/logistics/document-renderer/inventory/{doc_code}/sample."""
    for code in ["LBL", "MOV", "INV_ADJ", "CNT", "CDIFF", "TRF", "TRF_REC"]:
        resp = client.post(
            f"/api/logistics/document-renderer/inventory/{code}/sample?scenario=basic&format=pdf"
        )
        assert resp.status_code == 200, f"Failed for {code}: {resp.text}"
        assert resp.headers["content-type"] == "application/pdf"
        assert "X-Snapshot-Hash" in resp.headers
        assert "X-Pdf-Hash" in resp.headers
        assert resp.headers["x-document-type"] == code
        assert resp.content.startswith(b"%PDF-1.")

        html_res = client.post(
            f"/api/logistics/document-renderer/inventory/{code}/sample?scenario=basic&format=html"
        )
        assert html_res.status_code == 200

    # Invalid code check
    bad_res = client.post("/api/logistics/document-renderer/inventory/INVALID_CODE/sample")
    assert bad_res.status_code == 400
    assert "Código documental de inventario no soportado" in bad_res.text
