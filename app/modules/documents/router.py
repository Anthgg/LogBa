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


def build_receiving_sample_context(
    doc_code: str,
    scenario: str,
    status_code: Optional[str],
    org_name: str,
    tax_id: str,
    branch_name: str,
    branch_code: str,
    branch_address: str,
    user_email: str,
) -> tuple[DocumentRenderContext, str]:
    """Builds synthetic sample document context for the 6 inbound receiving types (F016)."""
    org_ctx = OrganizationHeaderContext(
        name=org_name, code="ORG-01", tax_id=tax_id, logo_base64=None
    )
    branch_ctx = BranchHeaderContext(name=branch_name, code=branch_code, address=branch_address)
    code_upper = doc_code.upper().strip()

    if code_upper == "ARR":
        st = status_code.upper() if status_code else "SCHEDULED"
        template_key = "arrival_appointment_v1"
        item_count = 50 if scenario == "multipage" else 6
        rows = [
            {
                "item_no": str(i + 1),
                "sku": f"MAT-INB-{(i + 1):03d}",
                "description": f"Suministro Industrial / Insumo Operativo Tipo #{i + 1}",
                "ordered_qty": f"{(i + 1) * 150:,.2f}",
                "unit": "UND" if i % 2 == 0 else "KG",
                "pallets": str((i % 4) + 1),
                "weight_kg": f"{(i + 1) * 75.5:,.1f} kg",
            }
            for i in range(item_count)
        ]
        notes_text = (
            "El conductor y la cuadrilla deben ingresar con implementos de seguridad completos "
            "(casco, chaleco reflectivo, calzado de seguridad con puntera de acero). "
            "Reportar precinto en garita vehicular 15 minutos antes de la ventana asignada."
        )
        if scenario == "long_text":
            notes_text += (
                " Protocolo de descarga para insumos pesados: El transportista deberá presentar "
                "la Guía de Remisión Remitente (GTR) y el Certificado de Calidad de Origen antes "
                "de iniciar la maniobra de acople en el muelle asignado. En caso de lluvia o "
                "condiciones climáticas adversas, la unidad deberá permanecer encarpada hasta "
                "la autorización explícita del supervisor de patio."
            )

        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="ARR",
                type_name="Cita de Llegada / Arribo",
                display_code=f"PREVIEW-ARR-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Proveedor", "value": "Aceros y Derivados del Pacífico S.A.C."},
                {
                    "label": "Empresa de Transporte",
                    "value": "Transportes & Carga TransAndina E.I.R.L.",
                },
                {"label": "Conductor", "value": "Carlos Alberto Mendoza Peña (Lic: Q-44891023)"},
                {"label": "Placa Tracto / Remolque", "value": "B8Z-912 / T5A-780"},
                {"label": "Orden de Compra Relacionada", "value": f"PO-{branch_code}-2026-000189"},
                {"label": "Guía Remitente (GTR)", "value": "T001-0008451"},
                {"label": "Total Pallets Estimados", "value": "18 Pallets Estándar"},
                {"label": "Peso Bruto Total", "value": "12,450.00 kg"},
            ],
            tables=[
                DocumentTableContext(
                    title="Detalle de Carga y Mercancía Programada para Descarga",
                    columns=[
                        TableColumnContext(key="item_no", label="#", align="center", width="5%"),
                        TableColumnContext(
                            key="sku", label="Código SKU", align="left", width="16%"
                        ),
                        TableColumnContext(
                            key="description",
                            label="Descripción del Producto",
                            align="left",
                            width="35%",
                        ),
                        TableColumnContext(
                            key="ordered_qty", label="Cantidad Prog.", align="right", width="14%"
                        ),
                        TableColumnContext(key="unit", label="U.M.", align="center", width="8%"),
                        TableColumnContext(
                            key="pallets", label="Bultos", align="center", width="8%"
                        ),
                        TableColumnContext(
                            key="weight_kg", label="Peso Est.", align="right", width="14%"
                        ),
                    ],
                    rows=rows,
                )
            ],
            custom_content={
                "appointment_window": "2026-08-29 de 08:30 a 11:30 (Ventana 3 Horas)",
                "dock": "Muelle #03 (Carga Pesada)",
            },
            notes=notes_text,
            visual_signature=VisualSignatureContext(
                signer_name="Ing. Javier Paredes Soto",
                signer_role="Coordinador de Citas & Patio de Maniobras",
                signed_at="2026-08-29 07:45:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    elif code_upper == "CPV":
        st = status_code.upper() if status_code else "INSIDE"
        template_key = "gate_control_v1"
        rows = [
            {
                "check_no": "1",
                "item": "Verificación de Identidad y Licencia del Conductor",
                "standard": "DNI / Licencia vigente y sin infracciones",
                "result": "CONFORME",
                "obs": "Conductor Carlos Mendoza verificado en padrón",
            },
            {
                "check_no": "2",
                "item": "Revisión de Precinto de Seguridad de Origen",
                "standard": "Precinto intacto con código coincidente con GTR",
                "result": "CONFORME",
                "obs": "Precinto Nro: SEC-2026-LIMA-88912 intacto",
            },
            {
                "check_no": "3",
                "item": "Inspección Visual de Carreta / Furgón",
                "standard": "Piso seco, sin olores ni contaminación cruzada",
                "result": "CONFORME",
                "obs": "Furgón en óptimas condiciones de higiene",
            },
            {
                "check_no": "4",
                "item": "Documentación Físico/Digital Presentada",
                "standard": "GTR Proveedor + Guía Transportista + OC",
                "result": "CONFORME" if scenario != "observed" else "OBSERVADO",
                "obs": "GTR T001-0008451 conforme"
                if scenario != "observed"
                else "Falta copia legible de guía transportista",
            },
            {
                "check_no": "5",
                "item": "Implementos de Protección Personal (EPP)",
                "standard": "Casco, chaleco, botas punta de acero",
                "result": "CONFORME",
                "obs": "Conductor cuenta con EPP completo",
            },
        ]
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="CPV",
                type_name="Control de Puerta Vehicular",
                display_code=f"PREVIEW-CPV-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Cita de Llegada Asociada", "value": f"ARR-{branch_code}-2026-0001"},
                {"label": "Garita / Punto de Control", "value": "Garita Principal G-01 (Norte)"},
                {"label": "Oficial de Seguridad", "value": "Sgto. Walter Ramos Quispe"},
                {"label": "Transportista", "value": "Transportes & Carga TransAndina E.I.R.L."},
                {"label": "Placa Tracto / Remolque", "value": "B8Z-912 / T5A-780"},
                {"label": "Nro Precinto Origen", "value": "SEC-2026-LIMA-88912"},
            ],
            tables=[
                DocumentTableContext(
                    title="Lista de Verificación de Seguridad y Documentos Presentados",
                    columns=[
                        TableColumnContext(key="check_no", label="#", align="center", width="5%"),
                        TableColumnContext(
                            key="item",
                            label="Criterio / Inspección de Garita",
                            align="left",
                            width="32%",
                        ),
                        TableColumnContext(
                            key="standard", label="Estándar Requerido", align="left", width="28%"
                        ),
                        TableColumnContext(
                            key="result", label="Resultado", align="center", width="13%"
                        ),
                        TableColumnContext(
                            key="obs", label="Observaciones Técnicas", align="left", width="22%"
                        ),
                    ],
                    rows=rows,
                )
            ],
            custom_content={
                "vehicle_plate": "B8Z-912 / T5A-780",
                "driver_name": "Carlos Alberto Mendoza Peña",
                "driver_dni": "44891023",
                "entry_time": "08:24:15 UTC",
                "exit_time": "11:45:00 UTC" if st == "EXITED" else "En Operación de Patio",
            },
            notes=(
                "El vehículo ingresó dentro de su ventana de cita autorizada. Se le asigna "
                "el carril 2 con destino al Muelle #03. Velocidad máxima en patio: 10 km/h."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Walter Ramos Quispe",
                signer_role="Oficial de Seguridad & Control de Garita",
                signed_at="2026-08-29 08:25:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    elif code_upper == "REC":
        st = status_code.upper() if status_code else "COMPLETED"
        template_key = "receiving_report_v1"
        item_count = 50 if scenario == "multipage" else 6
        rows = [
            {
                "item_no": str(i + 1),
                "sku": f"PRD-MAT-{(i + 1):03d}",
                "description": f"Material Industrial / Insumo Crítico Tipo #{i + 1}",
                "ordered_qty": f"{(i + 1) * 100:,.2f}",
                "shipped_qty": f"{(i + 1) * 100:,.2f}",
                "received_qty": f"{(i + 1) * 100:,.2f}"
                if scenario != "partial"
                else f"{(i + 1) * 80:,.2f}",
                "unit": "UND" if i % 2 == 0 else "KG",
                "lot_number": f"LOTE-2026-{(i + 1):03d}",
                "condition": "CONFORME" if scenario != "observed" or i != 1 else "OBSERVADO",
                "obs": "Empaque y rotulado óptimo"
                if scenario != "observed" or i != 1
                else "Empaque con signos de humedad externa",
            }
            for i in range(item_count)
        ]
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="REC",
                type_name="Acta de Recepción Técnica",
                display_code=f"PREVIEW-REC-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Orden de Compra", "value": f"PO-{branch_code}-2026-000189"},
                {"label": "Cita de Llegada", "value": f"ARR-{branch_code}-2026-0001"},
                {"label": "Proveedor", "value": "Aceros y Derivados del Pacífico S.A.C."},
                {"label": "Guía Remitente (GTR)", "value": "T001-0008451"},
                {"label": "Muelle de Descarga", "value": "Muelle #03 (Almacén Central)"},
                {"label": "Horario Descarga", "value": "08:45 a 10:30 UTC (1h 45m)"},
                {"label": "Inspector Técnico", "value": "Ing. Marco Tulio Morales"},
                {
                    "label": "Modalidad de Recepción",
                    "value": "Recepción Total"
                    if scenario != "partial"
                    else "Recepción Parcial Autorizada",
                },
            ],
            tables=[
                DocumentTableContext(
                    title="Detalle de Mercancía Recibida e Inspección Física en Muelle",
                    columns=[
                        TableColumnContext(key="item_no", label="#", align="center", width="4%"),
                        TableColumnContext(
                            key="sku", label="Código SKU", align="left", width="13%"
                        ),
                        TableColumnContext(
                            key="description",
                            label="Descripción del Producto",
                            align="left",
                            width="27%",
                        ),
                        TableColumnContext(
                            key="ordered_qty", label="Ordenado", align="right", width="10%"
                        ),
                        TableColumnContext(
                            key="received_qty", label="Recibido", align="right", width="10%"
                        ),
                        TableColumnContext(key="unit", label="U.M.", align="center", width="6%"),
                        TableColumnContext(
                            key="lot_number", label="Nro Lote", align="center", width="12%"
                        ),
                        TableColumnContext(
                            key="condition", label="Condición", align="center", width="9%"
                        ),
                        TableColumnContext(
                            key="obs", label="Observaciones", align="left", width="9%"
                        ),
                    ],
                    rows=rows,
                )
            ],
            custom_content={
                "technical_verdict": "CONFORM" if scenario != "observed" else "OBSERVED",
                "inspected_packages": "18 Pallets (100% Muestreado)",
            },
            notes=(
                "Se certifica que la mercancía detallada fue descargada en presencia "
                "del transportista y personal técnico. Los conteos y pesos coinciden."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Ing. Marco Tulio Morales",
                signer_role="Supervisor de Recepción & Calidad en Almacén",
                signed_at="2026-08-29 10:45:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    elif code_upper == "GRN":
        st = status_code.upper() if status_code else "ISSUED"
        template_key = "goods_receipt_v1"
        item_count = 50 if scenario == "multipage" else 6
        rows = [
            {
                "item_no": str(i + 1),
                "sku": f"PRD-MAT-{(i + 1):03d}",
                "description": f"Material Industrial / Insumo Crítico Tipo #{i + 1}",
                "accepted_qty": f"{(i + 1) * 100:,.2f}",
                "unit": "UND" if i % 2 == 0 else "KG",
                "lot_number": f"LOTE-2026-{(i + 1):03d}",
                "location": f"RACK-{(i % 5) + 1:02d}-N{(i % 3) + 1:02d}",
                "quality_status": "ACEPTADO",
            }
            for i in range(item_count)
        ]
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="GRN",
                type_name="Guía de Ingreso a Almacén",
                display_code=f"PREVIEW-GRN-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Acta de Recepción Relacionada", "value": f"REC-{branch_code}-2026-0001"},
                {"label": "Orden de Compra", "value": f"PO-{branch_code}-2026-000189"},
                {"label": "Proveedor", "value": "Aceros y Derivados del Pacífico S.A.C."},
                {"label": "Guía Remitente (GTR)", "value": "T001-0008451"},
                {
                    "label": "Almacén de Destino",
                    "value": f"Almacén Central Materias Primas ({branch_code})",
                },
                {"label": "Fecha / Hora Ingreso", "value": "2026-08-29 11:00:00 UTC"},
                {"label": "Responsable de Ingreso", "value": "Manuel Antonio Benítez Cruz"},
            ],
            tables=[
                DocumentTableContext(
                    title="Artículos Aceptados para Ingreso a Almacén",
                    columns=[
                        TableColumnContext(key="item_no", label="#", align="center", width="5%"),
                        TableColumnContext(
                            key="sku", label="Código SKU", align="left", width="15%"
                        ),
                        TableColumnContext(
                            key="description",
                            label="Descripción del Producto",
                            align="left",
                            width="33%",
                        ),
                        TableColumnContext(
                            key="accepted_qty", label="Cant. Aceptada", align="right", width="13%"
                        ),
                        TableColumnContext(key="unit", label="U.M.", align="center", width="7%"),
                        TableColumnContext(
                            key="lot_number", label="Lote", align="center", width="12%"
                        ),
                        TableColumnContext(
                            key="location", label="Ubicación Asignada", align="center", width="15%"
                        ),
                    ],
                    rows=rows,
                )
            ],
            notes=(
                "El presente documento sustenta el ingreso físico oficial a almacén. "
                "Queda registrado en el archivo documental inmutable del sistema."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Manuel Antonio Benítez Cruz",
                signer_role="Jefe de Almacén General",
                signed_at="2026-08-29 11:15:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    elif code_upper == "RDIFF":
        st = status_code.upper() if status_code else "OPEN"
        template_key = "receiving_difference_v1"
        item_count = 25 if scenario == "multipage" else 4
        rows = [
            {
                "item_no": "1",
                "sku": "MAT-LAM-001",
                "description": "Plancha de Acero Laminado 1/2 pulgada",
                "expected_qty": "200.00",
                "received_qty": "180.00",
                "difference_qty": "-20.00",
                "diff_type": "FALTANTE (SHORTAGE)",
                "severity": "ALTA",
                "obs": "Faltante de 20 unidades según bultos precintados",
            },
            {
                "item_no": "2",
                "sku": "MAT-PER-004",
                "description": "Perfil Estructural Cuadrado 50x50mm",
                "expected_qty": "100.00",
                "received_qty": "100.00",
                "difference_qty": "0.00",
                "diff_type": "DAÑADO (DAMAGED)",
                "severity": "MEDIA",
                "obs": "5 unidades con deformación severa por amarre",
            },
            {
                "item_no": "3",
                "sku": "MAT-PNT-012",
                "description": "Pintura Epóxica Anticorrosiva Gris (Galones)",
                "expected_qty": "50.00",
                "received_qty": "55.00",
                "difference_qty": "+5.00",
                "diff_type": "SOBRANTE (EXCESS)",
                "severity": "BAJA",
                "obs": "5 galones adicionales no solicitados en la OC",
            },
            {
                "item_no": "4",
                "sku": "MAT-DOC-000",
                "description": "Certificado de Análisis Metalográfico de Lote",
                "expected_qty": "1.00",
                "received_qty": "0.00",
                "difference_qty": "-1.00",
                "diff_type": "DOCUMENTAL",
                "severity": "ALTA",
                "obs": "Falta Certificado de Calidad del lote L-9921",
            },
        ]
        if scenario == "multipage":
            for i in range(4, item_count):
                rows.append(
                    {
                        "item_no": str(i + 1),
                        "sku": f"MAT-DISC-{(i + 1):03d}",
                        "description": f"Artículo con Discrepancia de Descarga #{i + 1}",
                        "expected_qty": f"{(i + 1) * 10:,.2f}",
                        "received_qty": f"{(i + 1) * 8:,.2f}",
                        "difference_qty": f"-{(i + 1) * 2:,.2f}",
                        "diff_type": "FALTANTE",
                        "severity": "MEDIA",
                        "obs": f"Discrepancia en bulto #{i + 1}",
                    }
                )

        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="RDIFF",
                type_name="Acta de Diferencias de Recepción",
                display_code=f"PREVIEW-RDIFF-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Acta de Recepción Técnica", "value": f"REC-{branch_code}-2026-0001"},
                {"label": "Orden de Compra", "value": f"PO-{branch_code}-2026-000189"},
                {"label": "Proveedor", "value": "Aceros y Derivados del Pacífico S.A.C."},
                {"label": "Transportista", "value": "Transportes & Carga TransAndina E.I.R.L."},
                {"label": "Conductor Presente", "value": "Carlos Alberto Mendoza Peña"},
                {"label": "Total Discrepancias", "value": f"{len(rows)} Ítems Observados"},
                {
                    "label": "Estado de Resolución",
                    "value": "Pendiente de Notificación al Proveedor",
                },
            ],
            tables=[
                DocumentTableContext(
                    title="Detalle de Discrepancias y Faltantes Registrados en Descarga",
                    columns=[
                        TableColumnContext(key="item_no", label="#", align="center", width="4%"),
                        TableColumnContext(
                            key="sku", label="Código SKU", align="left", width="12%"
                        ),
                        TableColumnContext(
                            key="description",
                            label="Descripción del Producto",
                            align="left",
                            width="26%",
                        ),
                        TableColumnContext(
                            key="expected_qty", label="Esperado", align="right", width="9%"
                        ),
                        TableColumnContext(
                            key="received_qty", label="Recibido", align="right", width="9%"
                        ),
                        TableColumnContext(
                            key="difference_qty", label="Diferencia", align="right", width="10%"
                        ),
                        TableColumnContext(
                            key="diff_type", label="Tipo Diferencia", align="center", width="14%"
                        ),
                        TableColumnContext(
                            key="obs", label="Detalle / Hallazgo", align="left", width="16%"
                        ),
                    ],
                    rows=rows,
                )
            ],
            notes=(
                "El presente documento certifica que el transportista y receptor han "
                "verificado diferencias. Se traslada a Compras para reclamo formal."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Carlos Mendoza Peña (Conductor) / Marco Morales (Almacén)",
                signer_role="Conformidad Conjunta de Constatación de Diferencias",
                signed_at="2026-08-29 11:30:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    elif code_upper == "NC":
        st = status_code.upper() if status_code else "ISSUED"
        template_key = "non_conformity_v1"
        rows = [
            {
                "finding_no": "1",
                "category": "CALIDAD DE PRODUCTO",
                "description": (
                    "Presencia de óxido y porosidad en lote de planchas laminadas L-9921"
                ),
                "evidence": "FOT-20260829-01.jpg (Muestreo 10 planchas)",
                "severity": "CRÍTICA",
                "disposition": "DEVOLUCIÓN TOTAL AL PROVEEDOR",
            },
            {
                "finding_no": "2",
                "category": "EMPAQUE Y ROTULADO",
                "description": (
                    "Falta de etiquetas de identificación con código de barras en 30 bultos"
                ),
                "evidence": "FOT-20260829-02.jpg",
                "severity": "MODERADA",
                "disposition": "RE-ETIQUETADO CON CARGO A PROVEEDOR",
            },
            {
                "finding_no": "3",
                "category": "DOCUMENTAL",
                "description": (
                    "Certificado de Calidad de Origen no coincide con número de colada entregado"
                ),
                "evidence": "DOC-CERT-COLADA-REF.pdf",
                "severity": "ALTA",
                "disposition": "SUBSANACIÓN EN PLAZO DE 24 HORAS",
            },
        ]
        if scenario == "multipage":
            for i in range(3, 20):
                rows.append(
                    {
                        "finding_no": str(i + 1),
                        "category": "CALIDAD",
                        "description": f"Desviación técnica en parámetro dimensional #{i + 1}",
                        "evidence": f"EVIDENCIA-{(i + 1):02d}.pdf",
                        "severity": "MODERADA",
                        "disposition": "CUARENTENA PREVENTIVA",
                    }
                )

        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="NC",
                type_name="Reporte de No Conformidad",
                display_code=f"PREVIEW-NC-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Acta de Recepción Origen", "value": f"REC-{branch_code}-2026-0001"},
                {"label": "Orden de Compra", "value": f"PO-{branch_code}-2026-000189"},
                {"label": "Proveedor Observado", "value": "Aceros y Derivados del Pacífico S.A.C."},
                {"label": "Lote Afectado", "value": "LOTE-2026-001 (Planchas Laminadas)"},
                {
                    "label": "Severidad Global",
                    "value": "CRÍTICA" if scenario == "critical" else "MODERADA",
                },
                {
                    "label": "Responsable de Calidad",
                    "value": "Ing. Patricia Del Solar (QA Manager)",
                },
            ],
            tables=[
                DocumentTableContext(
                    title="Hallazgos y Desviaciones Técnicas Identificadas",
                    columns=[
                        TableColumnContext(key="finding_no", label="#", align="center", width="5%"),
                        TableColumnContext(
                            key="category", label="Categoría", align="center", width="18%"
                        ),
                        TableColumnContext(
                            key="description",
                            label="Descripción del Hallazgo / Desviación",
                            align="left",
                            width="37%",
                        ),
                        TableColumnContext(
                            key="evidence", label="Evidencia", align="center", width="15%"
                        ),
                        TableColumnContext(
                            key="severity", label="Severidad", align="center", width="10%"
                        ),
                        TableColumnContext(
                            key="disposition",
                            label="Disposición Propuesta",
                            align="left",
                            width="15%",
                        ),
                    ],
                    rows=rows,
                )
            ],
            custom_content={
                "severity": "CRÍTICA" if scenario == "critical" else "MODERADA",
            },
            notes=(
                "El proveedor debe remitir su plan de acción correctiva (8D / CAPA) "
                "en un plazo no mayor a 3 días hábiles. El material queda bloqueado en "
                "zona de cuarentena hasta su resolución."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Ing. Patricia Del Solar",
                signer_role="Jefa de Aseguramiento de Calidad (QA/QC)",
                signed_at="2026-08-29 12:00:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Código documental de ingreso/recepción no soportado: {doc_code}. "
                "Soportados: ARR, CPV, REC, GRN, RDIFF, NC."
            ),
        )


