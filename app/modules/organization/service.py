import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.core.rbac import AuthorizationContext
from app.modules.organization.matrix import (
    SOD_CONFLICTS_DATA,
    get_canonical_matrix_data,
)
from app.modules.organization.models import (
    Branch,
    OperationalLocation,
    Organization,
    Permission,
    Role,
    Warehouse,
)
from app.modules.organization.permissions_catalog import ENDPOINT_PERMISSION_MATRIX
from app.modules.organization.repository import (
    BranchRepository,
    OperationalLocationRepository,
    OrganizationRepository,
    PermissionRepository,
    RolePermissionRepository,
    RoleRepository,
    StructureRepository,
    WarehouseRepository,
)
from app.modules.organization.schemas import (
    BranchCreate,
    BranchUpdate,
    EndpointPermissionMappingResponse,
    OrganizationCreate,
    OrganizationHierarchyItem,
    OrganizationUpdate,
    PermissionResponse,
    RoleCreate,
    RoleEffectivePermissionsResponse,
    RoleMatrixResponse,
    RolePermissionAssignRequest,
    RoleUpdate,
    SodConflictItem,
    StructureResponse,
    WarehouseCreate,
    WarehouseUpdate,
)

settings = get_settings()


class OrganizationService:
    def __init__(self) -> None:
        self.org_repo = OrganizationRepository()
        self.branch_repo = BranchRepository()

    def create_organization(self, db: Session, data: OrganizationCreate) -> Organization:
        if data.is_test_data and settings.is_production:
            raise ForbiddenError(
                message="Synthetic test data cannot be created in production environment.",
                code="SYNTHETIC_DATA_FORBIDDEN_IN_PRODUCTION",
            )

        existing = self.org_repo.get_by_code(db, data.code)
        if existing:
            raise ConflictError(
                message=f"Organization with code '{data.code}' already exists.",
                code="DUPLICATE_ORGANIZATION_CODE",
                details={"code": data.code},
            )

        org = Organization(
            code=data.code,
            name=data.name,
            is_active=data.is_active,
            is_test_data=data.is_test_data,
        )
        self.org_repo.create(db, org)
        db.commit()
        db.refresh(org)
        return org

    def get_organization(self, db: Session, org_id: uuid.UUID) -> Organization:
        org = self.org_repo.get_by_id(db, org_id)
        if not org:
            raise NotFoundError(
                message="Organization not found.",
                code="ORGANIZATION_NOT_FOUND",
                details={"organization_id": str(org_id)},
            )
        return org

    def list_organizations(self, db: Session) -> List[Organization]:
        return self.org_repo.list_all(db)

    def update_organization(
        self, db: Session, org_id: uuid.UUID, data: OrganizationUpdate
    ) -> Organization:
        org = self.get_organization(db, org_id)
        if data.name is not None:
            org.name = data.name
        if data.is_active is not None:
            org.is_active = data.is_active
        db.commit()
        db.refresh(org)
        return org

    def delete_organization(self, db: Session, org_id: uuid.UUID) -> None:
        org = self.get_organization(db, org_id)
        branch_count = self.branch_repo.count_by_organization(db, org_id)
        if branch_count > 0:
            raise ConflictError(
                message="No se puede eliminar la organización porque contiene sedes asociadas.",
                code="ORGANIZATION_HAS_BRANCHES",
                details={"organization_id": str(org_id), "branch_count": branch_count},
            )
        self.org_repo.delete(db, org)
        db.commit()


