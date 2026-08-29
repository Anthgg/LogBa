"""Central Document Rendering Service."""

from typing import Optional, Tuple

from app.shared.documents.hashing.service import CanonicalSnapshotService
from app.shared.documents.qr.service import DocumentQRService
from app.shared.documents.renderer.engine import SecureTemplateEngine
from app.shared.documents.renderer.pdf import WeasyPrintPdfRenderer
from app.shared.documents.schemas.context import DocumentRenderContext
from app.shared.documents.templates.registry import TemplateRegistry


class DocumentRenderingService:
    """Central domain service coordinating context validation, snapshotting, and PDF generation."""

    def __init__(self) -> None:
        self.html_engine = SecureTemplateEngine()
        self.pdf_engine = WeasyPrintPdfRenderer()

    def process_and_render(
        self,
        context: DocumentRenderContext,
        template_key: Optional[str] = None,
    ) -> Tuple[bytes, str, str, str]:
        """
        Executes canonical pipeline:
        1. Resolves template manifest.
        2. Computes deterministic SNAPSHOT_HASH from canonical JSON.
        3. Generates QR code containing snapshot hash and metadata.
        4. Injects watermark if status is DRAFT or VOID.
        5. Renders HTML via Jinja2 autoescape.
        6. Compiles PDF via WeasyPrint.
        7. Computes PDF_HASH from final bytes.

        Returns: (pdf_bytes, html_content, snapshot_hash, pdf_hash)
        """
        key = template_key or context.metadata.template_key
        manifest = TemplateRegistry.get_manifest(key)

        ctx_dict = context.model_dump()
        ctx_dict["metadata"]["template_key"] = manifest.template_key
        ctx_dict["metadata"]["template_version"] = manifest.version
        ctx_dict["metadata"]["renderer_name"] = manifest.supported_renderer

        # 1. Deterministic SNAPSHOT_HASH
        snapshot_hash = CanonicalSnapshotService.compute_snapshot_hash(ctx_dict)
        ctx_dict["snapshot_hash"] = snapshot_hash

        # 2. QR Data URI
        qr_payload = {
            "document_type": ctx_dict["document"]["type_code"],
            "display_code": ctx_dict["document"]["display_code"],
            "version": ctx_dict["document"]["version_number"],
            "snapshot_hash": snapshot_hash,
            "generated_at": ctx_dict["metadata"]["generated_at"],
        }
        ctx_dict["qr_data_uri"] = DocumentQRService.generate_qr_data_uri(qr_payload)

        # 3. Watermark logic
        doc_status = ctx_dict["document"]["status"].upper()
        if doc_status == "DRAFT" and not ctx_dict.get("watermark_text"):
            ctx_dict["watermark_text"] = "BORRADOR"
        elif doc_status == "VOID" and not ctx_dict.get("watermark_text"):
            ctx_dict["watermark_text"] = "ANULADO"

        # 4. Render HTML
        html_content = self.html_engine.render_html(key, ctx_dict)

        # 5. Render PDF
        pdf_bytes = self.pdf_engine.render_pdf(
            html_content=html_content,
            title=ctx_dict["document"]["display_code"],
        )

        # 6. PDF_HASH
        pdf_hash = CanonicalSnapshotService.compute_pdf_hash(pdf_bytes)

        return pdf_bytes, html_content, snapshot_hash, pdf_hash