@router.post(
    "/document-renderer/receiving/{doc_code}/sample",
    summary="Generate canonical sample preview for receiving document types",
    dependencies=[Depends(require_permission("document_templates.preview"))],
)
def render_receiving_sample_document(
    doc_code: str,
    scenario: str = Query(
        "basic", description="Scenario: basic, multipage, long_text, observed, partial, critical"
    ),
    status_code: Optional[str] = Query(
        None, description="Document status (e.g. SCHEDULED, INSIDE, COMPLETED, ISSUED, OPEN)"
    ),
    format: str = Query("pdf", description="Output format: pdf or html"),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Renders canonical synthetic preview for inbound receiving documents (F016)."""
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

    ctx, template_key = build_receiving_sample_context(
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


# ============================================================================
# F017: INVENTORY DOCUMENT SAMPLES & PREVIEW SCENARIOS
# ============================================================================


def build_inventory_sample_context(
    doc_code: str,
    scenario: str = "basic",
    status_code: Optional[str] = None,
    org_name: str = "Organización Logística Integral del Perú",
    tax_id: str = "20100012345",
    branch_name: str = "Sede Principal Lima",
    branch_code: str = "LIM",
    branch_address: str = "Av. Industrial 456, Parque Logístico, Callao, Lima",
    user_email: str = "gerencia.demo@logistica.local",
) -> Tuple[DocumentRenderContext, str]:
    """Builds realistic synthetic preview context for the 7 inventory documents (F017)."""
    code_upper = doc_code.upper().strip()
    is_multi = scenario.lower() in ("multipage", "multi")
    is_long = scenario.lower() in ("long_text", "long")
    is_blind = scenario.lower() in ("blind", "blind_count", "ciego")
    is_diff = scenario.lower() in ("difference", "with_differences", "discrepancy")
    rows_count = 50 if is_multi else (20 if is_long else 6)

    org_ctx = OrganizationHeaderContext(name=org_name, code="ORG-01", tax_id=tax_id)
    branch_ctx = BranchHeaderContext(name=branch_name, code=branch_code, address=branch_address)

    if code_upper in ("LBL", "LOCATION_LABEL"):
        st = status_code.upper() if status_code else "ACTIVE"
        template_key = "location_label_v1"
        loc_code = (
            "ALM01-SECTOR-A-PASILLO-01-RACK-02-NIVEL-03-POS-01"
            if is_long
            else "ALM01-Z-A-P01-R02-N03"
        )
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="LBL",
                type_name="Etiqueta de Ubicación / Pallet",
                display_code=loc_code,
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Almacén", "value": "Almacén Central de Materias Primas"},
                {"label": "Zona / Sector", "value": "Sector A (Refractarios & Minerales)"},
                {"label": "Pasillo / Rack", "value": "Pasillo 01 • Rack R-02"},
                {"label": "Nivel / Posición", "value": "Nivel N-03 • Posición P-01"},
            ],
            custom_content={
                "location": {
                    "warehouse_name": "ALMACÉN CENTRAL DE MATERIAS PRIMAS",
                    "location_code": loc_code,
                    "zone_code": "SECTOR-A",
                    "aisle": "P-01",
                    "rack": "R-02",
                    "level": "N-03",
                    "position": "POS-1",
                    "location_type": "RACK HEAVY DUTY PALLET",
                    "capacity_kg": "2,000 KG",
                }
            },
            notes="Etiqueta física de código de ubicación WMS. Lectura QR validada.",
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    elif code_upper in ("MOV", "INVENTORY_MOVEMENT"):
        st = status_code.upper() if status_code else "EXECUTED"
        template_key = "inventory_movement_v1"
        rows = [
            {
                "item_no": str(i),
                "sku": f"MAT-REF-{i:04d}",
                "description": (
                    f"Greda refractaria formulada estándar grado {i} para fundición industrial"
                    if is_long
                    else f"Ladrillo refractario de alta alúmina AL-{i:02d}"
                ),
                "source_location": f"Z-01-P01-R0{i % 3 + 1}-N01",
                "target_location": f"Z-02-P04-R0{i % 3 + 1}-N02",
                "quantity": f"{i * 25.0:.2f}",
                "uom": "UND" if i % 2 == 0 else "KG",
                "lot_number": f"LOTE-202608-{i:03d}",
                "notes": "Reubicación por optimización de pasillo",
            }
            for i in range(1, rows_count + 1)
        ]
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="MOV",
                type_name="Movimiento Interno de Inventario",
                display_code=f"PREVIEW-MOV-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Tipo de Movimiento", "value": "REUBICACIÓN INTERNA DE STOCK (SLOTTING)"},
                {"label": "Almacén", "value": "Almacén Central Callao (ALM-01)"},
                {"label": "Operador Responsable", "value": "Juan Pérez (Operador WMS)"},
                {"label": "Referencia Operativa", "value": "TASK-WMS-20260829-8812"},
            ],
            tables=[
                DocumentTableContext(
                    title="Detalle de Existencias Reubicadas",
                    columns=[
                        TableColumnContext(key="item_no", label="#", align="center", width="5%"),
                        TableColumnContext(key="sku", label="SKU", align="center", width="15%"),
                        TableColumnContext(
                            key="description", label="Descripción", align="left", width="30%"
                        ),
                        TableColumnContext(
                            key="source_location", label="Origen", align="center", width="15%"
                        ),
                        TableColumnContext(
                            key="target_location", label="Destino", align="center", width="15%"
                        ),
                        TableColumnContext(
                            key="quantity", label="Cantidad", align="right", width="10%"
                        ),
                        TableColumnContext(key="uom", label="U.M.", align="center", width="10%"),
                    ],
                    rows=rows,
                )
            ],
            notes=(
                "Movimiento interno ejecutado según directivas de balance de carga de estantería. "
                "Registrado en log inmutable del sistema."
            ),
            visual_signature=VisualSignatureContext(
                signer_name=user_email,
                signer_role="Operador WMS / Almacenes",
                signed_at="2026-08-29 11:30:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    elif code_upper in ("INV_ADJ", "ADJ", "INVENTORY_ADJUSTMENT"):
        st = status_code.upper() if status_code else "APPROVED"
        template_key = "inventory_adjustment_v1"
        rows = [
            {
                "item_no": str(i),
                "sku": f"MAT-INS-{i:04d}",
                "description": f"Cemento refractario fraguado rápido tipo CR-{i:02d}",
                "location": f"Z-01-P02-R01-N0{i % 4 + 1}",
                "qty_before": f"{100.0 + i * 10:.2f}",
                "adj_qty": f"{-(i * 2.0):.2f}" if i % 2 == 0 else f"{i * 1.5:.2f}",
                "qty_after": f"{(100.0 + i * 10) + (-(i * 2.0) if i % 2 == 0 else i * 1.5):.2f}",
                "uom": "BOL",
                "unit_cost": f"S/ {45.00 + i * 5:.2f}",
                "total_impact": (
                    f"S/ {abs((-(i * 2.0) if i % 2 == 0 else i * 1.5) * (45.00 + i * 5)):.2f}"
                ),
                "reason": (
                    "MERMA POR ROTURA DE ENVASE" if i % 2 == 0 else "REGULARIZACIÓN SOBRANTE"
                ),
            }
            for i in range(1, rows_count + 1)
        ]
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="INV_ADJ",
                type_name="Acta Oficial de Ajuste de Inventario",
                display_code=f"PREVIEW-ADJ-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {
                    "label": "Tipo de Ajuste",
                    "value": "AJUSTE POR MERMA / DESMEDRO Y REGULARIZACIÓN",
                },
                {"label": "Almacén Afectado", "value": "Almacén Central Callao (ALM-01)"},
                {"label": "Motivo / Causa", "value": "Inspección técnica trimestral de integridad"},
                {"label": "Autorización Step-Up", "value": "TOKEN MFA VALIDADO #9921-CALLAO"},
            ],
            tables=[
                DocumentTableContext(
                    title="Detalle de Existencias Ajustadas",
                    columns=[
                        TableColumnContext(key="item_no", label="#", align="center", width="4%"),
                        TableColumnContext(key="sku", label="SKU", align="center", width="12%"),
                        TableColumnContext(
                            key="description", label="Descripción", align="left", width="22%"
                        ),
                        TableColumnContext(
                            key="location", label="Ubicación", align="center", width="12%"
                        ),
                        TableColumnContext(
                            key="qty_before", label="Antes", align="right", width="8%"
                        ),
                        TableColumnContext(
                            key="adj_qty", label="Ajuste", align="right", width="8%"
                        ),
                        TableColumnContext(
                            key="qty_after", label="Después", align="right", width="8%"
                        ),
                        TableColumnContext(key="uom", label="U.M.", align="center", width="6%"),
                        TableColumnContext(
                            key="total_impact", label="Impacto (S/)", align="right", width="10%"
                        ),
                        TableColumnContext(key="reason", label="Motivo", align="left", width="10%"),
                    ],
                    rows=rows,
                )
            ],
            custom_content={
                "step_up_ref": "MFA-AUTH-20260829-9921-GERENCIA",
                "total_impact_str": "S/ 3,845.50 PEN",
            },
            notes=(
                "El presente ajuste cuenta con aprobación de Gerencia de Operaciones tras "
                "la constatación de mermas operativas durante el traslado interno. "
                "Se adjuntan informes fotográficos en el expediente digital."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Ing. Roberto Sánchez Velarde",
                signer_role="Gerente de Logística y Operaciones",
                signed_at="2026-08-29 14:00:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    elif code_upper in ("CNT", "STOCK_COUNT", "PHYSICAL_COUNT"):
        st = status_code.upper() if status_code else "IN_PROGRESS"
        template_key = "physical_count_v1"
        # In Blind count mode, system_qty is omitted!
        rows = []
        for i in range(1, rows_count + 1):
            row_dict = {
                "item_no": str(i),
                "location": f"Z-01-P01-R0{i % 3 + 1}-N0{i % 4 + 1}",
                "sku": f"MAT-MIN-{i:04d}",
                "description": f"Mineral refractario concentrado tipo M-{i:02d}",
                "uom": "KG",
                "lot_number": f"L-2026-{i:03d}",
                "counted_qty": f"{i * 100.0:.2f}" if not is_blind else "",
                "observations": "Conforme" if i % 3 != 0 else "Reconteo sugerido",
            }
            if not is_blind:
                row_dict["system_qty"] = f"{i * 100.0 + (0 if i % 3 != 0 else 5.0):.2f}"
            rows.append(row_dict)

        cols = [
            TableColumnContext(key="item_no", label="#", align="center", width="5%"),
            TableColumnContext(key="location", label="Ubicación", align="center", width="15%"),
            TableColumnContext(key="sku", label="SKU", align="center", width="15%"),
            TableColumnContext(
                key="description", label="Descripción del Ítem", align="left", width="30%"
            ),
            TableColumnContext(key="uom", label="U.M.", align="center", width="7%"),
            TableColumnContext(key="lot_number", label="Lote", align="center", width="13%"),
        ]
        if not is_blind:
            cols.append(
                TableColumnContext(key="system_qty", label="Teórico", align="right", width="10%")
            )
        cols.append(
            TableColumnContext(key="counted_qty", label="Conteo Físico", align="right", width="15%")
        )

        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="CNT",
                type_name="Planilla de Conteo Físico / Inventario Cíclico",
                display_code=f"PREVIEW-CNT-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Tipo de Conteo", "value": "INVENTARIO CÍCLICO POR ZONAS (WALL-TO-WALL)"},
                {"label": "Almacén / Sector", "value": "Almacén Central Callao • Zona 01"},
                {
                    "label": "Auditor Responsable",
                    "value": "Lic. Martín Paredes (Auditoría Interna)",
                },
                {"label": "Ronda de Conteo", "value": "Ronda 1 (Toma Principal)"},
            ],
            tables=[
                DocumentTableContext(
                    title="Planilla de Verificación Física de Existencias",
                    columns=cols,
                    rows=rows,
                )
            ],
            custom_content={
                "blind_count": is_blind,
            },
            notes=(
                "Planilla de recuento físico en almacén. El auditor debe consignar las cantidades "
                "físicas verificadas en cada posición de almacenamiento."
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    elif code_upper in ("CDIFF", "COUNT_DIFFERENCE"):
        st = status_code.upper() if status_code else "DRAFT"
        template_key = "count_difference_v1"
        rows = [
            {
                "item_no": str(i),
                "location": f"Z-01-P01-R01-N0{i:02d}",
                "sku": f"MAT-DIF-{i:04d}",
                "description": f"Insumo químico aditivo industrial QD-{i:02d}",
                "uom": "GL",
                "system_qty": f"{100.0:.2f}",
                "counted_qty": f"{95.0 if i % 2 == 0 else 104.0:.2f}",
                "difference_qty": f"{-5.0 if i % 2 == 0 else 4.0:.2f}",
                "diff_type": "FALTANTE" if i % 2 == 0 else "SOBRANTE",
                "unit_cost": f"S/ {80.00:.2f}",
                "total_variance": f"S/ {-400.00 if i % 2 == 0 else 320.00:.2f}",
                "justification": "Evaporación / Merma física"
                if i % 2 == 0
                else "Error en digitación anterior",
            }
            for i in range(1, rows_count + 1)
        ]
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="CDIFF",
                type_name="Acta de Diferencias de Conteo Físico",
                display_code=f"PREVIEW-CDIFF-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Conteo Físico Origen", "value": f"CNT-{branch_code}-2026-000045"},
                {"label": "Almacén", "value": "Almacén Central Callao (ALM-01)"},
                {"label": "Total Ítems con Desviación", "value": f"{len(rows)} Ítems Observados"},
                {"label": "Impacto Neto Valorizado", "value": "- S/ 80.00 PEN (Neto Faltante)"},
            ],
            tables=[
                DocumentTableContext(
                    title="Matriz de Desviaciones Teórico vs Conteo Físico",
                    columns=[
                        TableColumnContext(key="item_no", label="#", align="center", width="4%"),
                        TableColumnContext(
                            key="location", label="Ubicación", align="center", width="12%"
                        ),
                        TableColumnContext(key="sku", label="SKU", align="center", width="12%"),
                        TableColumnContext(
                            key="description", label="Descripción", align="left", width="22%"
                        ),
                        TableColumnContext(
                            key="system_qty", label="Teórico", align="right", width="8%"
                        ),
                        TableColumnContext(
                            key="counted_qty", label="Físico", align="right", width="8%"
                        ),
                        TableColumnContext(
                            key="difference_qty", label="Dif.", align="right", width="8%"
                        ),
                        TableColumnContext(
                            key="diff_type", label="Tipo", align="center", width="10%"
                        ),
                        TableColumnContext(
                            key="total_variance", label="Valorizado", align="right", width="10%"
                        ),
                        TableColumnContext(
                            key="justification", label="Justificación", align="left", width="14%"
                        ),
                    ],
                    rows=rows,
                )
            ],
            notes=(
                "Acta de conciliación técnica de inventario físico. Las desviaciones requieren "
                "sustento formal antes de proceder con el acta de ajuste correspondiente."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Lic. Martín Paredes",
                signer_role="Auditor de Control de Inventarios",
                signed_at="2026-08-29 17:00:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    elif code_upper in ("TRF", "TRANSFER_REQUEST", "WAREHOUSE_TRANSFER"):
        st = status_code.upper() if status_code else "IN_TRANSIT"
        template_key = "warehouse_transfer_v1"
        rows = [
            {
                "item_no": str(i),
                "sku": f"MAT-TRF-{i:04d}",
                "description": f"Carga paletizada de insumo refractario IP-{i:02d}",
                "requested_qty": f"{i * 50.0:.2f}",
                "dispatched_qty": f"{i * 50.0:.2f}",
                "uom": "UND",
                "lot_number": f"LOTE-TRF-{i:03d}",
                "origin_location": f"ALM01-Z01-R0{i % 3 + 1}",
                "dest_location": "ALM02-REC-ZONA",
                "weight_kg": f"{i * 250.0:.1f} KG",
            }
            for i in range(1, rows_count + 1)
        ]
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="TRF",
                type_name="Solicitud de Transferencia entre Almacenes",
                display_code=f"PREVIEW-TRF-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Almacén Origen", "value": "Almacén Central Callao (ALM-01)"},
                {"label": "Almacén Destino", "value": "Almacén Regional Sur Arequipa (ALM-02)"},
                {
                    "label": "Transportista / Placa",
                    "value": "Transportes Rápidos del Sur • V3B-891",
                },
                {"label": "Fecha Límite de Arribo", "value": "2026-08-31 18:00 UTC"},
            ],
            tables=[
                DocumentTableContext(
                    title="Detalle de Existencias a Transferir",
                    columns=[
                        TableColumnContext(key="item_no", label="#", align="center", width="5%"),
                        TableColumnContext(key="sku", label="SKU", align="center", width="15%"),
                        TableColumnContext(
                            key="description", label="Descripción", align="left", width="30%"
                        ),
                        TableColumnContext(
                            key="requested_qty", label="Sol.", align="right", width="10%"
                        ),
                        TableColumnContext(
                            key="dispatched_qty", label="Desp.", align="right", width="10%"
                        ),
                        TableColumnContext(key="uom", label="U.M.", align="center", width="8%"),
                        TableColumnContext(
                            key="lot_number", label="Lote", align="center", width="12%"
                        ),
                        TableColumnContext(
                            key="weight_kg", label="Peso Est.", align="right", width="10%"
                        ),
                    ],
                    rows=rows,
                )
            ],
            custom_content={
                "transfer": {
                    "origin_wh": "ALMACÉN CENTRAL CALLAO (ALM-01)",
                    "dest_wh": "ALMACÉN REGIONAL SUR AREQUIPA (ALM-02)",
                }
            },
            notes=(
                "Orden de traslado inter-sucursales sujeta a verificación en punto de control "
                "de puerta y recepción conforme en almacén de destino."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Carlos Benavides Silva",
                signer_role="Supervisor de Despacho y Flota",
                signed_at="2026-08-29 15:30:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    elif code_upper in ("TRF_REC", "TREC", "TRANSFER_RECEIPT"):
        st = status_code.upper() if status_code else "RECEIVED"
        template_key = "transfer_receipt_v1"
        rows = [
            {
                "item_no": str(i),
                "sku": f"MAT-TRF-{i:04d}",
                "description": f"Carga paletizada de insumo refractario IP-{i:02d}",
                "sent_qty": f"{i * 50.0:.2f}",
                "received_qty": f"{i * 50.0 - (2.0 if is_diff and i == 1 else 0.0):.2f}",
                "difference_qty": f"{-2.0 if is_diff and i == 1 else 0.0:.2f}",
                "uom": "UND",
                "condition": "CONFORME" if not (is_diff and i == 1) else "DAÑADO / FALTANTE",
                "lot_number": f"LOTE-TRF-{i:03d}",
                "observations": "Recibido en buen estado"
                if not (is_diff and i == 1)
                else "Envase roto en tránsito",
            }
            for i in range(1, rows_count + 1)
        ]
        ctx = DocumentRenderContext(
            organization=org_ctx,
            branch=branch_ctx,
            document=DocumentHeaderContext(
                type_code="TRF_REC",
                type_name="Acta de Recepción de Transferencia",
                display_code=f"PREVIEW-TREC-{branch_code}-2026-0001",
                status=st,
                version_number=1,
                emission_date="2026-08-29",
            ),
            metadata=DocumentMetadataContext(generated_by=user_email, template_key=template_key),
            summary_fields=[
                {"label": "Transferencia Relacionada", "value": f"TRF-{branch_code}-2026-000088"},
                {"label": "Almacén Remitente", "value": "Almacén Central Callao (ALM-01)"},
                {"label": "Almacén Receptor", "value": "Almacén Regional Sur Arequipa (ALM-02)"},
                {"label": "Guía de Remisión Transportista", "value": "GRT-001-0004912"},
            ],
            tables=[
                DocumentTableContext(
                    title="Confrontación de Cantidades Despachadas vs Recibidas",
                    columns=[
                        TableColumnContext(key="item_no", label="#", align="center", width="5%"),
                        TableColumnContext(key="sku", label="SKU", align="center", width="15%"),
                        TableColumnContext(
                            key="description", label="Descripción", align="left", width="28%"
                        ),
                        TableColumnContext(
                            key="sent_qty", label="Enviado", align="right", width="10%"
                        ),
                        TableColumnContext(
                            key="received_qty", label="Recibido", align="right", width="10%"
                        ),
                        TableColumnContext(
                            key="difference_qty", label="Dif.", align="right", width="8%"
                        ),
                        TableColumnContext(key="uom", label="U.M.", align="center", width="7%"),
                        TableColumnContext(
                            key="condition", label="Estado", align="center", width="17%"
                        ),
                    ],
                    rows=rows,
                )
            ],
            custom_content={
                "has_discrepancies": is_diff,
                "discrepancy_summary": (
                    "Se detectó 1 ítem con faltante/daño físico al momento de abrir el precinto. "
                    "Se levantó informe de avería de transporte."
                    if is_diff
                    else None
                ),
            },
            notes=(
                "Acta de conformidad de llegada de transferencia. La mercadería conforme ha sido "
                "ingresada al área de recepción para su posterior almacenamiento."
            ),
            visual_signature=VisualSignatureContext(
                signer_name="Enrique Gutiérrez Soto",
                signer_role="Jefe de Almacén Receptor (Arequipa)",
                signed_at="2026-08-29 18:00:00 UTC",
            ),
            watermark_text="VISTA PREVIA",
        )
        return ctx, template_key

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Código documental de inventario no soportado: {doc_code}. "
                "Soportados: LBL, MOV, INV_ADJ (ADJ), CNT, CDIFF, TRF, TRF_REC (TREC)."
            ),
        )


@router.post(
    "/document-renderer/inventory/{doc_code}/sample",
    summary="Generate canonical sample preview for inventory document types",
    dependencies=[Depends(require_permission("document_templates.preview"))],
)
def render_inventory_sample_document(
    doc_code: str,
    scenario: str = Query(
        "basic", description="Scenario: basic, blind, multipage, long_text, difference"
    ),
    status_code: Optional[str] = Query(
        None,
        description=(
            "Document status (e.g. ACTIVE, EXECUTED, APPROVED, IN_PROGRESS, IN_TRANSIT, RECEIVED)"
        ),
    ),
    format: str = Query("pdf", description="Output format: pdf or html"),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Renders canonical synthetic preview for inventory package documents (F017)."""
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

    ctx, template_key = build_inventory_sample_context(
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
