import uuid
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.rbac import AuthenticatedPrincipal
from app.db.connection import get_db
from app.modules.auth.dependencies import (
    get_audit_context,
    get_current_principal,
    require_permission,
    validate_csrf,
)
from app.modules.documents.models import DocumentType
from app.modules.documents.numbering_standard import (
    DocumentNumberingPreviewRequest,
    DocumentNumberingPreviewResponse,
    DocumentNumberingService,
    NumberingStandardSpecResponse,
    format_canonical_document_code,
)
from app.modules.documents.schemas import (
    DocumentFamilyCreate,
    DocumentFamilyResponse,
    DocumentRetentionPolicyCreate,
    DocumentRetentionPolicyResponse,
    DocumentTypeCreate,
    DocumentTypeDetailResponse,
    DocumentTypeResponse,
    DocumentTypeUpdate,
    DocumentTypeVersionCreate,
    DocumentTypeVersionResponse,
)
from app.modules.documents.series_schemas import (
    DocumentSeriesCreate,
    DocumentSeriesDetailResponse,
    DocumentSeriesNumberResponse,
    DocumentSeriesReservationCreate,
    DocumentSeriesReservationResponse,
    DocumentSeriesResponse,
    VoidDocumentNumberRequest,
)
from app.modules.documents.series_service import DocumentSeriesService
from app.modules.documents.service import DocumentCatalogService
from app.shared.audit.contracts import AuditContext
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
from app.shared.documents.schemas.manifest import TemplateManifest
from app.shared.documents.service import DocumentRenderingService
from app.shared.documents.templates.registry import TemplateRegistry

router = APIRouter()


def _map_doc_type_response(dt: DocumentType) -> DocumentTypeResponse:
    current_v = next((v for v in dt.versions if v.is_current), None)
    return DocumentTypeResponse(
        id=dt.id,
        code=dt.code,
        name=dt.name,
        description=dt.description,
        family_id=dt.family_id,
        family_name=dt.family.name if dt.family else None,
        document_scope=dt.document_scope,  # type: ignore
        is_active=dt.is_active,
        phase_owner=dt.phase_owner,
        current_version_number=current_v.version_number if current_v else None,
        current_template_key=current_v.template_key if current_v else None,
        retention_policy_name=current_v.retention_policy.name
        if current_v and current_v.retention_policy
        else None,
        created_at=dt.created_at,
        updated_at=dt.updated_at,
    )


def _map_doc_type_detail_response(dt: DocumentType) -> DocumentTypeDetailResponse:
    current_v = next((v for v in dt.versions if v.is_current), None)
    return DocumentTypeDetailResponse(
        id=dt.id,
        code=dt.code,
        name=dt.name,
        description=dt.description,
        family_id=dt.family_id,
        family_name=dt.family.name if dt.family else None,
        document_scope=dt.document_scope,  # type: ignore
        is_active=dt.is_active,
        phase_owner=dt.phase_owner,
        current_version_number=current_v.version_number if current_v else None,
        current_template_key=current_v.template_key if current_v else None,
        retention_policy_name=current_v.retention_policy.name
        if current_v and current_v.retention_policy
        else None,
        created_at=dt.created_at,
        updated_at=dt.updated_at,
        current_version=DocumentTypeVersionResponse.model_validate(current_v)
        if current_v
        else None,
        versions=[DocumentTypeVersionResponse.model_validate(v) for v in dt.versions],
    )


# --- Document Families ---
@router.get(
    "/document-families",
    response_model=List[DocumentFamilyResponse],
    summary="List all canonical document families",
    dependencies=[Depends(require_permission("document_catalog.read"))],
)
def get_document_families(
    active_only: bool = Query(False, description="Filter only active families"),
    db: Session = Depends(get_db),
) -> List[DocumentFamilyResponse]:
    families = DocumentCatalogService.get_families(db, active_only=active_only)
    return [DocumentFamilyResponse.model_validate(f) for f in families]


