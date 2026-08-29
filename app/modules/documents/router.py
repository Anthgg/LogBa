import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.modules.auth.dependencies import (
    get_audit_context,
    require_permission,
    validate_csrf,
)
from app.modules.documents.models import DocumentType
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