class BranchService:
    def __init__(self) -> None:
        self.org_repo = OrganizationRepository()
        self.branch_repo = BranchRepository()
        self.loc_repo = OperationalLocationRepository()
        self.warehouse_repo = WarehouseRepository()

    def create_branch(self, db: Session, org_id: uuid.UUID, data: BranchCreate) -> Branch:
        org = self.org_repo.get_by_id(db, org_id)
        if not org:
            raise NotFoundError(
                message="Organization not found.",
                code="ORGANIZATION_NOT_FOUND",
                details={"organization_id": str(org_id)},
            )

        if data.is_test_data and settings.is_production:
            raise ForbiddenError(
                message="Synthetic test data cannot be created in production environment.",
                code="SYNTHETIC_DATA_FORBIDDEN_IN_PRODUCTION",
            )

        existing = self.branch_repo.get_by_code(db, org_id, data.code)
        if existing:
            raise ConflictError(
                message=f"Branch with code '{data.code}' already exists in this organization.",
                code="DUPLICATE_BRANCH_CODE",
                details={"code": data.code, "organization_id": str(org_id)},
            )

        location = OperationalLocation(
            label=data.location.label,
            address_line1=data.location.address_line1,
            address_line2=data.location.address_line2,
            district=data.location.district,
            province=data.location.province,
            department=data.location.department,
            country_code=data.location.country_code,
            latitude=data.location.latitude,
            longitude=data.location.longitude,
        )
        self.loc_repo.create(db, location)

        branch = Branch(
            organization_id=org_id,
            code=data.code,
            name=data.name,
            location_id=location.id,
            is_active=data.is_active,
            is_test_data=data.is_test_data,
        )
        self.branch_repo.create(db, branch)
        db.commit()
        db.refresh(branch)
        return branch

    def get_branch(self, db: Session, branch_id: uuid.UUID) -> Branch:
        branch = self.branch_repo.get_by_id(db, branch_id)
        if not branch:
            raise NotFoundError(
                message="Branch not found.",
                code="BRANCH_NOT_FOUND",
                details={"branch_id": str(branch_id)},
            )
        return branch

    def list_branches_by_organization(self, db: Session, org_id: uuid.UUID) -> List[Branch]:
        org = self.org_repo.get_by_id(db, org_id)
        if not org:
            raise NotFoundError(
                message="Organization not found.",
                code="ORGANIZATION_NOT_FOUND",
                details={"organization_id": str(org_id)},
            )
        return self.branch_repo.list_by_organization(db, org_id)

    def update_branch(self, db: Session, branch_id: uuid.UUID, data: BranchUpdate) -> Branch:
        branch = self.get_branch(db, branch_id)
        if data.name is not None:
            branch.name = data.name
        if data.is_active is not None:
            branch.is_active = data.is_active
        if data.location is not None and branch.location:
            loc = branch.location
            loc.label = data.location.label
            loc.address_line1 = data.location.address_line1
            loc.address_line2 = data.location.address_line2
            loc.district = data.location.district
            loc.province = data.location.province
            loc.department = data.location.department
            loc.country_code = data.location.country_code
            loc.latitude = data.location.latitude
            loc.longitude = data.location.longitude

        db.commit()
        db.refresh(branch)
        return branch

    def delete_branch(self, db: Session, branch_id: uuid.UUID) -> None:
        branch = self.get_branch(db, branch_id)
        warehouse_count = self.warehouse_repo.count_by_branch(db, branch_id)
        if warehouse_count > 0:
            raise ConflictError(
                message="No se puede eliminar la sede porque contiene almacenes asociados.",
                code="BRANCH_HAS_WAREHOUSES",
                details={"branch_id": str(branch_id), "warehouse_count": warehouse_count},
            )
        self.branch_repo.delete(db, branch)
        db.commit()


class WarehouseService:
    def __init__(self) -> None:
        self.branch_repo = BranchRepository()
        self.warehouse_repo = WarehouseRepository()
        self.loc_repo = OperationalLocationRepository()

    def create_warehouse(
        self, db: Session, branch_id: uuid.UUID, data: WarehouseCreate
    ) -> Warehouse:
        branch = self.branch_repo.get_by_id(db, branch_id)
        if not branch:
            raise NotFoundError(
                message="Branch not found.",
                code="BRANCH_NOT_FOUND",
                details={"branch_id": str(branch_id)},
            )

        if data.is_test_data and settings.is_production:
            raise ForbiddenError(
                message="Synthetic test data cannot be created in production environment.",
                code="SYNTHETIC_DATA_FORBIDDEN_IN_PRODUCTION",
            )

        existing = self.warehouse_repo.get_by_code(db, branch_id, data.code)
        if existing:
            raise ConflictError(
                message=f"Warehouse with code '{data.code}' already exists in this branch.",
                code="DUPLICATE_WAREHOUSE_CODE",
                details={"code": data.code, "branch_id": str(branch_id)},
            )

        if data.use_branch_location:
            location_id = branch.location_id
        else:
            if not data.custom_location:
                raise ValidationError(
                    message="Custom location must be provided when use_branch_location is false.",
                    code="CUSTOM_LOCATION_REQUIRED",
                )
            custom_loc = OperationalLocation(
                label=data.custom_location.label,
                address_line1=data.custom_location.address_line1,
                address_line2=data.custom_location.address_line2,
                district=data.custom_location.district,
                province=data.custom_location.province,
                department=data.custom_location.department,
                country_code=data.custom_location.country_code,
                latitude=data.custom_location.latitude,
                longitude=data.custom_location.longitude,
            )
            self.loc_repo.create(db, custom_loc)
            location_id = custom_loc.id

        warehouse = Warehouse(
            organization_id=branch.organization_id,
            branch_id=branch_id,
            code=data.code,
            name=data.name,
            location_id=location_id,
            is_active=data.is_active,
            is_test_data=data.is_test_data,
        )
        self.warehouse_repo.create(db, warehouse)
        db.commit()
        db.refresh(warehouse)
        return warehouse

    def get_warehouse(self, db: Session, warehouse_id: uuid.UUID) -> Warehouse:
        warehouse = self.warehouse_repo.get_by_id(db, warehouse_id)
        if not warehouse:
            raise NotFoundError(
                message="Warehouse not found.",
                code="WAREHOUSE_NOT_FOUND",
                details={"warehouse_id": str(warehouse_id)},
            )
        return warehouse

    def list_warehouses_by_branch(self, db: Session, branch_id: uuid.UUID) -> List[Warehouse]:
        branch = self.branch_repo.get_by_id(db, branch_id)
        if not branch:
            raise NotFoundError(
                message="Branch not found.",
                code="BRANCH_NOT_FOUND",
                details={"branch_id": str(branch_id)},
            )
        return self.warehouse_repo.list_by_branch(db, branch_id)

    def update_warehouse(
        self, db: Session, warehouse_id: uuid.UUID, data: WarehouseUpdate
    ) -> Warehouse:
        warehouse = self.get_warehouse(db, warehouse_id)
        if data.name is not None:
            warehouse.name = data.name
        if data.is_active is not None:
            warehouse.is_active = data.is_active

        if data.use_branch_location is True:
            branch = self.branch_repo.get_by_id(db, warehouse.branch_id)
            if branch:
                warehouse.location_id = branch.location_id
        elif data.custom_location is not None:
            loc = warehouse.location
            if loc and warehouse.location_id != warehouse.branch.location_id:
                loc.label = data.custom_location.label
                loc.address_line1 = data.custom_location.address_line1
                loc.address_line2 = data.custom_location.address_line2
                loc.district = data.custom_location.district
                loc.province = data.custom_location.province
                loc.department = data.custom_location.department
                loc.country_code = data.custom_location.country_code
                loc.latitude = data.custom_location.latitude
                loc.longitude = data.custom_location.longitude
            else:
                new_loc = OperationalLocation(
                    label=data.custom_location.label,
                    address_line1=data.custom_location.address_line1,
                    address_line2=data.custom_location.address_line2,
                    district=data.custom_location.district,
                    province=data.custom_location.province,
                    department=data.custom_location.department,
                    country_code=data.custom_location.country_code,
                    latitude=data.custom_location.latitude,
                    longitude=data.custom_location.longitude,
                )
                self.loc_repo.create(db, new_loc)
                warehouse.location_id = new_loc.id

        db.commit()
        db.refresh(warehouse)
        return warehouse

    def delete_warehouse(self, db: Session, warehouse_id: uuid.UUID) -> None:
        warehouse = self.get_warehouse(db, warehouse_id)
        self.warehouse_repo.delete(db, warehouse)
        db.commit()


class RoleService:
    def __init__(self) -> None:
        self.role_repo = RoleRepository()
        self.org_repo = OrganizationRepository()

    def create_role(self, db: Session, data: RoleCreate) -> Role:
        if data.organization_id is not None:
            org = self.org_repo.get_by_id(db, data.organization_id)
            if not org:
                raise NotFoundError(
                    message="Organization not found for role scoping.",
                    code="ORGANIZATION_NOT_FOUND",
                    details={"organization_id": str(data.organization_id)},
                )

        if data.is_test_data and settings.is_production:
            raise ForbiddenError(
                message="Synthetic test data cannot be created in production environment.",
                code="SYNTHETIC_DATA_FORBIDDEN_IN_PRODUCTION",
            )

        existing = self.role_repo.get_by_code(db, data.code, data.organization_id)
        if existing:
            raise ConflictError(
                message=f"Role with code '{data.code}' already exists.",
                code="DUPLICATE_ROLE_CODE",
                details={"code": data.code},
            )

        role = Role(
            organization_id=data.organization_id,
            code=data.code,
            name=data.name,
            description=data.description,
            is_system=data.is_system,
            is_active=data.is_active,
            is_test_data=data.is_test_data,
        )
        self.role_repo.create(db, role)
        db.commit()
        db.refresh(role)
        return role

    def get_role(self, db: Session, role_id: uuid.UUID) -> Role:
        role = self.role_repo.get_by_id(db, role_id)
        if not role:
            raise NotFoundError(
                message="Role not found.",
                code="ROLE_NOT_FOUND",
                details={"role_id": str(role_id)},
            )
        return role

    def list_roles(self, db: Session, organization_id: Optional[uuid.UUID] = None) -> List[Role]:
        return self.role_repo.list_all(db, organization_id)

    def update_role(self, db: Session, role_id: uuid.UUID, data: RoleUpdate) -> Role:
        role = self.get_role(db, role_id)
        if data.name is not None:
            role.name = data.name
        if data.description is not None:
            role.description = data.description
        if data.is_active is not None:
            role.is_active = data.is_active
        db.commit()
        db.refresh(role)
        return role

    def delete_role(self, db: Session, role_id: uuid.UUID) -> None:
        role = self.get_role(db, role_id)
        if role.is_system:
            raise ConflictError(
                message="Los roles base del sistema están protegidos y no pueden ser eliminados.",
                code="SYSTEM_ROLE_PROTECTED",
                details={"role_id": str(role_id), "code": role.code},
            )
        self.role_repo.delete(db, role)
        db.commit()

    def get_matrix(self) -> RoleMatrixResponse:
        return get_canonical_matrix_data()


