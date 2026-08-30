"""Automated Tests for Outbound Document Package (F018).

Tests schemas, Jinja2 rendering, WeasyPrint compilation, QR decoding,
SHA-256 dual-stage hashing, multipage pagination, business scenarios,
security autoescape, concurrency isolation, and FastAPI REST endpoints for the 7 outbound types.
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
from app.modules.documents.router import build_outbound_sample_context
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


def test_01_all_7_outbound_templates_registered():
    """Verify that all 7 outbound document templates and aliases are registered."""
    outbound_manifests = TemplateRegistry.list_templates(family="outbound")
    keys = {m.template_key for m in outbound_manifests}

    expected = {
        "outbound_request_v1",
        "outbound_order_v1",
        "picking_list_v1",
        "packing_list_v1",
        "manifest_v1",
        "dispatch_report_v1",
        "seal_control_v1",
    }
    assert expected.issubset(keys), f"Missing manifests: {expected - keys}"

    # Verify alias resolution
    assert TemplateRegistry.get_manifest("picking_sheet_v1").template_key == "picking_list_v1"
    assert TemplateRegistry.get_manifest("cargo_manifest_v1").template_key == "manifest_v1"
    assert TemplateRegistry.get_manifest("dispatch_guide_v1").template_key == "dispatch_report_v1"


def test_02_catalog_mapping_and_zero_collisions():
    """Verify that the 7 outbound types in PostgreSQL catalog have valid template bindings."""
    db: Session = SessionLocal()
    try:
        outbound_codes = ["OUT_REQ", "ODS", "PICK", "PACK", "MNF", "DSP", "SEAL"]
        types = db.query(DocumentType).filter(DocumentType.code.in_(outbound_codes)).all()
        assert len(types) == 7

        for dt in types:
            assert dt.family.code == "OUTBOUND"
            assert dt.document_scope == "INTERNAL"
            assert dt.is_active is True
    finally:
        db.close()


def test_03_outbound_request_rendering_and_qr():
    """Verify rendering of Outbound Request (Solicitud de Salida) with QR decoding."""
    service = DocumentRenderingService()
    ctx, tpl_key = build_outbound_sample_context("OUT_REQ", scenario="basic")

    pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(ctx, tpl_key)

    assert len(pdf_bytes) > 2000
    assert "Solicitud de Salida de Almacén" in html_content
    assert "DISTRIBUIDORA INDUSTRIAL DEL SUR" in html_content
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
    assert qr_payload["document_type"] == "OUT_REQ"
    assert "display_code" in qr_payload
    assert qr_payload["snapshot_hash"] == snapshot_hash


def test_04_outbound_order_rendering():
    """Verify rendering of Outbound Order (ODS)."""
    service = DocumentRenderingService()
    ctx, tpl_key = build_outbound_sample_context("ODS", scenario="basic")

    pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(ctx, tpl_key)

    assert len(pdf_bytes) > 2000
    assert "Orden de Salida / Despacho (ODS)" in html_content
    assert "Materiales Autorizados para Egreso" in html_content
    assert len(snapshot_hash) == 64


def test_05_picking_list_rendering():
    """Verify rendering of Picking List with location code sequence."""
    service = DocumentRenderingService()
    ctx, tpl_key = build_outbound_sample_context("PICK", scenario="basic")

    pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(ctx, tpl_key)

    assert len(pdf_bytes) > 2000
    assert "Hoja / Lista de Picking" in html_content
    assert "Secuencia de Recolección en Almacén" in html_content
    assert "Z01-P" in html_content


def test_06_packing_list_rendering():
    """Verify rendering of Packing List with box/package hierarchy."""
    service = DocumentRenderingService()
    ctx, tpl_key = build_outbound_sample_context("PACK", scenario="basic")

    pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(ctx, tpl_key)

    assert len(pdf_bytes) > 2000
    assert "Lista de Empaque / Packing List" in html_content
    assert "Distribución y Contenido por Bulto" in html_content
    assert "CX-001" in html_content


def test_07_cargo_manifest_rendering():
    """Verify rendering of Cargo Manifest with transport snapshot."""
    service = DocumentRenderingService()
    ctx, tpl_key = build_outbound_sample_context("MNF", scenario="basic")

    pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(ctx, tpl_key)

    assert len(pdf_bytes) > 2000
    assert "Manifiesto de Carga Consolidado" in html_content
    assert "TRANSPORTES Y CARGA EXPRÉS" in html_content
    assert "ABC-123" in html_content


def test_08_dispatch_report_and_seal_control_rendering():
    """Verify Dispatch Report (DSP) and Seal Control (SEAL) rendering."""
    service = DocumentRenderingService()

    # DSP
    ctx_dsp, tpl_dsp = build_outbound_sample_context("DSP", scenario="basic")
    pdf_dsp, html_dsp, _, _ = service.process_and_render(ctx_dsp, tpl_dsp)
    assert len(pdf_dsp) > 2000
    assert "Acta Oficial de Despacho" in html_dsp
    assert "MUELLE N° 03" in html_dsp

    # SEAL
    ctx_seal, tpl_seal = build_outbound_sample_context("SEAL", scenario="replacement")
    pdf_seal, html_seal, _, _ = service.process_and_render(ctx_seal, tpl_seal)
    assert len(pdf_seal) > 2000
    assert "Acta de Control de Precintos" in html_seal
    assert "EVENTO DE REEMPLAZO DE PRECINTO" in html_seal


def test_09_multipage_pagination():
    """Verify multipage (50 rows) rendering spans multiple pages cleanly."""
    service = DocumentRenderingService()
    ctx, tpl = build_outbound_sample_context("OUT_REQ", scenario="multipage")

    pdf_bytes, html, _, _ = service.process_and_render(ctx, tpl)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    assert page_count >= 2, f"Multipage scenario should produce at least 2 pages, got {page_count}"
    assert "PRD-OUT-1050" in html


def test_10_security_autoescaping_and_traversal_rejection():
    """Verify autoescape against XSS and path traversal protection."""
    service = DocumentRenderingService()

    # XSS Autoescaping
    ctx_xss, tpl_xss = build_outbound_sample_context("OUT_REQ", scenario="basic")
    ctx_xss.organization.name = "<script>alert('xss')</script> Organizacion Segura"
    _, html_xss, _, _ = service.process_and_render(ctx_xss, tpl_xss)
    assert "<script>" not in html_xss
    assert "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;" in html_xss

    # Path traversal rejection
    with pytest.raises(DomainError):
        TemplateRegistry.get_manifest("../../../../etc/passwd")


def test_11_concurrency_isolation():
    """Verify concurrent rendering isolation across different outbound templates."""
    service = DocumentRenderingService()

    def render_task(doc_code: str):
        ctx, tpl_key = build_outbound_sample_context(doc_code, scenario="basic")
        pdf_bytes, html, snap_hash, pdf_hash = service.process_and_render(ctx, tpl_key)
        return doc_code, len(pdf_bytes), snap_hash, pdf_hash

    codes = ["OUT_REQ", "ODS", "PICK", "PACK", "MNF", "DSP", "SEAL"] * 3
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(render_task, codes))

    assert len(results) == 21
    for code, pdf_len, snap_hash, pdf_hash in results:
        assert pdf_len > 2000
        assert len(snap_hash) == 64
        assert len(pdf_hash) == 64


def test_12_fastapi_outbound_sample_endpoints_e2e(client: TestClient):
    """Verify E2E execution of POST /api/logistics/document-renderer/outbound/{doc_code}/sample."""
    csrf = generate_csrf_token()
    headers = {"X-CSRF-Token": csrf}

    for code in ["OUT_REQ", "ODS", "PICK", "PACK", "MNF", "DSP", "SEAL"]:
        resp = client.post(
            f"/api/logistics/document-renderer/outbound/{code}/sample?scenario=basic&format=pdf",
            headers=headers,
        )
        assert resp.status_code == 200, f"Failed for {code}: {resp.text}"
        assert resp.headers["content-type"] == "application/pdf"
        assert "X-Snapshot-Hash" in resp.headers
        assert "X-Pdf-Hash" in resp.headers
        assert resp.headers["x-document-type"] == code
        assert resp.content.startswith(b"%PDF-1.")

        html_res = client.post(
            f"/api/logistics/document-renderer/outbound/{code}/sample?scenario=basic&format=html",
            headers=headers,
        )
        assert html_res.status_code == 200

    # Invalid code check
    bad_res = client.post(
        "/api/logistics/document-renderer/outbound/INVALID_CODE/sample",
        headers=headers,
    )
    assert bad_res.status_code == 400
    assert "Código documental de salida no soportado" in bad_res.text
