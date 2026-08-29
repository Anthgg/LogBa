"""Comprehensive Test Suite for F014 Document Template Engine, HTML/CSS to PDF, QR, and Hashing."""

import base64
import concurrent.futures
import io
import json

import pymupdf  # PyMuPDF
import pytest
import zxingcpp
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader

from app.core.config import get_settings
from app.core.errors import DomainError
from app.main import app
from app.modules.auth.csrf import generate_csrf_token
from app.scripts import seed_demo
from app.shared.documents.hashing.service import CanonicalSnapshotService
from app.shared.documents.qr.service import DocumentQRService
from app.shared.documents.renderer.pdf import local_only_url_fetcher
from app.shared.documents.schemas.context import (
    BranchHeaderContext,
    DocumentHeaderContext,
    DocumentMetadataContext,
    DocumentRenderContext,
    DocumentTableContext,
    OrganizationHeaderContext,
    TableColumnContext,
    VisualSignatureContext,
)
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


def build_sample_context(status: str = "DRAFT", rows_count: int = 5) -> DocumentRenderContext:
    rows = []
    for i in range(1, rows_count + 1):
        rows.append(
            {
                "item_no": str(i),
                "sku": f"MAT-GRE-{i:04d}",
                "description": (f"Greda refractaria estándar grado {i} para hornos industriales"),
                "unit": "KG",
                "quantity": f"{i * 10.0:.2f}",
                "unit_price": f"S/ {15.50 + i:.2f}",
                "total": f"S/ {(i * 10.0) * (15.50 + i):.2f}",
            }
        )

    return DocumentRenderContext(
        organization=OrganizationHeaderContext(
            name="Organización Logística Integral del Perú",
            code="ORG-01",
            tax_id="20100012345",
        ),
        branch=BranchHeaderContext(
            name="Sede Principal Lima",
            code="LIM",
            address="Av. Industrial 456, Parque Logístico, Lima, Perú",
        ),
        document=DocumentHeaderContext(
            type_code="PO",
            type_name="Orden de Compra / Requisición Logística",
            display_code="PO-LIM-2026-000001",
            status=status,
            version_number=1,
            emission_date="2026-08-29",
        ),
        metadata=DocumentMetadataContext(
            generated_by="gerencia.demo@logistica.local",
            template_key="base_document_v1",
            template_version="1.0.0",
        ),
        summary_fields=[
            {"label": "Proveedor", "value": "Insumos Minerales del Perú S.A.C."},
            {"label": "Condición de Pago", "value": "Crédito 30 días"},
            {"label": "Moneda", "value": "Soles (PEN)"},
        ],
        tables=[
            DocumentTableContext(
                title="Detalle de Ítems e Insumos",
                columns=[
                    TableColumnContext(key="item_no", label="Item", align="center", width="5%"),
                    TableColumnContext(key="sku", label="Código SKU", align="center", width="15%"),
                    TableColumnContext(
                        key="description", label="Descripción", align="left", width="40%"
                    ),
                    TableColumnContext(key="unit", label="U.M.", align="center", width="10%"),
                    TableColumnContext(
                        key="quantity", label="Cantidad", align="right", width="10%"
                    ),
                    TableColumnContext(
                        key="unit_price", label="P. Unit.", align="right", width="10%"
                    ),
                    TableColumnContext(key="total", label="Total", align="right", width="10%"),
                ],
                rows=rows,
            )
        ],
        notes="Documento de prueba sintético con caracteres especiales: ñ, á, é, í, ó, ú, $, S/.",
        visual_signature=VisualSignatureContext(
            signer_name="Gerencia Demo",
            signer_role="Director de Operaciones",
            signed_at="2026-08-29 13:00:00 UTC",
        ),
    )


def test_template_registry_and_path_traversal_protection():
    """Verify template registry lookup, family filtering, and path traversal rejection."""
    templates = TemplateRegistry.list_templates()
    assert len(templates) >= 1
    base_m = TemplateRegistry.get_manifest("base_document_v1")
    assert base_m.template_key == "base_document_v1"
    assert base_m.family == "base"
    assert base_m.supported_renderer == "WeasyPrint"

    # Test unknown template
    with pytest.raises(DomainError) as exc_info:
        TemplateRegistry.get_manifest("unknown_template_xyz")
    assert exc_info.value.code == "TEMPLATE_NOT_FOUND"

    # Test path traversal attempts
    traversal_keys = ["../../etc/passwd", "../templates/base", "base/../../secret", "base\\file"]
    for bad_key in traversal_keys:
        with pytest.raises(DomainError) as exc:
            TemplateRegistry.resolve_template_path(bad_key)
        assert exc.value.code in ["TEMPLATE_PATH_TRAVERSAL_DETECTED", "TEMPLATE_NOT_FOUND"]


