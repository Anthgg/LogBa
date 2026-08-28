import uuid
from typing import List, Optional

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.organization.models import (
    Branch,
    OperationalLocation,
    Organization,
    Permission,
    Role,
    RolePermission,
    Warehouse,
)


class OperationalLocationRepository:
    def create(self, db: Session, location: OperationalLocation) -> OperationalLocation:
        db.add(location)
        db.flush()
        return location

    def get_by_id(self, db: Session, location_id: uuid.UUID) -> Optional[OperationalLocation]:
        return db.scalar(select(OperationalLocation).where(OperationalLocation.id == location_id))


class OrganizationRepository:
    def create(self, db: Session, organization: Organization) -> Organization:
        db.add(organization)
        db.flush()
        return organization

    def get_by_id(self, db: Session, org_id: uuid.UUID) -> Optional[Organization]:
        return db.scalar(select(Organization).where(Organization.id == org_id))

    def get_by_code(self, db: Session, code: str) -> Optional[Organization]:
        return db.scalar(select(Organization).where(Organization.code == code))

    def list_all(self, db: Session) -> List[Organization]:
        return list(db.scalars(select(Organization).order_by(Organization.created_at.desc())).all())

    def delete(self, db: Session, organization: Organization) -> None:
        db.delete(organization)
        db.flush()


class BranchRepository:
    def create(self, db: Session, branch: Branch) -> Branch:
        db.add(branch)
        db.flush()
        return branch

    def get_by_id(self, db: Session, branch_id: uuid.UUID) -> Optional[Branch]:
        return db.scalar(
            select(Branch).where(Branch.id == branch_id).options(selectinload(Branch.location))
        )

    def get_by_code(self, db: Session, org_id: uuid.UUID, code: str) -> Optional[Branch]:
        return db.scalar(
            select(Branch).where(
                Branch.organization_id == org_id,
                Branch.code == code,
            )
        )

    def list_by_organization(self, db: Session, org_id: uuid.UUID) -> List[Branch]:
        return list(
            db.scalars(
                select(Branch)
                .where(Branch.organization_id == org_id)
                .options(selectinload(Branch.location))
                .order_by(Branch.created_at.asc())
            ).all()
        )

    def count_by_organization(self, db: Session, org_id: uuid.UUID) -> int:
        query = select(Branch).where(Branch.organization_id == org_id)
        return len(list(db.scalars(query).all()))

    def delete(self, db: Session, branch: Branch) -> None:
        db.delete(branch)
        db.flush()


class WarehouseRepository:
    def create(self, db: Session, warehouse: Warehouse) -> Warehouse:
        db.add(warehouse)
        db.flush()
        return warehouse

    def get_by_id(self, db: Session, warehouse_id: uuid.UUID) -> Optional[Warehouse]:
        return db.scalar(
            select(Warehouse)
            .where(Warehouse.id == warehouse_id)
            .options(selectinload(Warehouse.location))
        )

    def get_by_code(self, db: Session, branch_id: uuid.UUID, code: str) -> Optional[Warehouse]:
        return db.scalar(
            select(Warehouse).where(
                Warehouse.branch_id == branch_id,
                Warehouse.code == code,
            )
        )

    def list_by_branch(self, db: Session, branch_id: uuid.UUID) -> List[Warehouse]:
        return list(
            db.scalars(
                select(Warehouse)
                .where(Warehouse.branch_id == branch_id)
                .options(selectinload(Warehouse.location))
                .order_by(Warehouse.created_at.asc())
            ).all()
        )

    def count_by_branch(self, db: Session, branch_id: uuid.UUID) -> int:
        query = select(Warehouse).where(Warehouse.branch_id == branch_id)
        return len(list(db.scalars(query).all()))

    def delete(self, db: Session, warehouse: Warehouse) -> None:
        db.delete(warehouse)
        db.flush()


class RoleRepository:
    def create(self, db: Session, role: Role) -> Role:
        db.add(role)
        db.flush()
        return role

    def get_by_id(self, db: Session, role_id: uuid.UUID) -> Optional[Role]:
        return db.scalar(select(Role).where(Role.id == role_id))

    def get_by_code(
        self, db: Session, code: str, organization_id: Optional[uuid.UUID] = None
    ) -> Optional[Role]:
        if organization_id is None:
            return db.scalar(
                select(Role).where(
                    Role.code == code,
                    Role.organization_id.is_(None),
                )
            )
        return db.scalar(
            select(Role).where(
                Role.code == code,
                Role.organization_id == organization_id,
            )
        )

    def list_all(self, db: Session, organization_id: Optional[uuid.UUID] = None) -> List[Role]:
        if organization_id is not None:
            stmt = (
                select(Role)
                .where(
                    or_(
                        Role.organization_id == organization_id,
                        Role.organization_id.is_(None),
                    )
                )
                .order_by(Role.is_system.desc(), Role.created_at.asc())
            )
        else:
            stmt = select(Role).order_by(Role.is_system.desc(), Role.created_at.asc())
        return list(db.scalars(stmt).all())

    def delete(self, db: Session, role: Role) -> None:
        db.delete(role)
        db.flush()


class PermissionRepository:
    def create(self, db: Session, permission: Permission) -> Permission:
        db.add(permission)
        db.flush()
        return permission

    def get_by_id(self, db: Session, permission_id: uuid.UUID) -> Optional[Permission]:
        return db.scalar(select(Permission).where(Permission.id == permission_id))

    def get_by_code(self, db: Session, code: str) -> Optional[Permission]:
        return db.scalar(select(Permission).where(Permission.code == code))

    def list_all(
        self, db: Session, category: Optional[str] = None, active_only: bool = False
    ) -> List[Permission]:
        stmt = select(Permission)
        if category:
            stmt = stmt.where(Permission.category == category)
        if active_only:
            stmt = stmt.where(Permission.is_active.is_(True))
        stmt = stmt.order_by(Permission.category.asc(), Permission.code.asc())
        return list(db.scalars(stmt).all())

    def list_by_ids(self, db: Session, permission_ids: List[uuid.UUID]) -> List[Permission]:
        if not permission_ids:
            return []
        stmt = select(Permission).where(Permission.id.in_(permission_ids))
        return list(db.scalars(stmt).all())

    def list_by_codes(self, db: Session, codes: List[str]) -> List[Permission]:
        if not codes:
            return []
        stmt = select(Permission).where(Permission.code.in_(codes))
        return list(db.scalars(stmt).all())


class RolePermissionRepository:
    def list_permissions_by_role(self, db: Session, role_id: uuid.UUID) -> List[Permission]:
        stmt = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id, Permission.is_active.is_(True))
            .order_by(Permission.category.asc(), Permission.code.asc())
        )
        return list(db.scalars(stmt).all())

    def set_role_permissions(
        self, db: Session, role_id: uuid.UUID, permission_ids: List[uuid.UUID]
    ) -> List[Permission]:
        # Delete existing role permissions
        db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        db.flush()

        # Insert new role permissions
        for pid in set(permission_ids):
            rp = RolePermission(role_id=role_id, permission_id=pid)
            db.add(rp)
        db.flush()

        return self.list_permissions_by_role(db, role_id)


class StructureRepository:
    def get_full_hierarchy(self, db: Session) -> List[Organization]:
        stmt = (
            select(Organization)
            .options(
                selectinload(Organization.branches).selectinload(Branch.location),
                selectinload(Organization.branches)
                .selectinload(Branch.warehouses)
                .selectinload(Warehouse.location),
            )
            .order_by(Organization.created_at.asc())
        )
        return list(db.scalars(stmt).all())
