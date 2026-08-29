"""Comprehensive Test Suite for F015 Purchasing Document Package (F015)."""

import base64
import concurrent.futures
import io
import json
import re

import pymupdf
import pytest
import zxingcpp
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader

from app.core.config import get_settings
from app.core.errors import DomainError
from app.db.connection import SessionLocal
from app.main import app
from app.modules.auth.csrf import generate_csrf_token
from app.modules.documents.models import DocumentFamily, DocumentType
from app.modules.documents.router import build_purchasing_sample_context
from app.scripts import seed_demo
from app.shared.documents.service import DocumentRenderingService
from app.shared.documents.templates.registry import TemplateRegistry
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


def test_purchasing_templates_registration_and_manifests():
    """Verify all 6 purchasing templates are registered in TemplateRegistry."""
    purchasing_templates = TemplateRegistry.list_templates(family="purchasing")
    assert len(purchasing_templates) == 6, (
        f"Expected 6 purchasing templates, found {len(purchasing_templates)}"
    )

    keys = [t.template_key for t in purchasing_templates]
    expected_keys = [
        "purchase_requisition_v1",
        "request_for_quotation_v1",
        "comparative_table_v1",
        "purchase_order_v1",
        "purchase_approval_v1",
        "supplier_send_confirmation_v1",
    ]
    for k in expected_keys:
        assert k in keys, f"Missing template key {k}"

    # Check landscape for comparative table
    cmp_m = TemplateRegistry.get_manifest("comparative_table_v1")
    assert cmp_m.orientation == "landscape"
    assert cmp_m.page_size == "A4"

    # Check portrait for PO
    po_m = TemplateRegistry.get_manifest("purchase_order_v1")
    assert po_m.orientation == "portrait"
    assert po_m.page_size == "A4"


def test_purchasing_document_types_and_zero_code_collisions():
    """Verify database catalog contains all 6 purchasing document types with 0 collisions."""
    with SessionLocal() as db:
        purchasing_family = (
            db.query(DocumentFamily).filter(DocumentFamily.code == "PURCHASING").first()
        )
        assert purchasing_family is not None

        doc_types = (
            db.query(DocumentType).filter(DocumentType.family_id == purchasing_family.id).all()
        )
        assert len(doc_types) == 6

        codes = [dt.code for dt in doc_types]
        assert len(codes) == len(set(codes)), "Duplicate document codes found in purchasing family!"
        for expected in ("REQ", "RFQ", "CMP", "PO", "POA", "PSC"):
            assert expected in codes, f"Expected document type code {expected} missing in database!"


@pytest.mark.parametrize(
    "doc_code,expected_tpl",
    [
        ("REQ", "purchase_requisition_v1"),
        ("RFQ", "request_for_quotation_v1"),
        ("CMP", "comparative_table_v1"),
        ("PO", "purchase_order_v1"),
        ("POA", "purchase_approval_v1"),
        ("PSC", "supplier_send_confirmation_v1"),
    ],
)
def test_render_individual_purchasing_templates(doc_code: str, expected_tpl: str):
    """Verify rendering of each purchasing template produces valid PDF, SHA-256 hashes, and HTML."""
    service = DocumentRenderingService()
    ctx, tpl_key = build_purchasing_sample_context(doc_code=doc_code, scenario="basic")
    assert tpl_key == expected_tpl

    pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(
        ctx, template_key=tpl_key
    )

    assert pdf_bytes.startswith(b"%PDF-1.")
    assert len(snapshot_hash) == 64
    assert len(pdf_hash) == 64
    assert "<!DOCTYPE html>" in html_content
    assert ctx.document.display_code in html_content


def test_comparative_table_landscape_orientation():
    """Verify comparative table renders with landscape page geometry (width > height)."""
    service = DocumentRenderingService()
    ctx, tpl_key = build_purchasing_sample_context(doc_code="CMP", scenario="basic")

    pdf_bytes, _, _, _ = service.process_and_render(ctx, template_key=tpl_key)
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    rect = page.rect  # A4 landscape is ~841.89 x 595.27 points

    assert rect.width > rect.height, (
        f"Expected landscape width > height, got {rect.width}x{rect.height}"
    )
    assert 835 <= rect.width <= 850
    assert 590 <= rect.height <= 600


@pytest.mark.parametrize("doc_code", ["REQ", "RFQ", "CMP", "PO", "POA", "PSC"])
def test_purchasing_qr_barcode_roundtrip(doc_code: str):
    """Verify QR barcode generated for each purchasing document decodes reliably via zxing-cpp."""
    ctx, tpl_key = build_purchasing_sample_context(doc_code=doc_code, scenario="basic")
    service = DocumentRenderingService()
    pdf_bytes, html_content, snapshot_hash, _ = service.process_and_render(
        ctx, template_key=tpl_key
    )

    m = re.search(r'src="(data:image/png;base64,[^"]+)"', html_content)
    assert m is not None, "QR image data-uri not found in rendered HTML!"
    b64_content = m.group(1).split(",")[1]
    img_bytes = base64.b64decode(b64_content)
    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    decoded = zxingcpp.read_barcode(pil_img)
    assert decoded is not None
    decoded_json = json.loads(decoded.text)
    assert decoded_json["document_type"] == doc_code
    assert decoded_json["display_code"] == ctx.document.display_code
    assert decoded_json["snapshot_hash"] == snapshot_hash


