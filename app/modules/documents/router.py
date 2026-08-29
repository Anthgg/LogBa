import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
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