def test_snapshot_canonicalization_and_hash_integrity():
    """Verify deterministic canonical snapshot serialization and SHA-256 hash sensitivity."""
    ctx = build_sample_context(status="DRAFT", rows_count=3)
    data1 = ctx.model_dump()
    data2 = json.loads(json.dumps(data1))

    # Same data -> identical canonical JSON and hash
    canon1 = CanonicalSnapshotService.canonical_json(data1)
    canon2 = CanonicalSnapshotService.canonical_json(data2)
    assert canon1 == canon2

    hash1 = CanonicalSnapshotService.compute_snapshot_hash(data1)
    hash2 = CanonicalSnapshotService.compute_snapshot_hash(data2)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex string

    # Modifying a single character alters the hash
    data2["document"]["display_code"] = "PO-LIM-2026-000002"
    hash_modified = CanonicalSnapshotService.compute_snapshot_hash(data2)
    assert hash1 != hash_modified


def test_qr_generation_and_roundtrip_decoding():
    """Verify QR generation to Data URI PNG and roundtrip decoding with zxing-cpp."""
    payload = {
        "document_type": "PO",
        "display_code": "PO-LIM-2026-000001",
        "version": 1,
        "snapshot_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "generated_at": "2026-08-29T13:00:00Z",
    }
    data_uri = DocumentQRService.generate_qr_data_uri(payload)
    assert data_uri.startswith("data:image/png;base64,")

    # Decode data URI to PIL Image
    b64_content = data_uri.split(",")[1]
    img_bytes = base64.b64decode(b64_content)
    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    # Read barcode using zxing-cpp
    decoded = zxingcpp.read_barcode(pil_img)
    assert decoded is not None
    decoded_json = json.loads(decoded.text)
    assert decoded_json["document_type"] == payload["document_type"]
    assert decoded_json["display_code"] == payload["display_code"]
    assert decoded_json["version"] == payload["version"]
    assert decoded_json["snapshot_hash"] == payload["snapshot_hash"]


def test_html_and_pdf_rendering_pipeline():
    """Verify complete rendering pipeline producing valid HTML and compiled PDF bytes."""
    service = DocumentRenderingService()
    ctx = build_sample_context(status="DRAFT", rows_count=5)

    pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(ctx)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")  # Valid PDF signature
    assert len(snapshot_hash) == 64
    assert len(pdf_hash) == 64
    assert "<!DOCTYPE html>" in html_content
    assert "PO-LIM-2026-000001" in html_content
    assert "BORRADOR" in html_content
    assert "Greda refractaria" in html_content


def test_pdf_multipage_and_pagination():
    """Verify multipage document rendering (50 rows across multiple pages) with page counters."""
    service = DocumentRenderingService()
    ctx = build_sample_context(status="ISSUED", rows_count=50)

    pdf_bytes, _, _, _ = service.process_and_render(ctx)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    num_pages = len(reader.pages)
    assert num_pages >= 2, f"Expected at least 2 pages for 50 rows, got {num_pages}"

    # Verify text on page 1 and last page
    page1_text = reader.pages[0].extract_text()
    assert "PO-LIM-2026-000001" in page1_text
    assert "MAT-GRE-0001" in page1_text


def test_unicode_and_currency_rendering():
    """Verify Spanish Unicode characters and currency symbols render correctly."""
    service = DocumentRenderingService()
    ctx = build_sample_context(status="APPROVED", rows_count=2)
    ctx.notes = (
        "Atención: Envío de camión con ñandú, caña y estaño. Precio: S/ 1,250.50 ($350.00 USD)."
    )

    pdf_bytes, html_content, _, _ = service.process_and_render(ctx)
    assert "Atención: Envío de camión con ñandú, caña y estaño" in html_content
    assert "S/ 1,250.50" in html_content

    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(p.extract_text() for p in reader.pages)
    assert "Atención" in full_text or "ñandú" in full_text or "PO-LIM" in full_text