@router.post(
    "/document-families",
    response_model=DocumentFamilyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new document family",
    dependencies=[Depends(require_permission("document_catalog.manage")), Depends(validate_csrf)],
)
def create_document_family(
    data: DocumentFamilyCreate,
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> DocumentFamilyResponse:
    try:
        family = DocumentCatalogService.create_family(
            db,
            payload=data,
            context=audit_ctx,
        )
        return DocumentFamilyResponse.model_validate(family)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Document Retention Policies ---
@router.get(
    "/document-retention-policies",
    response_model=List[DocumentRetentionPolicyResponse],
    summary="List all document retention policies",
    dependencies=[Depends(require_permission("document_catalog.read"))],
)
def get_retention_policies(
    active_only: bool = Query(False, description="Filter only active policies"),
    db: Session = Depends(get_db),
) -> List[DocumentRetentionPolicyResponse]:
    policies = DocumentCatalogService.get_retention_policies(db, active_only=active_only)
    return [DocumentRetentionPolicyResponse.model_validate(p) for p in policies]


@router.post(
    "/document-retention-policies",
    response_model=DocumentRetentionPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new retention policy",
    dependencies=[Depends(require_permission("document_catalog.manage")), Depends(validate_csrf)],
)
def create_retention_policy(
    data: DocumentRetentionPolicyCreate,
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> DocumentRetentionPolicyResponse:
    try:
        policy = DocumentCatalogService.create_retention_policy(
            db,
            payload=data,
            context=audit_ctx,
        )
        return DocumentRetentionPolicyResponse.model_validate(policy)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Document Types ---
@router.get(
    "/document-types",
    response_model=List[DocumentTypeResponse],
    summary="List all document types with family and current version details",
    dependencies=[Depends(require_permission("document_catalog.read"))],
)
def get_document_types(
    family_id: Optional[uuid.UUID] = Query(None, description="Filter by family ID"),
    scope: Optional[str] = Query(None, description="Filter by scope: INTERNAL or EXTERNAL"),
    active_only: bool = Query(False, description="Filter only active document types"),
    db: Session = Depends(get_db),
) -> List[DocumentTypeResponse]:
    types = DocumentCatalogService.get_document_types(
        db, family_id=family_id, scope=scope, active_only=active_only
    )
    return [_map_doc_type_response(t) for t in types]


@router.post(
    "/document-types",
    response_model=DocumentTypeDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new document type specification",
    dependencies=[Depends(require_permission("document_catalog.manage")), Depends(validate_csrf)],
)
def create_document_type(
    data: DocumentTypeCreate,
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> DocumentTypeDetailResponse:
    try:
        doc_type = DocumentCatalogService.create_document_type(
            db,
            payload=data,
            context=audit_ctx,
        )
        return _map_doc_type_detail_response(doc_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/document-types/{id}",
    response_model=DocumentTypeDetailResponse,
    summary="Get document type detail with complete version history",
    dependencies=[Depends(require_permission("document_catalog.read"))],
)
def get_document_type_detail(
    id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DocumentTypeDetailResponse:
    doc_type = DocumentCatalogService.get_document_type_by_id(db, id)
    if not doc_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tipo documental no encontrado"
        )
    return _map_doc_type_detail_response(doc_type)


@router.patch(
    "/document-types/{id}",
    response_model=DocumentTypeDetailResponse,
    summary="Update document type metadata (name, description, active status)",
    dependencies=[Depends(require_permission("document_catalog.manage")), Depends(validate_csrf)],
)
def update_document_type(
    id: uuid.UUID,
    data: DocumentTypeUpdate,
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> DocumentTypeDetailResponse:
    try:
        doc_type = DocumentCatalogService.update_document_type(
            db,
            type_id=id,
            payload=data,
            context=audit_ctx,
        )
        return _map_doc_type_detail_response(doc_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Document Type Versions ---
@router.get(
    "/document-types/{id}/versions",
    response_model=List[DocumentTypeVersionResponse],
    summary="List all versions of a document type in reverse chronological order",
    dependencies=[Depends(require_permission("document_catalog.read"))],
)
def get_document_type_versions(
    id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[DocumentTypeVersionResponse]:
    doc_type = DocumentCatalogService.get_document_type_by_id(db, id)
    if not doc_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tipo documental no encontrado"
        )
    versions = DocumentCatalogService.get_versions(db, id)
    return [DocumentTypeVersionResponse.model_validate(v) for v in versions]


@router.post(
    "/document-types/{id}/versions",
    response_model=DocumentTypeVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a new immutable version for a document type",
    dependencies=[Depends(require_permission("document_catalog.manage")), Depends(validate_csrf)],
)
def create_document_type_version(
    id: uuid.UUID,
    data: DocumentTypeVersionCreate,
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> DocumentTypeVersionResponse:
    try:
        version = DocumentCatalogService.create_new_version(
            db,
            type_id=id,
            payload=data,
            context=audit_ctx,
        )
        return DocumentTypeVersionResponse.model_validate(version)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/document-types/{id}/versions/{version_number}",
    response_model=DocumentTypeVersionResponse,
    summary="Get specific historical version snapshot",
    dependencies=[Depends(require_permission("document_catalog.read"))],
)
def get_document_type_version_by_number(
    id: uuid.UUID,
    version_number: int,
    db: Session = Depends(get_db),
) -> DocumentTypeVersionResponse:
    version = DocumentCatalogService.get_version_by_number(db, id, version_number)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Versión {version_number} no encontrada para este tipo documental",
        )
    return DocumentTypeVersionResponse.model_validate(version)


# --- Document Numbering Standard & Preview (F012) ---
@router.get(
    "/document-numbering/standard",
    response_model=NumberingStandardSpecResponse,
    summary="Get canonical document numbering standard specification (TIPO-SEDE-AÑO-CORRELATIVO)",
    dependencies=[Depends(require_permission("document_catalog.read"))],
)
def get_document_numbering_standard() -> NumberingStandardSpecResponse:
    return DocumentNumberingService.get_standard_spec()


@router.post(
    "/document-numbering/preview",
    response_model=DocumentNumberingPreviewResponse,
    summary="Generate non-allocating preview of canonical document code",
    dependencies=[Depends(require_permission("document_catalog.read")), Depends(validate_csrf)],
)
def preview_document_numbering(
    data: DocumentNumberingPreviewRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> DocumentNumberingPreviewResponse:
    return DocumentNumberingService.preview_numbering(
        db=db,
        principal=principal,
        payload=data,
    )


# --- Document Series & Concurrent Reservations (F013) ---
@router.get(
    "/document-series",
    response_model=List[DocumentSeriesResponse],
    summary="List document series with realtime reservation and void counters",
    dependencies=[Depends(require_permission("document_series.read"))],
)
def list_document_series(
    document_type_id: Optional[uuid.UUID] = Query(None, description="Filter by document type"),
    branch_id: Optional[uuid.UUID] = Query(None, description="Filter by branch"),
    period_year: Optional[int] = Query(None, description="Filter by period year"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> List[DocumentSeriesResponse]:
    return DocumentSeriesService.get_series_list(
        db=db,
        principal=principal,
        document_type_id=document_type_id,
        branch_id=branch_id,
        period_year=period_year,
        is_active=is_active,
    )


@router.post(
    "/document-series",
    response_model=DocumentSeriesResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new digital document series",
    dependencies=[Depends(require_permission("document_series.create")), Depends(validate_csrf)],
)
def create_document_series(
    data: DocumentSeriesCreate,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> DocumentSeriesResponse:
    series = DocumentSeriesService.create_series(
        db=db,
        payload=data,
        principal=principal,
        context=audit_ctx,
    )
    return DocumentSeriesService._map_series_response(series, db)


@router.get(
    "/document-series/{id}",
    response_model=DocumentSeriesDetailResponse,
    summary="Get document series details with reservation history",
    dependencies=[Depends(require_permission("document_series.read"))],
)
def get_document_series_detail(
    id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> DocumentSeriesDetailResponse:
    series = DocumentSeriesService.get_series_by_id(db=db, series_id=id, principal=principal)
    base_res = DocumentSeriesService._map_series_response(series, db)
    reservations_res = [
        DocumentSeriesReservationResponse(
            id=r.id,
            series_id=r.series_id,
            start_correlative=r.start_correlative,
            end_correlative=r.end_correlative,
            quantity=r.quantity,
            first_display_code=format_canonical_document_code(
                series.document_type.code,
                series.branch.code,
                series.period_year,
                r.start_correlative,
                series.correlative_width,
            ),
            last_display_code=format_canonical_document_code(
                series.document_type.code,
                series.branch.code,
                series.period_year,
                r.end_correlative,
                series.correlative_width,
            ),
            reserved_by_user_id=r.reserved_by_user_id,
            reserved_by_name=r.user.display_name if r.user else None,
            reserved_at=r.reserved_at,
            reason=r.reason,
            correlation_id=r.correlation_id,
        )
        for r in series.reservations
    ]
    return DocumentSeriesDetailResponse(
        **base_res.model_dump(),
        reservations=reservations_res,
    )


@router.post(
    "/document-series/{id}/reservations",
    response_model=DocumentSeriesReservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reserve a concurrent block/range of correlatives for a document series",
    dependencies=[Depends(require_permission("document_series.reserve")), Depends(validate_csrf)],
)
def reserve_document_correlatives(
    id: uuid.UUID,
    data: DocumentSeriesReservationCreate,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> DocumentSeriesReservationResponse:
    reservation = DocumentSeriesService.reserve_correlatives(
        db=db,
        series_id=id,
        payload=data,
        principal=principal,
        context=audit_ctx,
    )
    series = reservation.series
    first_code = format_canonical_document_code(
        series.document_type.code,
        series.branch.code,
        series.period_year,
        reservation.start_correlative,
        series.correlative_width,
    )
    last_code = format_canonical_document_code(
        series.document_type.code,
        series.branch.code,
        series.period_year,
        reservation.end_correlative,
        series.correlative_width,
    )
    return DocumentSeriesReservationResponse(
        id=reservation.id,
        series_id=reservation.series_id,
        start_correlative=reservation.start_correlative,
        end_correlative=reservation.end_correlative,
        quantity=reservation.quantity,
        first_display_code=first_code,
        last_display_code=last_code,
        reserved_by_user_id=reservation.reserved_by_user_id,
        reserved_by_name=principal.email,
        reserved_at=reservation.reserved_at,
        reason=reservation.reason,
        correlation_id=reservation.correlation_id,
    )


@router.get(
    "/document-series/reservations/{id}",
    response_model=DocumentSeriesReservationResponse,
    summary="Get reservation details by ID",
    dependencies=[Depends(require_permission("document_series.read"))],
)
def get_reservation_detail(
    id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> DocumentSeriesReservationResponse:
    reservation = DocumentSeriesService.get_reservation_by_id(
        db=db, reservation_id=id, principal=principal
    )
    series = reservation.series
    first_code = format_canonical_document_code(
        series.document_type.code,
        series.branch.code,
        series.period_year,
        reservation.start_correlative,
        series.correlative_width,
    )
    last_code = format_canonical_document_code(
        series.document_type.code,
        series.branch.code,
        series.period_year,
        reservation.end_correlative,
        series.correlative_width,
    )
    return DocumentSeriesReservationResponse(
        id=reservation.id,
        series_id=reservation.series_id,
        start_correlative=reservation.start_correlative,
        end_correlative=reservation.end_correlative,
        quantity=reservation.quantity,
        first_display_code=first_code,
        last_display_code=last_code,
        reserved_by_user_id=reservation.reserved_by_user_id,
        reserved_by_name=reservation.user.display_name if reservation.user else None,
        reserved_at=reservation.reserved_at,
        reason=reservation.reason,
        correlation_id=reservation.correlation_id,
    )


@router.get(
    "/document-series/{id}/numbers",
    response_model=List[DocumentSeriesNumberResponse],
    summary="List individual correlative numbers for a series",
    dependencies=[Depends(require_permission("document_series.read"))],
)
def list_series_numbers(
    id: uuid.UUID,
    status: Optional[str] = Query(None, description="Filter by status: RESERVED, VOIDED"),
    reservation_id: Optional[uuid.UUID] = Query(None, description="Filter by reservation ID"),
    from_correlative: Optional[int] = Query(None, description="Minimum correlative"),
    to_correlative: Optional[int] = Query(None, description="Maximum correlative"),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> List[DocumentSeriesNumberResponse]:
    numbers = DocumentSeriesService.get_series_numbers(
        db=db,
        series_id=id,
        principal=principal,
        status=status,
        reservation_id=reservation_id,
        from_correlative=from_correlative,
        to_correlative=to_correlative,
    )
    return [
        DocumentSeriesNumberResponse(
            id=n.id,
            series_id=n.series_id,
            reservation_id=n.reservation_id,
            correlative=n.correlative,
            display_code=n.display_code,
            status=n.status,
            reserved_at=n.reserved_at,
            voided_at=n.voided_at,
            voided_by_user_id=n.voided_by_user_id,
            voided_by_name=n.voided_by.display_name if n.voided_by else None,
            void_reason=n.void_reason,
        )
        for n in numbers
    ]


@router.post(
    "/document-series/numbers/{id}/void",
    response_model=DocumentSeriesNumberResponse,
    summary="Void a reserved correlative number without freeing or reusing it",
    dependencies=[Depends(require_permission("document_series.void")), Depends(validate_csrf)],
)
def void_series_number(
    id: uuid.UUID,
    data: VoidDocumentNumberRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> DocumentSeriesNumberResponse:
    number = DocumentSeriesService.void_number(
        db=db,
        number_id=id,
        payload=data,
        principal=principal,
        context=audit_ctx,
    )
    return DocumentSeriesNumberResponse(
        id=number.id,
        series_id=number.series_id,
        reservation_id=number.reservation_id,
        correlative=number.correlative,
        display_code=number.display_code,
        status=number.status,
        reserved_at=number.reserved_at,
        voided_at=number.voided_at,
        voided_by_user_id=number.voided_by_user_id,
        voided_by_name=principal.email,
        void_reason=number.void_reason,
    )


@router.get(
    "/document-series/reservations/{id}/booklet",
    summary="Download technical numbering booklet (talonario) in CSV format",
    dependencies=[Depends(require_permission("document_series.download"))],
)
def download_reservation_booklet(
    id: uuid.UUID,
    format: str = Query("csv", description="Format of booklet: csv"),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    audit_ctx: AuditContext = Depends(get_audit_context),
):
    if format.lower() != "csv":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no soportado. Únicamente se admite format=csv en F013.",
        )
    csv_content = DocumentSeriesService.generate_booklet_csv(
        db=db,
        reservation_id=id,
        principal=principal,
        context=audit_ctx,
    )
    filename = f"talonario_reserva_{id}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================================================
# F014: DOCUMENT TEMPLATES & RENDERING ENGINE ENDPOINTS
# ============================================================================


@router.get(
    "/document-renderer/templates",
    response_model=List[TemplateManifest],
    summary="List registered document templates and manifests",
    dependencies=[Depends(require_permission("document_templates.read"))],
)
def list_document_templates(
    family: Optional[str] = Query(None, description="Filter by template family"),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> List[TemplateManifest]:
    """Retrieves all registered template manifests."""
    return TemplateRegistry.list_templates(family=family)


@router.get(
    "/document-renderer/templates/{template_key}",
    response_model=TemplateManifest,
    summary="Get document template manifest by key",
    dependencies=[Depends(require_permission("document_templates.read"))],
)
def get_document_template(
    template_key: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> TemplateManifest:
    """Retrieves specific template manifest."""
    return TemplateRegistry.get_manifest(template_key)


class RenderPreviewRequest(BaseModel):
    template_key: Optional[str] = Field(
        None, description="Target template key (defaults to base_document_v1)"
    )
    format: str = Field(default="pdf", description="Output format: pdf or html")
    context: DocumentRenderContext


@router.post(
    "/document-renderer/preview",
    summary="Generate on-demand document preview (PDF or HTML) from canonical render context",
    dependencies=[Depends(require_permission("document_templates.preview"))],
)
def render_document_preview(
    payload: RenderPreviewRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """Executes backend rendering pipeline and returns compiled PDF or HTML preview."""
    service = DocumentRenderingService()
    pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(
        context=payload.context,
        template_key=payload.template_key,
    )

    headers = {
        "X-Snapshot-Hash": snapshot_hash,
        "X-Pdf-Hash": pdf_hash,
        "X-Renderer-Name": "WeasyPrint",
        "X-Renderer-Version": "69.0",
    }

    if payload.format.lower() == "html":
        return HTMLResponse(content=html_content, headers=headers)

    filename = f"{payload.context.document.display_code}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            **headers,
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


@router.post(
    "/document-renderer/sample",
    summary="Generate canonical sample document for visual verification",
    dependencies=[Depends(require_permission("document_templates.preview"))],
)
def render_sample_document(
    format: str = Query("pdf", description="Output format: pdf or html"),
    rows_count: int = Query(10, ge=1, le=100, description="Number of table rows in sample"),
    status_code: str = Query("DRAFT", description="Document status: DRAFT, APPROVED, ISSUED, VOID"),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Builds a realistic synthetic sample document context and renders it."""
    # Find branch/org info
    branch_name = "Sede Principal Lima"
    branch_code = "LIM"
    org_name = "Organización Logística Integral"
    tax_id = "20100012345"

    if principal.organization_id:
        from app.modules.organization.models import Branch, Organization

        org = db.query(Organization).filter(Organization.id == principal.organization_id).first()
        if org:
            org_name = org.name
        branch = (
            db.query(Branch).filter(Branch.organization_id == principal.organization_id).first()
        )
        if branch:
            branch_name = branch.name
            branch_code = branch.code

    # Build sample rows
    rows = []
    for i in range(1, rows_count + 1):
        rows.append(
            {
                "item_no": str(i),
                "sku": f"MAT-GRE-{i:04d}",
                "description": (
                    f"Greda refractaria formulada estándar grado {i} para hornos industriales"
                ),
                "unit": "KG",
                "quantity": f"{i * 25.50:.2f}",
                "unit_price": f"S/ {14.20 + i:.2f}",
                "total": f"S/ {(i * 25.50) * (14.20 + i):.2f}",
            }
        )

    ctx = DocumentRenderContext(
        organization=OrganizationHeaderContext(
            name=org_name,
            code="ORG-01",
            tax_id=tax_id,
        ),
        branch=BranchHeaderContext(
            name=branch_name,
            code=branch_code,
            address="Av. Industrial 456, Parque Logístico, Lima, Perú",
        ),
        document=DocumentHeaderContext(
            type_code="PO",
            type_name="Orden de Compra / Requisición Logística",
            display_code=f"PO-{branch_code}-2026-000001",
            status=status_code.upper(),
            version_number=1,
            emission_date="2026-08-29",
        ),
        metadata=DocumentMetadataContext(
            generated_by=principal.email,
            template_key="base_document_v1",
            template_version="1.0.0",
        ),
        summary_fields=[
            {"label": "Proveedor", "value": "Insumos Minerales del Perú S.A.C."},
            {"label": "Condición de Pago", "value": "Crédito 30 días"},
            {"label": "Moneda", "value": "Soles (PEN)"},
            {"label": "Prioridad", "value": "Alta / Producción Inmediata"},
        ],
        tables=[
            DocumentTableContext(
                title="Detalle de Ítems e Insumos Solicitados",
                columns=[
                    TableColumnContext(key="item_no", label="Item", align="center", width="5%"),
                    TableColumnContext(key="sku", label="Código SKU", align="center", width="15%"),
                    TableColumnContext(
                        key="description",
                        label="Descripción del Material",
                        align="left",
                        width="40%",
                    ),
                    TableColumnContext(key="unit", label="U.M.", align="center", width="8%"),
                    TableColumnContext(
                        key="quantity", label="Cantidad", align="right", width="10%"
                    ),
                    TableColumnContext(
                        key="unit_price", label="P. Unit.", align="right", width="10%"
                    ),
                    TableColumnContext(key="total", label="Total", align="right", width="12%"),
                ],
                rows=rows,
            )
        ],
        notes=(
            "Documento de prueba sintético generado por el motor central de renderizado F014. "
            "Incluye validación completa de caracteres Unicode (ñ, á, é, í, ó, ú, S/), "
            "saltos de página y verificación criptográfica QR."
        ),
        visual_signature=VisualSignatureContext(
            signer_name=principal.display_name or principal.email,
            signer_role="Responsable de Compras & Logística",
            signed_at="2026-08-29 13:00:00 UTC",
        ),
    )

    service = DocumentRenderingService()
    pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(
        context=ctx,
        template_key="base_document_v1",
    )

    headers = {
        "X-Snapshot-Hash": snapshot_hash,
        "X-Pdf-Hash": pdf_hash,
        "X-Renderer-Name": "WeasyPrint",
        "X-Renderer-Version": "69.0",
    }

    if format.lower() == "html":
        return HTMLResponse(content=html_content, headers=headers)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            **headers,
            "Content-Disposition": f'inline; filename="{ctx.document.display_code}.pdf"',
        },
    )


# ============================================================================

# ============================================================================
# F015: PURCHASING DOCUMENT SAMPLES & PREVIEW SCENARIOS
# ============================================================================


def build_purchasing_sample_context(
    doc_code: str,
    scenario: str = "basic",
    status_code: Optional[str] = None,
    org_name: str = "Organización Logística Integral del Perú",
    tax_id: str = "20100012345",
    branch_name: str = "Sede Central Lima",
    branch_code: str = "LIM",
    branch_address: str = "Av. Industrial 456, Parque Logístico, Callao, Lima",
    user_email: str = "gerencia.demo@logistica.local",
) -> Tuple[DocumentRenderContext, str]:
    """Builds realistic synthetic preview context for the 6 purchasing documents."""
    code_upper = doc_code.upper().strip()
    is_multi = scenario.lower() in ("multipage", "multi")
    is_long = scenario.lower() in ("long_text", "long")
    rows_count = 50 if is_multi else (20 if is_long else 6)

    org_ctx = OrganizationHeaderContext(name=org_name, code="ORG-01", tax_id=tax_id)
    branch_ctx = BranchHeaderContext(name=branch_name, code=branch_code, address=branch_address)

    if code_upper == "REQ":
        st = status_code.upper() if status_code else "DRAFT"
        template_key = "purchase_requisition_v1"
        rows = [
            {
                "item_no": str(i),
                "sku": f"MAT-GRE-{i:04d}",
                "description": (
                    f"Greda refractaria formulada estándar grado {i} "
                    "para hornos térmicos industriales"
                    if is_long
                    else f"Greda refractaria grado {i} para fundición"
                ),
                "unit": "KG",
                "quantity": f"{i * 50.0:.2f}",
                "required_date": "2026-09-15",
                "notes": (
                    "Certificado de calidad requerido" if i % 2 == 0 else "Urgente para línea 2"
                ),
            }
            for i in range(1, rows_count + 1)
        ]
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="REQ",
                type_name="Requerimiento de Compra",
                display_code=f"PREVIEW-REQ-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Solicitante", "value": "Ing. Carlos Mendoza (Jefe de Planta)"},
                {"label": "Área / Departamento", "value": "Mantenimiento & Producción"},
                {"label": "Centro de Costo", "value": "CC-PROD-LIMA-01 (Líneas Térmicas)"},
                {"label": "Prioridad Operativa", "value": "Alta / Parada de Planta"},
            ],
            tables=[
                DocumentTableContext(
                    title="Detalle de Bienes e Insumos Solicitados",
                    columns=[
                        TableColumnContext(key="item_no", label="Item", align="center", width="6%"),
                        TableColumnContext(
                            key="sku", label="Código SKU", align="center", width="14%"
                        ),
                        TableColumnContext(
                            key="description",
                            label="Descripción del Requerimiento",
                            align="left",
                            width="38%",
                        ),
                        TableColumnContext(
                            key="quantity", label="Cantidad", align="right", width="12%"
                        ),
                        TableColumnContext(key="unit", label="U.M.", align="center", width="8%"),
                        TableColumnContext(
                            key="required_date", label="F. Requerida", align="center", width="10%"
                        ),
                        TableColumnContext(
                            key="notes", label="Observaciones", align="left", width="12%"
                        ),
                    ],
                    rows=rows,
                )
            ],
            notes=(
                "Requerimiento generado para renovación de revestimientos térmicos en fundición. "
                "Los materiales deben contar con certificación técnica y ficha de seguridad."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Carlos Mendoza Ramos",
                signer_role="Jefe de Planta & Mantenimiento",
                signed_at="2026-08-29 10:30:00 UTC",
            ),
            watermark_text=(
                "BORRADOR" if st == "DRAFT" else ("ANULADO" if st == "VOID" else "VISTA PREVIA")
            ),
        )
        return ctx, template_key

    elif code_upper == "RFQ":
        st = status_code.upper() if status_code else "ISSUED"
        template_key = "request_for_quotation_v1"
        rows = [
            {
                "item_no": str(i),
                "sku": f"MAT-GRE-{i:04d}",
                "description": (
                    f"Greda refractaria formulada estándar grado {i} "
                    "con resistencia térmica hasta 1400°C"
                ),
                "quantity": f"{i * 50.0:.2f}",
                "unit": "KG",
                "target_date": "2026-09-20",
            }
            for i in range(1, rows_count + 1)
        ]
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="RFQ",
                type_name="Solicitud de Cotización",
                display_code=f"PREVIEW-RFQ-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Requerimiento Asociado", "value": f"REQ-{branch_code}-2026-000142"},
                {"label": "Fecha Límite de Recepción", "value": "2026-09-05 18:00 UTC"},
                {"label": "Comprador a Cargo", "value": "Lic. Patricia Alarcón"},
                {"label": "Moneda Referencial", "value": "Soles (PEN) / Dólares (USD)"},
            ],
            tables=[
                DocumentTableContext(
                    title="Ítems e Insumos para Cotización",
                    columns=[
                        TableColumnContext(key="item_no", label="Item", align="center", width="8%"),
                        TableColumnContext(
                            key="sku", label="Código SKU", align="center", width="18%"
                        ),
                        TableColumnContext(
                            key="description",
                            label="Descripción Técnica & Requisitos",
                            align="left",
                            width="44%",
                        ),
                        TableColumnContext(
                            key="quantity", label="Cantidad", align="right", width="15%"
                        ),
                        TableColumnContext(key="unit", label="U.M.", align="center", width="15%"),
                    ],
                    rows=rows,
                )
            ],
            custom_content={
                "supplier": {
                    "name": "Minerales & Refractarios del Centro S.A.C.",
                    "tax_id": "20448899112",
                    "contact_name": "Ing. Fernando Salas",
                    "email": "ventas@refractarioscentro.pe",
                }
            },
            notes=(
                "Condiciones comerciales solicitadas: Plazo de entrega máximo 10 días útiles. "
                "Forma de pago requerida: Factura a 30 días crédito. Indicar marca y garantía."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Patricia Alarcón Vera",
                signer_role="Especialista de Compras & Abastecimiento",
                signed_at="2026-08-29 11:00:00 UTC",
            ),
            watermark_text="VISTA PREVIA" if st != "VOID" else "ANULADO",
        )
        return ctx, template_key

    elif code_upper == "CMP":
        st = status_code.upper() if status_code else "APPROVED"
        template_key = "comparative_table_v1"
        rows = []
        for i in range(1, rows_count + 1):
            rows.append(
                {
                    "item_no": str(i),
                    "sku": f"MAT-GRE-{i:04d}",
                    "description": f"Greda refractaria grado {i}",
                    "quantity": f"{i * 50:.0f} KG",
                    "supp_a": f"S/ {14.50 + i:.2f} (7d / Cred)",
                    "supp_b": f"S/ {13.80 + i:.2f} (5d / Cred) ★",
                    "supp_c": f"S/ {15.20 + i:.2f} (12d / Cont)",
                    "recommended": "Proveedor B (Mejor Precio y Plazo)",
                }
            )
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="CMP",
                type_name="Cuadro Comparativo de Ofertas",
                display_code=f"PREVIEW-CMP-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "RFQ de Referencia", "value": f"RFQ-{branch_code}-2026-000088"},
                {"label": "Requerimiento", "value": f"REQ-{branch_code}-2026-000142"},
                {"label": "Evaluador Comercial", "value": "Lic. Patricia Alarcón"},
                {
                    "label": "Proveedor Adjudicado",
                    "value": "Minerales & Refractarios del Centro (94.5 pts)",
                },
            ],
            tables=[
                DocumentTableContext(
                    title="Matriz de Evaluación Comparativa de Proveedores",
                    columns=[
                        TableColumnContext(key="item_no", label="#", align="center", width="4%"),
                        TableColumnContext(key="sku", label="SKU", align="center", width="10%"),
                        TableColumnContext(
                            key="description", label="Descripción", align="left", width="22%"
                        ),
                        TableColumnContext(
                            key="quantity", label="Cantidad", align="right", width="8%"
                        ),
                        TableColumnContext(
                            key="supp_a", label="Prov A: Insumos Perú", align="center", width="18%"
                        ),
                        TableColumnContext(
                            key="supp_b",
                            label="Prov B: Refractarios Centro (★)",
                            align="center",
                            width="20%",
                        ),
                        TableColumnContext(
                            key="supp_c",
                            label="Prov C: Minas Andinas",
                            align="center",
                            width="18%",
                        ),
                    ],
                    rows=rows,
                )
            ],
            notes=(
                "Se adjudica la compra al Proveedor B (Minerales & Refractarios del Centro S.A.C.) "
                "por presentar la mejor propuesta técnico-económica y menor tiempo de entrega."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Comité de Adquisiciones & Logística",
                signer_role="Evaluación Técnica y Financiera",
                signed_at="2026-08-29 14:00:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    elif code_upper == "PO":
        st = status_code.upper() if status_code else "ISSUED"
        template_key = "purchase_order_v1"
        rows = []
        total_subtotal = 0.0
        for i in range(1, rows_count + 1):
            qty = i * 25.0
            price = 14.50 + (i * 0.5)
            sub = qty * price
            total_subtotal += sub
            rows.append(
                {
                    "item_no": str(i),
                    "sku": f"MAT-GRE-{i:04d}",
                    "description": (
                        f"Greda refractaria formulada estándar grado {i} en sacos de 25 kg"
                    ),
                    "quantity": f"{qty:.2f}",
                    "unit": "KG",
                    "unit_price": f"S/ {price:.2f}",
                    "total": f"S/ {sub:.2f}",
                }
            )
        igv = total_subtotal * 0.18
        total_general = total_subtotal + igv

        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="PO",
                type_name="Orden de Compra Oficial",
                display_code=f"PREVIEW-PO-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Condición de Pago", "value": "Crédito a 30 días calendario"},
                {"label": "Moneda", "value": "Soles (PEN)"},
                {"label": "Referencia REQ", "value": f"REQ-{branch_code}-2026-000142"},
                {"label": "Referencia CMP", "value": f"CMP-{branch_code}-2026-000088"},
            ],
            tables=[
                DocumentTableContext(
                    title="Detalle de Ítems e Insumos Contratados",
                    columns=[
                        TableColumnContext(key="item_no", label="Item", align="center", width="6%"),
                        TableColumnContext(
                            key="sku", label="Código SKU", align="center", width="15%"
                        ),
                        TableColumnContext(
                            key="description",
                            label="Descripción del Material",
                            align="left",
                            width="39%",
                        ),
                        TableColumnContext(
                            key="quantity", label="Cantidad", align="right", width="10%"
                        ),
                        TableColumnContext(key="unit", label="U.M.", align="center", width="8%"),
                        TableColumnContext(
                            key="unit_price", label="P. Unit.", align="right", width="10%"
                        ),
                        TableColumnContext(
                            key="total", label="Subtotal", align="right", width="12%"
                        ),
                    ],
                    rows=rows,
                )
            ],
            custom_content={
                "supplier": {
                    "name": "Minerales & Refractarios del Centro S.A.C.",
                    "tax_id": "20448899112",
                    "address": "Av. Los Ingenieros 789, Urb. Industrial, Ate, Lima",
                    "contact_name": "Ing. Fernando Salas",
                    "email": "ventas@refractarioscentro.pe",
                },
                "financial_summary": [
                    {
                        "label": "Subtotal Afecto",
                        "value": f"S/ {total_subtotal:,.2f}",
                        "is_total": False,
                    },
                    {"label": "I.G.V. (18%)", "value": f"S/ {igv:,.2f}", "is_total": False},
                    {
                        "label": "TOTAL ORDEN DE COMPRA",
                        "value": f"S/ {total_general:,.2f}",
                        "is_total": True,
                    },
                ],
                "delivery_schedule": (
                    [
                        {
                            "installment_no": 1,
                            "scheduled_date": "2026-09-08",
                            "quantity": f"{total_subtotal * 0.5 / 15:.1f} KG",
                            "destination_branch_or_warehouse": f"Almacén Principal {branch_name}",
                        },
                        {
                            "installment_no": 2,
                            "scheduled_date": "2026-09-22",
                            "quantity": f"{total_subtotal * 0.5 / 15:.1f} KG",
                            "destination_branch_or_warehouse": f"Almacén Principal {branch_name}",
                        },
                    ]
                    if is_multi
                    else None
                ),
            },
            notes=(
                "1. La entrega debe acompañarse con la Guía de Remisión Remitente del proveedor. "
                "2. La recepción en almacén queda sujeta a control de calidad y "
                "conformidad técnica. "
                "3. Facturación electrónica debe consignar el RUC y razón social exacta."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Gerencia General / Dirección de Operaciones",
                signer_role="Aprobación Oficial de Adquisiciones",
                signed_at="2026-08-29 15:00:00 UTC",
            ),
            watermark_text=(
                "BORRADOR" if st == "DRAFT" else ("ANULADO" if st == "VOID" else "VISTA PREVIA")
            ),
        )
        return ctx, template_key

    elif code_upper == "POA":
        st = status_code.upper() if status_code else "APPROVED"
        template_key = "purchase_approval_v1"
        rows = [
            {
                "level": "Nivel 1: Jefatura de Compras",
                "approver": "Patricia Alarcón Vera",
                "date": "2026-08-29 11:30 UTC",
                "result": "CONFORME",
                "comments": "Evaluación comercial y cuadro comparativo aprobados.",
            },
            {
                "level": "Nivel 2: Gerencia de Operaciones",
                "approver": "Ing. Miguel Ángel Torres",
                "date": "2026-08-29 14:15 UTC",
                "result": "CONFORME",
                "comments": "Presupuesto disponible en CC-PROD-LIMA-01.",
            },
            {
                "level": "Nivel 3: Gerencia General",
                "approver": "Dr. Fernando Morales",
                "date": "2026-08-29 16:00 UTC",
                "result": "DICTAMEN FAVORABLE",
                "comments": "Aprobado para emisión inmediata de Orden de Compra.",
            },
        ]
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="POA",
                type_name="Acta de Aprobación de Compra",
                display_code=f"PREVIEW-POA-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Orden de Compra Relacionada", "value": f"PO-{branch_code}-2026-000189"},
                {"label": "Monto Total Aprobado", "value": "S/ 84,550.00 PEN (Inc. IGV)"},
                {
                    "label": "Proveedor Adjudicado",
                    "value": "Minerales & Refractarios del Centro S.A.C.",
                },
                {"label": "Centro de Costo", "value": "CC-PROD-LIMA-01 (Operaciones)"},
            ],
            tables=[
                DocumentTableContext(
                    title="Historial de Niveles y Cadena de Aprobación",
                    columns=[
                        TableColumnContext(
                            key="level", label="Nivel / Instancia", align="left", width="28%"
                        ),
                        TableColumnContext(
                            key="approver", label="Responsable", align="left", width="24%"
                        ),
                        TableColumnContext(
                            key="date", label="Fecha / Hora", align="center", width="18%"
                        ),
                        TableColumnContext(
                            key="result", label="Dictamen", align="center", width="15%"
                        ),
                        TableColumnContext(
                            key="comments", label="Comentarios", align="left", width="15%"
                        ),
                    ],
                    rows=rows,
                )
            ],
            notes=(
                "El presente dictamen formaliza la autorización de gasto y contratación según "
                "las políticas corporativas de compras mayores. Registrado en log inmutable."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Dr. Fernando Morales Castro",
                signer_role="Gerente General & Apoderado",
                signed_at="2026-08-29 16:00:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    elif code_upper == "PSC":
        st = status_code.upper() if status_code else "PROCESSED"
        template_key = "supplier_send_confirmation_v1"
        rows = [
            {
                "item_no": "1",
                "doc_name": f"Orden de Compra Oficial (PO-{branch_code}-2026-000189.pdf)",
                "size": "34.5 KB",
                "hash_sha256": "43f18f352c9423c10a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef",
                "status": "ENTREGADO",
            },
            {
                "item_no": "2",
                "doc_name": "Especificaciones Técnicas y Planos (ANEXO-TEC-01.pdf)",
                "size": "1.2 MB",
                "hash_sha256": "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef43f18f352c9423c10",
                "status": "ENTREGADO",
            },
        ]
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="PSC",
                type_name="Constancia de Envío a Proveedor",
                display_code=f"PREVIEW-PSC-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Orden de Compra Asociada", "value": f"PO-{branch_code}-2026-000189"},
                {
                    "label": "Proveedor Notificado",
                    "value": "Minerales & Refractarios del Centro S.A.C.",
                },
                {"label": "Canal de Notificación", "value": "EMAIL / SERVIDOR SEGURO"},
                {"label": "ID Mensaje / Tracking", "value": "MSG-20260829-88912-CALLAO"},
            ],
            tables=[
                DocumentTableContext(
                    title="Documentos y Archivos Adjuntos Transmitidos",
                    columns=[
                        TableColumnContext(key="item_no", label="#", align="center", width="6%"),
                        TableColumnContext(
                            key="doc_name", label="Documento / Archivo", align="left", width="40%"
                        ),
                        TableColumnContext(key="size", label="Tamaño", align="center", width="12%"),
                        TableColumnContext(
                            key="hash_sha256",
                            label="Hash Criptográfico SHA-256",
                            align="center",
                            width="30%",
                        ),
                        TableColumnContext(
                            key="status", label="Estado", align="center", width="12%"
                        ),
                    ],
                    rows=rows,
                )
            ],
            custom_content={
                "send_channel": "NOTIFICACIÓN ELECTRÓNICA POR CORREO",
                "send_reference": "REF: MSG-20260829-88912-CALLAO",
                "supplier": {
                    "name": "Minerales & Refractarios del Centro S.A.C.",
                    "tax_id": "20448899112",
                    "email": "ventas@refractarioscentro.pe, despacho@refractarioscentro.pe",
                },
            },
            notes=(
                "Constancia documental que certifica el envío técnico de la Orden de Compra y "
                "anexos al proveedor. El proveedor confirmó recepción a las 16:30 UTC."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Área de Adquisiciones & Despacho",
                signer_role="Oficial de Comunicaciones con Proveedores",
                signed_at="2026-08-29 16:35:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Código documental de compras no soportado: {doc_code}. "
                "Soportados: REQ, RFQ, CMP, PO, POA, PSC."
            ),
        )


@router.post(
    "/document-renderer/purchasing/{doc_code}/sample",
    summary="Generate canonical sample preview for purchasing document types",
    dependencies=[Depends(require_permission("document_templates.preview"))],
)
def render_purchasing_sample_document(
    doc_code: str,
    scenario: str = Query(
        "basic", description="Scenario: basic, multipage, long_text, multi_supplier"
    ),
    status_code: Optional[str] = Query(
        None, description="Document status (e.g. DRAFT, APPROVED, ISSUED, VOID)"
    ),
    format: str = Query("pdf", description="Output format: pdf or html"),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Renders canonical synthetic preview for purchasing documents."""
    branch_name = "Sede Principal Lima"
    branch_code = "LIM"
    org_name = "Organización Logística Integral del Perú"
    tax_id = "20100012345"
    branch_address = "Av. Industrial 456, Parque Logístico, Callao, Lima"

    if principal.organization_id:
        from app.modules.organization.models import Branch, Organization

        org = db.query(Organization).filter(Organization.id == principal.organization_id).first()
        if org:
            org_name = org.name
        branch = (
            db.query(Branch).filter(Branch.organization_id == principal.organization_id).first()
        )
        if branch:
            branch_name = branch.name
            branch_code = branch.code
            if branch.location and branch.location.address_line1:
                branch_address = branch.location.address_line1

    ctx, template_key = build_purchasing_sample_context(
        doc_code=doc_code,
        scenario=scenario,
        status_code=status_code,
        org_name=org_name,
        tax_id=tax_id,
        branch_name=branch_name,
        branch_code=branch_code,
        branch_address=branch_address,
        user_email=principal.email,
    )

    service = DocumentRenderingService()
    pdf_bytes, html_content, snapshot_hash, pdf_hash = service.process_and_render(
        context=ctx,
        template_key=template_key,
    )

    headers = {
        "X-Snapshot-Hash": snapshot_hash,
        "X-Pdf-Hash": pdf_hash,
        "X-Template-Key": template_key,
        "X-Document-Type": doc_code.upper(),
        "X-Renderer-Name": "WeasyPrint",
        "X-Renderer-Version": "69.0",
    }

    if format.lower() == "html":
        return HTMLResponse(content=html_content, headers=headers)

    filename = f"{ctx.document.display_code}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            **headers,
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )
