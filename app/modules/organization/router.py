import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.modules.auth.dependencies import (
    get_audit_context,
    require_permission,
    validate_csrf,
)
from app.modules.organization.schemas import (
    BranchCreate,
    BranchResponse,
    BranchUpdate,
    EndpointPermissionMappingResponse,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    PermissionResponse,
    RoleCreate,
    RoleEffectivePermissionsResponse,
    RoleMatrixResponse,
    RolePermissionAssignRequest,
    RoleResponse,
    RoleUpdate,
    StructureResponse,
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
)
from app.modules.organization.service import (
    BranchService,
    OrganizationService,
    PermissionService,
    RoleService,
    StructureService,
    WarehouseService,
)
from app.shared.audit.contracts import AuditContext

router = APIRouter()
org_service = OrganizationService()
branch_service = BranchService()
wh_service = WarehouseService()
struct_service = StructureService()
role_service = RoleService()
perm_service = PermissionService()


# --- Structure Overview ---
@router.get(
    "/structure",
    response_model=StructureResponse,
    summary="Get complete organizational and warehouse tree",
    dependencies=[Depends(require_permission("organization.read"))],
)
def get_structure(db: Session = Depends(get_db)) -> StructureResponse:
    return struct_service.get_structure(db)


# --- Organizations ---
@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization",
    dependencies=[Depends(require_permission("organization.create")), Depends(validate_csrf)],
)
def create_organization(
    data: OrganizationCreate,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> OrganizationResponse:
    res = org_service.create_organization(db, data, context=context)
    return OrganizationResponse.model_validate(res)


@router.get(
    "/organizations",
    response_model=List[OrganizationResponse],
    summary="List organizations",
    dependencies=[Depends(require_permission("organization.read"))],
)
def list_organizations(
    db: Session = Depends(get_db),
) -> List[OrganizationResponse]:
    res = org_service.list_organizations(db)
    return [OrganizationResponse.model_validate(o) for o in res]


@router.get(
    "/organizations/{org_id}",
    response_model=OrganizationResponse,
    summary="Get organization by ID",
    dependencies=[Depends(require_permission("organization.read"))],
)
def get_organization(org_id: uuid.UUID, db: Session = Depends(get_db)) -> OrganizationResponse:
    res = org_service.get_organization(db, org_id)
    return OrganizationResponse.model_validate(res)


@router.patch(
    "/organizations/{org_id}",
    response_model=OrganizationResponse,
    summary="Update organization",
    dependencies=[Depends(require_permission("organization.update")), Depends(validate_csrf)],
)
def update_organization(
    org_id: uuid.UUID,
    data: OrganizationUpdate,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> OrganizationResponse:
    res = org_service.update_organization(db, org_id, data, context=context)
    return OrganizationResponse.model_validate(res)


@router.delete(
    "/organizations/{org_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete organization",
    dependencies=[Depends(require_permission("organization.delete")), Depends(validate_csrf)],
)
def delete_organization(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> None:
    org_service.delete_organization(db, org_id, context=context)


# --- Branches ---
@router.post(
    "/organizations/{org_id}/branches",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create branch under organization",
    dependencies=[Depends(require_permission("branch.create")), Depends(validate_csrf)],
)
def create_branch(
    org_id: uuid.UUID,
    data: BranchCreate,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> BranchResponse:
    res = branch_service.create_branch(db, org_id, data, context=context)
    return BranchResponse.model_validate(res)


@router.get(
    "/organizations/{org_id}/branches",
    response_model=List[BranchResponse],
    summary="List branches of an organization",
    dependencies=[Depends(require_permission("branch.read"))],
)
def list_branches_by_organization(
    org_id: uuid.UUID, db: Session = Depends(get_db)
) -> List[BranchResponse]:
    res = branch_service.list_branches_by_organization(db, org_id)
    return [BranchResponse.model_validate(b) for b in res]


@router.get(
    "/branches/{branch_id}",
    response_model=BranchResponse,
    summary="Get branch by ID",
    dependencies=[Depends(require_permission("branch.read"))],
)
def get_branch(branch_id: uuid.UUID, db: Session = Depends(get_db)) -> BranchResponse:
    res = branch_service.get_branch(db, branch_id)
    return BranchResponse.model_validate(res)


@router.patch(
    "/branches/{branch_id}",
    response_model=BranchResponse,
    summary="Update branch",
    dependencies=[Depends(require_permission("branch.update")), Depends(validate_csrf)],
)
def update_branch(
    branch_id: uuid.UUID,
    data: BranchUpdate,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> BranchResponse:
    res = branch_service.update_branch(db, branch_id, data, context=context)
    return BranchResponse.model_validate(res)


@router.delete(
    "/branches/{branch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete branch",
    dependencies=[Depends(require_permission("branch.delete")), Depends(validate_csrf)],
)
def delete_branch(
    branch_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> None:
    branch_service.delete_branch(db, branch_id, context=context)


# --- Warehouses ---
@router.post(
    "/branches/{branch_id}/warehouses",
    response_model=WarehouseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create warehouse under branch",
    dependencies=[Depends(require_permission("warehouse.create")), Depends(validate_csrf)],
)
def create_warehouse(
    branch_id: uuid.UUID,
    data: WarehouseCreate,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> WarehouseResponse:
    res = wh_service.create_warehouse(db, branch_id, data, context=context)
    return WarehouseResponse.model_validate(res)


@router.get(
    "/branches/{branch_id}/warehouses",
    response_model=List[WarehouseResponse],
    summary="List warehouses of a branch",
    dependencies=[Depends(require_permission("warehouse.read"))],
)
def list_warehouses_by_branch(
    branch_id: uuid.UUID, db: Session = Depends(get_db)
) -> List[WarehouseResponse]:
    res = wh_service.list_warehouses_by_branch(db, branch_id)
    return [WarehouseResponse.model_validate(w) for w in res]


@router.get(
    "/warehouses/{warehouse_id}",
    response_model=WarehouseResponse,
    summary="Get warehouse by ID",
    dependencies=[Depends(require_permission("warehouse.read"))],
)
def get_warehouse(warehouse_id: uuid.UUID, db: Session = Depends(get_db)) -> WarehouseResponse:
    res = wh_service.get_warehouse(db, warehouse_id)
    return WarehouseResponse.model_validate(res)


@router.patch(
    "/warehouses/{warehouse_id}",
    response_model=WarehouseResponse,
    summary="Update warehouse",
    dependencies=[Depends(require_permission("warehouse.update")), Depends(validate_csrf)],
)
def update_warehouse(
    warehouse_id: uuid.UUID,
    data: WarehouseUpdate,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> WarehouseResponse:
    res = wh_service.update_warehouse(db, warehouse_id, data, context=context)
    return WarehouseResponse.model_validate(res)


@router.delete(
    "/warehouses/{warehouse_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete warehouse",
    dependencies=[Depends(require_permission("warehouse.delete")), Depends(validate_csrf)],
)
def delete_warehouse(
    warehouse_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> None:
    wh_service.delete_warehouse(db, warehouse_id, context=context)


# --- Permissions ---
@router.get(
    "/permissions/endpoint-matrix",
    response_model=List[EndpointPermissionMappingResponse],
    summary="Get canonical REST endpoint-to-permission security matrix",
    dependencies=[Depends(require_permission("permissions.read"))],
)
def get_endpoint_matrix() -> List[EndpointPermissionMappingResponse]:
    return perm_service.get_endpoint_matrix()


@router.get(
    "/permissions",
    response_model=List[PermissionResponse],
    summary="List action-based permissions catalog",
    dependencies=[Depends(require_permission("permissions.read"))],
)
def list_permissions(
    category: Optional[str] = Query(None, description="Filter by permission category"),
    db: Session = Depends(get_db),
) -> List[PermissionResponse]:
    res = perm_service.list_permissions(db, category)
    return [PermissionResponse.model_validate(p) for p in res]


@router.get(
    "/permissions/{permission_id}",
    response_model=PermissionResponse,
    summary="Get permission by ID",
    dependencies=[Depends(require_permission("permissions.read"))],
)
def get_permission(permission_id: uuid.UUID, db: Session = Depends(get_db)) -> PermissionResponse:
    res = perm_service.get_permission(db, permission_id)
    return PermissionResponse.model_validate(res)


# --- Roles & Role Permissions ---
@router.get(
    "/roles/matrix",
    response_model=RoleMatrixResponse,
    summary="Get canonical roles responsibilities and SoD segregation matrix",
    dependencies=[Depends(require_permission("roles.read"))],
)
def get_role_matrix() -> RoleMatrixResponse:
    return role_service.get_matrix()


@router.post(
    "/roles",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create role",
    dependencies=[Depends(require_permission("roles.create")), Depends(validate_csrf)],
)
def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> RoleResponse:
    res = role_service.create_role(db, data, context=context)
    return RoleResponse.model_validate(res)


@router.get(
    "/roles",
    response_model=List[RoleResponse],
    summary="List roles (system and organization-scoped)",
    dependencies=[Depends(require_permission("roles.read"))],
)
def list_roles(
    organization_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db)
) -> List[RoleResponse]:
    res = role_service.list_roles(db, organization_id)
    return [RoleResponse.model_validate(r) for r in res]


@router.get(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="Get role by ID",
    dependencies=[Depends(require_permission("roles.read"))],
)
def get_role(role_id: uuid.UUID, db: Session = Depends(get_db)) -> RoleResponse:
    res = role_service.get_role(db, role_id)
    return RoleResponse.model_validate(res)


@router.patch(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="Update role",
    dependencies=[Depends(require_permission("roles.update")), Depends(validate_csrf)],
)
def update_role(
    role_id: uuid.UUID,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> RoleResponse:
    res = role_service.update_role(db, role_id, data, context=context)
    return RoleResponse.model_validate(res)


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete role",
    dependencies=[Depends(require_permission("roles.delete")), Depends(validate_csrf)],
)
def delete_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> None:
    role_service.delete_role(db, role_id, context=context)


@router.get(
    "/roles/{role_id}/permissions",
    response_model=RoleEffectivePermissionsResponse,
    summary="Get effective action permissions and SoD warnings for a role",
    dependencies=[Depends(require_permission("permissions.read"))],
)
def get_role_permissions(
    role_id: uuid.UUID, db: Session = Depends(get_db)
) -> RoleEffectivePermissionsResponse:
    return perm_service.get_role_effective_permissions(db, role_id)


@router.put(
    "/roles/{role_id}/permissions",
    response_model=RoleEffectivePermissionsResponse,
    summary="Assign/replace action permissions for a role",
    dependencies=[Depends(require_permission("permissions.assign")), Depends(validate_csrf)],
)
def assign_role_permissions(
    role_id: uuid.UUID,
    data: RolePermissionAssignRequest,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> RoleEffectivePermissionsResponse:
    return perm_service.assign_role_permissions(db, role_id, data, context=context)