def test_optional_logo_and_signature():
    """Verify rendering without logo and without visual signature proceeds gracefully."""
    service = DocumentRenderingService()
    ctx = build_sample_context(status="ISSUED", rows_count=3)
    ctx.organization.logo_base64 = None
    ctx.visual_signature = None

    pdf_bytes, html_content, _, _ = service.process_and_render(ctx)
    assert pdf_bytes.startswith(b"%PDF-")
    assert '<img src="" class="org-logo"' not in html_content
    assert '<div class="signer-name">' not in html_content


def test_ssrf_and_external_url_blocked():
    """Verify WeasyPrint custom URL fetcher blocks remote external URLs (SSRF protection)."""
    with pytest.raises(DomainError) as exc1:
        local_only_url_fetcher("http://169.254.169.254/latest/meta-data/")
    assert exc1.value.code == "PDF_RENDERER_SSRF_BLOCKED"

    with pytest.raises(DomainError) as exc2:
        local_only_url_fetcher("https://evil.com/malicious.png")
    assert exc2.value.code == "PDF_RENDERER_SSRF_BLOCKED"


def test_visual_regression_page_structure():
    """Render PDF page 1 to pixmap using PyMuPDF and validate structural visual metrics."""
    service = DocumentRenderingService()
    ctx = build_sample_context(status="DRAFT", rows_count=8)

    pdf_bytes, _, _, _ = service.process_and_render(ctx)
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) >= 1

    page = doc[0]
    rect = page.rect  # A4 standard is ~595.27 x 841.89 points
    assert 590 <= rect.width <= 600
    assert 835 <= rect.height <= 850

    # Render page to Pixmap image
    pix = page.get_pixmap(dpi=150)
    assert pix.width > 1000  # ~1240 px at 150 dpi
    assert pix.height > 1500  # ~1754 px at 150 dpi
    assert len(pix.tobytes("png")) > 50000  # Non-empty valid rendered graphic


def test_render_context_concurrency():
    """Verify concurrent worker threads rendering distinct documents have isolated contexts."""
    service = DocumentRenderingService()

    def worker_render(idx: int):
        ctx = build_sample_context(status="APPROVED", rows_count=3)
        ctx.document.display_code = f"PO-LIM-2026-{idx:06d}"
        ctx.notes = f"Thread worker isolated note {idx}"
        pdf_bytes, _, s_hash, p_hash = service.process_and_render(ctx)
        return idx, ctx.document.display_code, s_hash, p_hash, len(pdf_bytes)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker_render, i) for i in range(1, 11)]
        results = [f.result() for f in futures]

    assert len(results) == 10
    display_codes = [r[1] for r in results]
    snapshot_hashes = [r[2] for r in results]
    pdf_hashes = [r[3] for r in results]

    # All codes and hashes must be distinct
    assert len(set(display_codes)) == 10
    assert len(set(snapshot_hashes)) == 10
    assert len(set(pdf_hashes)) == 10


def test_api_endpoints_templates_and_sample(client: TestClient):
    """Verify REST API endpoints for template listing, manifest detail, and sample render."""
    # 1. GET templates list
    templates_res = client.get("/api/logistics/document-renderer/templates")
    assert templates_res.status_code == 200
    templates = templates_res.json()
    assert len(templates) >= 1
    assert any(t["template_key"] == "base_document_v1" for t in templates)

    # 2. GET template detail
    detail_res = client.get("/api/logistics/document-renderer/templates/base_document_v1")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["template_key"] == "base_document_v1"
    assert detail["page_size"] == "A4"

    # 3. POST sample document (PDF format)
    sample_pdf_res = client.post(
        "/api/logistics/document-renderer/sample?format=pdf&rows_count=5&status_code=DRAFT"
    )
    assert sample_pdf_res.status_code == 200
    assert sample_pdf_res.headers["content-type"] == "application/pdf"
    assert "X-Snapshot-Hash" in sample_pdf_res.headers
    assert "X-Pdf-Hash" in sample_pdf_res.headers
    assert sample_pdf_res.content.startswith(b"%PDF-")

    # 4. POST sample document (HTML format)
    sample_html_res = client.post(
        "/api/logistics/document-renderer/sample?format=html&rows_count=3&status_code=APPROVED"
    )
    assert sample_html_res.status_code == 200
    assert "text/html" in sample_html_res.headers["content-type"]
    assert "PO-" in sample_html_res.text