def test_multipage_purchase_order_and_requisition():
    """Verify multipage table pagination and page numbering on 50-item PO and REQ."""
    service = DocumentRenderingService()

    # 1. PO Multipage
    po_ctx, po_tpl = build_purchasing_sample_context(doc_code="PO", scenario="multipage")
    po_pdf, _, _, _ = service.process_and_render(po_ctx, template_key=po_tpl)
    po_reader = PdfReader(io.BytesIO(po_pdf))
    assert len(po_reader.pages) >= 2, (
        f"Expected >= 2 pages for 50 PO items, got {len(po_reader.pages)}"
    )

    # 2. REQ Multipage
    req_ctx, req_tpl = build_purchasing_sample_context(doc_code="REQ", scenario="multipage")
    req_pdf, _, _, _ = service.process_and_render(req_ctx, template_key=req_tpl)
    req_reader = PdfReader(io.BytesIO(req_pdf))
    assert len(req_reader.pages) >= 2, (
        f"Expected >= 2 pages for 50 REQ items, got {len(req_reader.pages)}"
    )


def test_security_autoescape_and_path_traversal():
    """Verify Jinja2 autoescaping protects against XSS injection in supplier names and notes."""
    service = DocumentRenderingService()
    ctx, tpl_key = build_purchasing_sample_context(doc_code="PO", scenario="basic")

    ctx.custom_content["supplier"]["name"] = "<script>alert('xss_attack')</script> Proveedor Seguro"
    ctx.notes = "<b>Importante:</b> Entrega en <img src=x onerror=alert(1)> almacén."

    pdf_bytes, html_content, _, _ = service.process_and_render(ctx, template_key=tpl_key)
    assert "<script>" not in html_content
    assert "&lt;script&gt;alert(&#39;xss_attack&#39;)&lt;/script&gt;" in html_content
    assert "<img src=x" not in html_content
    assert pdf_bytes.startswith(b"%PDF-1.")

    # Path traversal rejection
    with pytest.raises(DomainError) as exc:
        TemplateRegistry.resolve_template_path("../../etc/shadow")
    assert exc.value.code in ["TEMPLATE_PATH_TRAVERSAL_DETECTED", "TEMPLATE_NOT_FOUND"]


def test_purchasing_sample_api_endpoints(client: TestClient):
    """Verify REST API sample endpoints for all 6 purchasing documents."""
    for code in ("REQ", "RFQ", "CMP", "PO", "POA", "PSC"):
        # 1. PDF format
        res_pdf = client.post(
            f"/api/logistics/document-renderer/purchasing/{code}/sample?format=pdf&scenario=basic"
        )
        assert res_pdf.status_code == 200
        assert res_pdf.headers["content-type"] == "application/pdf"
        assert res_pdf.headers["x-document-type"] == code
        assert "X-Snapshot-Hash" in res_pdf.headers
        assert "X-Pdf-Hash" in res_pdf.headers
        assert res_pdf.content.startswith(b"%PDF-1.")

        # 2. HTML format
        res_html = client.post(
            f"/api/logistics/document-renderer/purchasing/{code}/sample?format=html&scenario=basic"
        )
        assert res_html.status_code == 200
        assert "text/html" in res_html.headers["content-type"]
        assert f"PREVIEW-{code}-" in res_html.text


def test_purchasing_concurrency_isolation():
    """Verify concurrent rendering of distinct purchasing document types in parallel threads."""
    service = DocumentRenderingService()

    def worker_task(code: str, idx: int):
        ctx, tpl_key = build_purchasing_sample_context(doc_code=code, scenario="basic")
        ctx.document.display_code = f"PREVIEW-{code}-LIM-2026-{idx:04d}"
        ctx.notes = f"Nota aislada de thread para worker {idx} - {code}"
        pdf_bytes, _, s_hash, p_hash = service.process_and_render(ctx, template_key=tpl_key)
        return code, ctx.document.display_code, s_hash, p_hash, len(pdf_bytes)

    tasks = [
        ("REQ", 1),
        ("RFQ", 2),
        ("CMP", 3),
        ("PO", 4),
        ("POA", 5),
        ("PSC", 6),
        ("REQ", 7),
        ("RFQ", 8),
        ("CMP", 9),
        ("PO", 10),
        ("POA", 11),
        ("PSC", 12),
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker_task, code, idx) for code, idx in tasks]
        results = [f.result() for f in futures]

    assert len(results) == 12
    display_codes = [r[1] for r in results]
    snapshot_hashes = [r[2] for r in results]
    assert len(set(display_codes)) == 12
    assert len(set(snapshot_hashes)) == 12