class PermissionService:
    def __init__(self) -> None:
        self.perm_repo = PermissionRepository()
        self.role_perm_repo = RolePermissionRepository()
        self.role_repo = RoleRepository()

    def list_permissions(self, db: Session, category: Optional[str] = None) -> List[Permission]:
        return self.perm_repo.list_all(db, category=category, active_only=True)

    def get_permission(self, db: Session, permission_id: uuid.UUID) -> Permission:
        perm = self.perm_repo.get_by_id(db, permission_id)
        if not perm:
            raise NotFoundError(
                message="Permission not found.",
                code="PERMISSION_NOT_FOUND",
                details={"permission_id": str(permission_id)},
            )
        return perm

    def get_role_effective_permissions(
        self, db: Session, role_id: uuid.UUID
    ) -> RoleEffectivePermissionsResponse:
        role = self.role_repo.get_by_id(db, role_id)
        if not role:
            raise NotFoundError(
                message="Role not found.",
                code="ROLE_NOT_FOUND",
                details={"role_id": str(role_id)},
            )

        perms = self.role_perm_repo.list_permissions_by_role(db, role_id)
        perm_responses = [PermissionResponse.model_validate(p) for p in perms]
        perm_codes = [p.code for p in perms]

        # Analyze SoD warnings on current assigned permissions
        sod_warnings: List[SodConflictItem] = []
        for conflict in SOD_CONFLICTS_DATA:
            role_a = conflict["role_a"]
            role_b = conflict["role_b"]
            # Detect cross-domain permission accumulation
            has_domain_a = any(c.startswith(role_a.lower()) for c in perm_codes)
            has_domain_b = any(c.startswith(role_b.lower()) for c in perm_codes)
            if has_domain_a and has_domain_b:
                sod_warnings.append(
                    SodConflictItem(
                        role_a=role_a,
                        role_b=role_b,
                        conflict_level=conflict["conflict_level"],
                        reason=conflict["reason"],
                        policy=conflict["policy"],
                    )
                )

        return RoleEffectivePermissionsResponse(
            role_id=role.id,
            role_code=role.code,
            role_name=role.name,
            is_system=role.is_system,
            permissions=perm_responses,
            effective_codes=perm_codes,
            sod_warnings=sod_warnings,
        )

    def assign_role_permissions(
        self, db: Session, role_id: uuid.UUID, data: RolePermissionAssignRequest
    ) -> RoleEffectivePermissionsResponse:
        role = self.role_repo.get_by_id(db, role_id)
        if not role:
            raise NotFoundError(
                message="Role not found.",
                code="ROLE_NOT_FOUND",
                details={"role_id": str(role_id)},
            )

        # Resolve target permission IDs
        target_perm_ids: List[uuid.UUID] = []
        if data.permission_ids is not None:
            found_perms = self.perm_repo.list_by_ids(db, data.permission_ids)
            if len(found_perms) != len(data.permission_ids):
                found_ids = {p.id for p in found_perms}
                missing = [str(pid) for pid in data.permission_ids if pid not in found_ids]
                raise ValidationError(
                    message="One or more specified permission IDs were not found in the catalog.",
                    code="PERMISSION_NOT_FOUND",
                    details={"missing_permission_ids": missing},
                )
            target_perm_ids = [p.id for p in found_perms]
        elif data.permission_codes is not None:
            found_perms = self.perm_repo.list_by_codes(db, data.permission_codes)
            if len(found_perms) != len(data.permission_codes):
                found_codes = {p.code for p in found_perms}
                missing_codes = [c for c in data.permission_codes if c not in found_codes]
                raise ValidationError(
                    message="One or more specified permission codes were not found in the catalog.",
                    code="PERMISSION_NOT_FOUND",
                    details={"missing_permission_codes": missing_codes},
                )
            target_perm_ids = [p.id for p in found_perms]

        # Invariant: AUDITOR cannot be assigned dangerous operational mutations
        if role.code == "AUDITOR":
            assigned_perms = self.perm_repo.list_by_ids(db, target_perm_ids)
            dangerous_actions = {
                "create",
                "update",
                "delete",
                "adjust",
                "release",
                "assign",
                "void",
            }
            violations = [p.code for p in assigned_perms if p.action in dangerous_actions]
            if violations:
                raise ConflictError(
                    message="Auditor profile is read-only and cannot have operational mutations.",
                    code="AUDITOR_MUTATION_FORBIDDEN",
                    details={"violating_permissions": violations},
                )

        self.role_perm_repo.set_role_permissions(db, role_id, target_perm_ids)
        db.commit()

        return self.get_role_effective_permissions(db, role_id)

    def create_authorization_context(
        self, db: Session, role_ids: List[uuid.UUID], org_id: Optional[uuid.UUID] = None
    ) -> AuthorizationContext:
        """Create an AuthorizationContext instance for domain evaluation."""
        if not role_ids:
            return AuthorizationContext(is_active=False)

        role_codes: List[str] = []
        all_perms: set[str] = set()

        for rid in role_ids:
            role = self.role_repo.get_by_id(db, rid)
            if role and role.is_active:
                role_codes.append(role.code)
                perms = self.role_perm_repo.list_permissions_by_role(db, rid)
                for p in perms:
                    if p.is_active:
                        all_perms.add(p.code)

        return AuthorizationContext(
            role_ids=role_ids,
            role_codes=role_codes,
            permissions=all_perms,
            organization_id=org_id,
            is_active=len(role_codes) > 0,
        )

    def get_endpoint_matrix(self) -> List[EndpointPermissionMappingResponse]:
        return [
            EndpointPermissionMappingResponse(
                endpoint=m["endpoint"],
                method=m["method"],
                required_permission=m["permission"],
                phase=m["phase"],
            )
            for m in ENDPOINT_PERMISSION_MATRIX
        ]


class StructureService:
    def __init__(self) -> None:
        self.struct_repo = StructureRepository()

    def get_structure(self, db: Session) -> StructureResponse:
        orgs = self.struct_repo.get_full_hierarchy(db)
        items = [OrganizationHierarchyItem.model_validate(org) for org in orgs]
        return StructureResponse(organizations=items)
