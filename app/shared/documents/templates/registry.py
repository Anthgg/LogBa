"""Template Registry with Family Separation and Security Controls."""

from typing import Dict, List, Optional

from app.core.errors import DomainError
from app.shared.documents.schemas.manifest import TemplateManifest


class TemplateRegistry:
    """Internal registry mapping immutable template keys to verified templates and manifests."""

    _manifests: Dict[str, TemplateManifest] = {
        # Base Universal Template (F014)
        "base_document_v1": TemplateManifest(
            template_key="base_document_v1",
            family="base",
            version="1.0.0",
            title="Plantilla Canónica Base A4",
            description=(
                "Plantilla universal base con encabezado institucional, metadata, "
                "tablas paginadas, notas, QR, firma visual y pie de página con paginación."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["DRAFT", "APPROVED", "ISSUED", "VOID"],
            created_at="2026-08-29T00:00:00Z",
        ),
        # 1. Requerimiento de Compra (REQ) - F015
        "purchase_requisition_v1": TemplateManifest(
            template_key="purchase_requisition_v1",
            family="purchasing",
            version="1.0.0",
            title="Requerimiento de Compra",
            description=(
                "Requerimiento interno de compra con solicitante, "
                "centro de costo, justificación y líneas."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["DRAFT", "PENDING", "APPROVED", "REJECTED", "COMPLETED", "VOID"],
            created_at="2026-08-29T00:00:00Z",
        ),
        # 2. Solicitud de Cotización (RFQ) - F015
        "request_for_quotation_v1": TemplateManifest(
            template_key="request_for_quotation_v1",
            family="purchasing",
            version="1.0.0",
            title="Solicitud de Cotización (RFQ)",
            description=(
                "Solicitud formal de cotización enviada a proveedores "
                "con especificaciones y fecha límite."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["DRAFT", "ISSUED", "CLOSED", "VOID"],
            created_at="2026-08-29T00:00:00Z",
        ),
        # 3. Cuadro Comparativo de Ofertas (CMP) - F015 (Landscape)
        "comparative_table_v1": TemplateManifest(
            template_key="comparative_table_v1",
            family="purchasing",
            version="1.0.0",
            title="Cuadro Comparativo de Ofertas",
            description=(
                "Matriz comparativa horizontal de cotizaciones de "
                "múltiples proveedores con precios y plazos."
            ),
            page_size="A4",
            orientation="landscape",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["DRAFT", "PENDING", "APPROVED", "VOID"],
            created_at="2026-08-29T00:00:00Z",
        ),
        # 4. Orden de Compra Oficial (PO) - F015
        "purchase_order_v1": TemplateManifest(
            template_key="purchase_order_v1",
            family="purchasing",
            version="1.0.0",
            title="Orden de Compra Oficial",
            description=(
                "Orden de compra oficial con desglose de impuestos, entregas parciales y cláusulas."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["DRAFT", "PENDING", "APPROVED", "ISSUED", "COMPLETED", "VOID"],
            created_at="2026-08-29T00:00:00Z",
        ),
        # 5. Aprobación de Compra (POA) - F015
        "purchase_approval_v1": TemplateManifest(
            template_key="purchase_approval_v1",
            family="purchasing",
            version="1.0.0",
            title="Acta / Aprobación de Compra",
            description=(
                "Acta de decisión de aprobación o rechazo de compra por niveles y sustento."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["PENDING", "APPROVED", "REJECTED"],
            created_at="2026-08-29T00:00:00Z",
        ),
        # 6. Constancia de Envío al Proveedor (PSC) - F015
        "supplier_send_confirmation_v1": TemplateManifest(
            template_key="supplier_send_confirmation_v1",
            family="purchasing",
            version="1.0.0",
            title="Constancia de Envío al Proveedor",
            description=(
                "Constancia técnica de notificación/despacho de orden de compra al proveedor."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["REGISTERED", "PROCESSED", "VOID"],
            created_at="2026-08-29T00:00:00Z",
        ),
    }

    _template_files: Dict[str, str] = {
        "base_document_v1": "base/base_document_v1.html",
        "purchase_requisition_v1": "purchasing/purchase_requisition_v1.html",
        "requisition_v1": "purchasing/purchase_requisition_v1.html",
        "request_for_quotation_v1": "purchasing/request_for_quotation_v1.html",
        "rfq_v1": "purchasing/request_for_quotation_v1.html",
        "comparative_table_v1": "purchasing/comparative_table_v1.html",
        "purchase_order_v1": "purchasing/purchase_order_v1.html",
        "purchase_order_v9": "purchasing/purchase_order_v1.html",
        "purchase_approval_v1": "purchasing/purchase_approval_v1.html",
        "supplier_send_confirmation_v1": "purchasing/supplier_send_confirmation_v1.html",
        "psc_v1": "purchasing/supplier_send_confirmation_v1.html",
    }

    @classmethod
    def list_templates(cls, family: Optional[str] = None) -> List[TemplateManifest]:
        """Returns all registered template manifests, optionally filtered by family."""
        if family:
            fam_clean = family.lower().strip()
            return [m for m in cls._manifests.values() if m.family.lower() == fam_clean]
        return list(cls._manifests.values())

    @classmethod
    def get_manifest(cls, template_key: str) -> TemplateManifest:
        """Retrieves manifest for a registered template key."""
        resolved_key = template_key
        if template_key == "requisition_v1":
            resolved_key = "purchase_requisition_v1"
        elif template_key == "rfq_v1":
            resolved_key = "request_for_quotation_v1"
        elif template_key == "purchase_order_v9":
            resolved_key = "purchase_order_v1"
        elif template_key == "psc_v1":
            resolved_key = "supplier_send_confirmation_v1"

        if resolved_key not in cls._manifests:
            raise DomainError(
                code="TEMPLATE_NOT_FOUND",
                message=f"La plantilla documental '{template_key}' no se encuentra registrada.",
            )
        return cls._manifests[resolved_key]

    @classmethod
    def resolve_template_path(cls, template_key: str) -> str:
        """Resolves relative template file path safely against registry. Prevents path traversal."""
        if ".." in template_key or "/" in template_key or "\\" in template_key:
            raise DomainError(
                code="TEMPLATE_PATH_TRAVERSAL_DETECTED",
                message="Identificador de plantilla inválido o intento de path traversal.",
            )
        if template_key not in cls._template_files:
            raise DomainError(
                code="TEMPLATE_NOT_FOUND",
                message=f"La plantilla documental '{template_key}' no está disponible.",
            )
        return cls._template_files[template_key]
