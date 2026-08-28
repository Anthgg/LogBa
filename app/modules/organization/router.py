import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.modules.organization.schemas import (
    BranchCreate,
    BranchResponse,
    BranchUpdate,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    StructureResponse,
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
)
from app.modules.organization.service import (
    BranchService,
    OrganizationService,
    StructureService,
    WarehouseService,
)

router = APIRouter(tags=["Organization & Warehouse Topology"])

org_service = OrganizationService()
branch_service = BranchService()
warehouse_service = WarehouseService()
structure_service = StructureService()


# --- Hierarchy Structure ---
@router.get("/structure", response_model=StructureResponse)
def get_logistics_structure(db: Session = Depends(get_db)):
    """Returns the full hierarchical structure (Organizations -> Branches -> Warehouses)."""
    return structure_service.get_structure(db)


# --- Organizations ---
@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(data: OrganizationCreate, db: Session = Depends(get_db)):
    return org_service.create_organization(db, data)


@router.get("/organizations", response_model=List[OrganizationResponse])
def list_organizations(db: Session = Depends(get_db)):
    return org_service.list_organizations(db)


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
def get_organization(organization_id: uuid.UUID, db: Session = Depends(get_db)):
    return org_service.get_organization(db, organization_id)


@router.patch("/organizations/{organization_id}", response_model=OrganizationResponse)
def update_organization(
    organization_id: uuid.UUID,
    data: OrganizationUpdate,
    db: Session = Depends(get_db),
):
    return org_service.update_organization(db, organization_id, data)


@router.delete(
    "/organizations/{organization_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_organization(organization_id: uuid.UUID, db: Session = Depends(get_db)):
    org_service.delete_organization(db, organization_id)
    return None


# --- Branches ---
@router.post(
    "/organizations/{organization_id}/branches",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_branch(
    organization_id: uuid.UUID,
    data: BranchCreate,
    db: Session = Depends(get_db),
):
    return branch_service.create_branch(db, organization_id, data)


@router.get(
    "/organizations/{organization_id}/branches",
    response_model=List[BranchResponse],
)
def list_branches_by_organization(organization_id: uuid.UUID, db: Session = Depends(get_db)):
    return branch_service.list_branches_by_organization(db, organization_id)


@router.get("/branches/{branch_id}", response_model=BranchResponse)
def get_branch(branch_id: uuid.UUID, db: Session = Depends(get_db)):
    return branch_service.get_branch(db, branch_id)


@router.patch("/branches/{branch_id}", response_model=BranchResponse)
def update_branch(branch_id: uuid.UUID, data: BranchUpdate, db: Session = Depends(get_db)):
    return branch_service.update_branch(db, branch_id, data)


@router.delete("/branches/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch(branch_id: uuid.UUID, db: Session = Depends(get_db)):
    branch_service.delete_branch(db, branch_id)
    return None


# --- Warehouses ---
@router.post(
    "/branches/{branch_id}/warehouses",
    response_model=WarehouseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_warehouse(
    branch_id: uuid.UUID,
    data: WarehouseCreate,
    db: Session = Depends(get_db),
):
    return warehouse_service.create_warehouse(db, branch_id, data)


@router.get(
    "/branches/{branch_id}/warehouses",
    response_model=List[WarehouseResponse],
)
def list_warehouses_by_branch(branch_id: uuid.UUID, db: Session = Depends(get_db)):
    return warehouse_service.list_warehouses_by_branch(db, branch_id)


@router.get("/warehouses/{warehouse_id}", response_model=WarehouseResponse)
def get_warehouse(warehouse_id: uuid.UUID, db: Session = Depends(get_db)):
    return warehouse_service.get_warehouse(db, warehouse_id)


@router.patch("/warehouses/{warehouse_id}", response_model=WarehouseResponse)
def update_warehouse(
    warehouse_id: uuid.UUID,
    data: WarehouseUpdate,
    db: Session = Depends(get_db),
):
    return warehouse_service.update_warehouse(db, warehouse_id, data)


@router.delete("/warehouses/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_warehouse(warehouse_id: uuid.UUID, db: Session = Depends(get_db)):
    warehouse_service.delete_warehouse(db, warehouse_id)
    return None
