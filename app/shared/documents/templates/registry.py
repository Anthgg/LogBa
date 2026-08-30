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
        # -------------------------------------------------------------------
        # Purchasing Package (F015)
        # -------------------------------------------------------------------
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
        # -------------------------------------------------------------------
        # Inbound Receiving Package (F016)
        # -------------------------------------------------------------------
        "arrival_appointment_v1": TemplateManifest(
            template_key="arrival_appointment_v1",
            family="receiving",
            version="1.0.0",
            title="Cita de Llegada / Arribo",
            description=(
                "Cita programada de llegada de transporte con ventana horaria, "
                "placa, conductor y carga estimada."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["SCHEDULED", "CHECKED_IN", "UNLOADED", "CANCELLED"],
            created_at="2026-08-29T00:00:00Z",
        ),
        "gate_control_v1": TemplateManifest(
            template_key="gate_control_v1",
            family="receiving",
            version="1.0.0",
            title="Control de Puerta Vehicular",
            description=(
                "Registro de control de garita vehicular con horas de entrada/salida, "
                "precintos y documentos."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["INSIDE", "EXITED", "CANCELLED"],
            created_at="2026-08-29T00:00:00Z",
        ),
        "receiving_report_v1": TemplateManifest(
            template_key="receiving_report_v1",
            family="receiving",
            version="1.0.0",
            title="Acta de Recepción Técnica",
            description=(
                "Acta de inspección y recepción técnica en muelle con comparación "
                "ordenada vs recibida y lotes."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["DRAFT", "COMPLETED", "VOID"],
            created_at="2026-08-29T00:00:00Z",
        ),
        "goods_receipt_v1": TemplateManifest(
            template_key="goods_receipt_v1",
            family="receiving",
            version="1.0.0",
            title="Guía de Ingreso a Almacén",
            description=(
                "Nota oficial de ingreso de mercancías a almacén con cantidades aceptadas "
                "y estado de calidad."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["DRAFT", "ISSUED", "CANCELLED"],
            created_at="2026-08-29T00:00:00Z",
        ),
        "receiving_difference_v1": TemplateManifest(
            template_key="receiving_difference_v1",
            family="receiving",
            version="1.0.0",
            title="Acta de Diferencias de Recepción",
            description=(
                "Constancia de discrepancias en descarga: faltantes, sobrantes, "
                "daños o precintos rotos."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["OPEN", "RESOLVED", "VOID"],
            created_at="2026-08-29T00:00:00Z",
        ),
        "non_conformity_v1": TemplateManifest(
            template_key="non_conformity_v1",
            family="receiving",
            version="1.0.0",
            title="Reporte de No Conformidad",
            description=(
                "Reporte formal de no conformidad con hallazgos, severidad, "
                "evidencias y propuesta de disposición."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["ISSUED", "ACCEPTED_BY_SUPPLIER", "CLOSED"],
            created_at="2026-08-29T00:00:00Z",
        ),
        # Inventory (F017)
        "location_label_v1": TemplateManifest(
            template_key="location_label_v1",
            family="inventory",
            version="1.0.0",
            title="Etiqueta de Ubicación / Pallet",
            description="Identificador físico de posición de estante, pallet o lote en almacén.",
            page_size="100x150mm",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["ACTIVE", "OBSOLETE"],
            created_at="2026-08-29T00:00:00Z",
        ),
        "inventory_movement_v1": TemplateManifest(
            template_key="inventory_movement_v1",
            family="inventory",
            version="1.0.0",
            title="Movimiento Interno de Inventario",
            description="Reubicación física de existencias entre posiciones de un mismo almacén.",
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["EXECUTED", "CANCELLED"],
            created_at="2026-08-29T00:00:00Z",
        ),
        "inventory_adjustment_v1": TemplateManifest(
            template_key="inventory_adjustment_v1",
            family="inventory",
            version="1.0.0",
            title="Ajuste de Inventario",
            description=(
                "Acta de modificación controlada de stock por merma, desmedro o regularización."
            ),
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["DRAFT", "PENDING_APPROVAL", "APPROVED", "REJECTED"],
            created_at="2026-08-29T00:00:00Z",
        ),
        "physical_count_v1": TemplateManifest(
            template_key="physical_count_v1",
            family="inventory",
            version="1.0.0",
            title="Conteo Físico / Inventario Cíclico",
            description="Planilla de toma física con soporte de conteo ciego (Blind Count).",
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["IN_PROGRESS", "FINALIZED", "CANCELLED"],
            created_at="2026-08-29T00:00:00Z",
        ),
        "count_difference_v1": TemplateManifest(
            template_key="count_difference_v1",
            family="inventory",
            version="1.0.0",
            title="Diferencia de Conteo Físico",
            description="Balance comparativo entre stock teórico del sistema y conteo físico real.",
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["DRAFT", "RECONCILED", "APPROVED"],
            created_at="2026-08-29T00:00:00Z",
        ),
        "warehouse_transfer_v1": TemplateManifest(
            template_key="warehouse_transfer_v1",
            family="inventory",
            version="1.0.0",
            title="Solicitud de Transferencia entre Almacenes",
            description="Orden de traspaso de existencias entre dos almacenes de la organización.",
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["DRAFT", "REQUESTED", "IN_TRANSIT", "COMPLETED", "CANCELLED"],
            created_at="2026-08-29T00:00:00Z",
        ),
        "transfer_receipt_v1": TemplateManifest(
            template_key="transfer_receipt_v1",
            family="inventory",
            version="1.0.0",
            title="Recepción de Transferencia",
            description="Acta de conformidad y verificación de llegada de mercadería transferida.",
            page_size="A4",
            orientation="portrait",
            supported_renderer="WeasyPrint",
            required_context_fields=["organization", "branch", "document", "metadata"],
            supported_statuses=["RECEIVED", "DISCREPANCY_FOUND", "CLOSED"],
            created_at="2026-08-29T00:00:00Z",
        ),
    }

    _template_files: Dict[str, str] = {
        # Base
        "base_document_v1": "base/base_document_v1.html",
        # Purchasing
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
        # Receiving
        "arrival_appointment_v1": "receiving/arrival_appointment_v1.html",
        "gate_control_v1": "receiving/gate_control_v1.html",
        "receiving_report_v1": "receiving/receiving_report_v1.html",
        "goods_receipt_v1": "receiving/goods_receipt_v1.html",
        "receiving_difference_v1": "receiving/receiving_difference_v1.html",
        "receiving_diff_v1": "receiving/receiving_difference_v1.html",
        "non_conformity_v1": "receiving/non_conformity_v1.html",
        # Inventory
        "location_label_v1": "inventory/location_label_v1.html",
        "inventory_movement_v1": "inventory/inventory_movement_v1.html",
        "inventory_adjustment_v1": "inventory/inventory_adjustment_v1.html",
        "physical_count_v1": "inventory/physical_count_v1.html",
        "stock_count_v1": "inventory/physical_count_v1.html",
        "count_difference_v1": "inventory/count_difference_v1.html",
        "warehouse_transfer_v1": "inventory/warehouse_transfer_v1.html",
        "transfer_request_v1": "inventory/warehouse_transfer_v1.html",
        "transfer_receipt_v1": "inventory/transfer_receipt_v1.html",
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
        elif template_key == "receiving_diff_v1":
            resolved_key = "receiving_difference_v1"
        elif template_key == "stock_count_v1":
            resolved_key = "physical_count_v1"
        elif template_key == "transfer_request_v1":
            resolved_key = "warehouse_transfer_v1"

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
