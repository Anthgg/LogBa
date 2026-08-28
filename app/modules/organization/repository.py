import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.organization.models import (
    Branch,
    OperationalLocation,
    Organization,
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
