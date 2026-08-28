import uuid
from typing import List

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.modules.organization.models import (
    Branch,
    OperationalLocation,
    Organization,
    Warehouse,
)
from app.modules.organization.repository import (
    BranchRepository,
    OperationalLocationRepository,
    OrganizationRepository,
    StructureRepository,
    WarehouseRepository,
)
from app.modules.organization.schemas import (
    BranchCreate,
    BranchUpdate,
    OrganizationCreate,
    OrganizationHierarchyItem,
    OrganizationUpdate,
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

        # Create location entity
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

        # Location Resolution
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


class StructureService:
    def __init__(self) -> None:
        self.struct_repo = StructureRepository()

    def get_structure(self, db: Session) -> StructureResponse:
        orgs = self.struct_repo.get_full_hierarchy(db)
        items = [OrganizationHierarchyItem.model_validate(org) for org in orgs]
        return StructureResponse(organizations=items)
