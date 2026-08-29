"""Automated Tests for Inbound Receiving Document Package (F016).

Tests schemas, Jinja2 rendering, WeasyPrint compilation, QR decoding,
SHA-256 dual-stage hashing, multipage pagination, security autoescape,
concurrency isolation, and FastAPI REST endpoints for the 6 inbound receiving types.
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

from app.core.errors import DomainError
from app.main import app
from app.modules.auth.csrf import generate_csrf_token
from app.modules.documents.router import build_receiving_sample_context
from app.scripts import seed_demo
from app.shared.documents.schemas.context import (
    BranchHeaderContext,
    DocumentHeaderContext,
    DocumentMetadataContext,
    DocumentRenderContext,
    OrganizationHeaderContext,
)
from app.shared.documents.service import DocumentRenderingService
from app.shared.documents.templates.registry import TemplateRegistry


@pytest.fixture(scope="module")
def client() -> TestClient:
    seed_demo.run_seed()
    c = TestClient(app)
    csrf = generate_csrf_token()
    login_res = c.post(
        "/api/auth/login",
        json={"email": "gerencia.demo@logistica.local", "password": "jesusanthony01"},
        headers={"X-CSRF-Token": csrf},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    return c


def test_receiving_templates_registered_in_registry():
    """Verify that all 6 inbound receiving templates are registered with correct metadata."""
    templates = TemplateRegistry.list_templates(family="receiving")
    assert len(templates) == 6, f"Expected 6 receiving templates, found {len(templates)}"

    keys = {t.template_key for t in templates}
    expected_keys = {
        "arrival_appointment_v1",
        "gate_control_v1",
        "receiving_report_v1",
        "goods_receipt_v1",
        "receiving_difference_v1",
        "non_conformity_v1",
    }
    assert keys == expected_keys

    for t in templates:
        assert t.family == "receiving"
        assert t.page_size == "A4"
        assert t.orientation == "portrait"
        assert t.supported_renderer == "WeasyPrint"
        assert len(t.supported_statuses) > 0


def test_alias_resolution_receiving():
    """Verify alias mapping for receiving templates."""
    m1 = TemplateRegistry.get_manifest("receiving_diff_v1")
    assert m1.template_key == "receiving_difference_v1"

    path1 = TemplateRegistry.resolve_template_path("receiving_diff_v1")
    assert path1 == "receiving/receiving_difference_v1.html"


def test_render_all_six_receiving_documents_pdf():
    """Verify that all 6 receiving documents compile to valid PDF with dual-stage hashes."""
    service = DocumentRenderingService()
    doc_specs = [
        ("ARR", "arrival_appointment_v1", "SCHEDULED"),
        ("CPV", "gate_control_v1", "INSIDE"),
        ("REC", "receiving_report_v1", "COMPLETED"),
        ("GRN", "goods_receipt_v1", "ISSUED"),
        ("RDIFF", "receiving_difference_v1", "OPEN"),
        ("NC", "non_conformity_v1", "ISSUED"),
    ]

    for code, expected_key, status in doc_specs:
        ctx, tpl_key = build_receiving_sample_context(
            doc_code=code,
            scenario="basic",
            status_code=status,
            org_name="Corporación Minera & Logística del Sur S.A.C.",
            tax_id="20556677889",
            branch_name="Sede Callao Operaciones",
            branch_code="CAL",
            branch_address="Av. Néstor Gambetta 1200, Callao",
            user_email="auditor.inbound@logistica.local",
        )
        assert tpl_key == expected_key

        pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(
            context=ctx,
            template_key=tpl_key,
        )

        assert pdf_bytes.startswith(b"%PDF-1.")
        assert len(pdf_bytes) > 2000
        assert len(snapshot_hash) == 64
        assert len(pdf_hash) == 64
        assert snapshot_hash != pdf_hash
        assert f"PREVIEW-{code}-CAL-2026-0001" in html_content
        assert "VISTA PREVIA" in html_content


def test_qr_code_decoding_all_receiving_documents():
    """Extract and decode QR code from HTML output for each receiving document."""
    service = DocumentRenderingService()
    codes = ["ARR", "CPV", "REC", "GRN", "RDIFF", "NC"]

    for code in codes:
        ctx, tpl_key = build_receiving_sample_context(
            doc_code=code,
            scenario="basic",
            status_code=None,
            org_name="Organización Logística",
            tax_id="20100012345",
            branch_name="Sede Lima",
            branch_code="LIM",
            branch_address="Av. Central 100",
            user_email="test@logistica.local",
        )

        _, html_content, snapshot_hash, _ = service.process_and_render(
            context=ctx,
            template_key=tpl_key,
        )

        m = re.search(r'src="(data:image/png;base64,[^"]+)"', html_content)
        assert m is not None, f"QR image data URI missing in {code} HTML"

        img_b64 = m.group(1).split(",")[1]
        pil_img = Image.open(io.BytesIO(base64.b64decode(img_b64))).convert("RGB")
        decoded = zxingcpp.read_barcode(pil_img)
        assert decoded is not None, f"Could not decode QR barcode for {code}"

        payload = json.loads(decoded.text)
        assert payload["document_type"] == code
        assert payload["display_code"] == ctx.document.display_code
        assert payload["snapshot_hash"] == snapshot_hash


def test_multipage_receiving_pagination():
    """Verify that 50-item receiving documents generate multiple pages without overflow."""
    service = DocumentRenderingService()
    codes = ["ARR", "REC", "GRN", "RDIFF"]

    for code in codes:
        ctx, tpl_key = build_receiving_sample_context(
            doc_code=code,
            scenario="multipage",
            status_code=None,
            org_name="Logística Integral del Perú",
            tax_id="20100012345",
            branch_name="Sede Lima",
            branch_code="LIM",
            branch_address="Av. Central 100",
            user_email="test@logistica.local",
        )

        pdf_bytes, _, _, _ = service.process_and_render(context=ctx, template_key=tpl_key)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) >= 2, (
            f"Expected multiple pages for {code} multipage scenario, got {len(reader.pages)}"
        )


def test_security_autoescape_and_path_traversal():
    """Verify that Jinja2 autoescaping neutralizes XSS and registry blocks path traversal."""
    service = DocumentRenderingService()
    malicious_text = "<script>alert('XSS_INJECTION')</script><b>Injected Bold</b>"

    ctx = DocumentRenderContext(
        organization=OrganizationHeaderContext(name=malicious_text, tax_id="20100012345"),
        branch=BranchHeaderContext(name="Sede Lima", code="LIM"),
        document=DocumentHeaderContext(
            type_code="REC",
            type_name="Acta de Recepción Técnica",
            display_code="REC-LIM-2026-0001",
            status="DRAFT",
        ),
        metadata=DocumentMetadataContext(template_key="receiving_report_v1"),
        notes=malicious_text,
    )

    pdf_bytes, html_content, _, _ = service.process_and_render(
        context=ctx,
        template_key="receiving_report_v1",
    )
    assert "<script>alert" not in html_content
    assert "&lt;script&gt;alert(&#39;XSS_INJECTION&#39;)&lt;/script&gt;" in html_content

    with pytest.raises(DomainError) as exc:
        TemplateRegistry.resolve_template_path("../../etc/passwd")
    assert exc.value.code == "TEMPLATE_PATH_TRAVERSAL_DETECTED"


def test_concurrency_isolation_receiving():
    """Verify thread-safe rendering under concurrent workload."""
    service = DocumentRenderingService()
    codes = ["ARR", "CPV", "REC", "GRN", "RDIFF", "NC"] * 2

    def _render_task(i: int, code: str):
        ctx, tpl_key = build_receiving_sample_context(
            doc_code=code,
            scenario="basic",
            status_code=None,
            org_name=f"Org Concurrency #{i}",
            tax_id=f"201000{i:05d}",
            branch_name=f"Sede #{i}",
            branch_code=f"S{i:02d}",
            branch_address="Av. Industrial 123",
            user_email=f"user_{i}@logistica.local",
        )
        pdf_bytes, html_content, s_hash, p_hash = service.process_and_render(
            context=ctx,
            template_key=tpl_key,
        )
        assert f"PREVIEW-{code}-S{i:02d}-2026-0001" in html_content
        return code, s_hash, p_hash, len(pdf_bytes)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_render_task, idx, c) for idx, c in enumerate(codes)]
        results = [f.result() for f in futures]

    assert len(results) == 12
    s_hashes = [r[1] for r in results]
    assert len(set(s_hashes)) == 12, "Snapshot hashes should all be uniquely distinct"


def test_fastapi_sample_endpoint_receiving(client: TestClient):
    """Verify REST API endpoint for receiving sample documents."""
    codes = ["ARR", "CPV", "REC", "GRN", "RDIFF", "NC"]

    for code in codes:
        res = client.post(
            f"/api/logistics/document-renderer/receiving/{code}/sample?scenario=basic&format=pdf"
        )
        assert res.status_code == 200, f"Endpoint failed for {code}: {res.text}"
        assert res.headers["x-document-type"] == code
        assert "X-Snapshot-Hash" in res.headers
        assert "X-Pdf-Hash" in res.headers
        assert res.headers["x-renderer-name"] == "WeasyPrint"
        assert res.content.startswith(b"%PDF-1.")

        html_res = client.post(
            f"/api/logistics/document-renderer/receiving/{code}/sample?scenario=basic&format=html"
        )
        assert html_res.status_code == 200
        assert f"PREVIEW-{code}-" in html_res.text

    # Invalid code check
    bad_res = client.post("/api/logistics/document-renderer/receiving/INVALID_CODE/sample")
    assert bad_res.status_code == 400
    assert "Código documental de ingreso/recepción no soportado" in bad_res.text
