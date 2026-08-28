import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- Location Schemas ---
class LocationBase(BaseModel):
    label: str = Field(..., min_length=1, max_length=150)
    address_line1: str = Field(..., min_length=1, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    district: Optional[str] = Field(None, max_length=100)
    province: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    country_code: str = Field("PE", min_length=2, max_length=2)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < -90.0 or v > 90.0):
            raise ValueError("Latitude must be between -90 and 90 degrees.")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < -180.0 or v > 180.0):
            raise ValueError("Longitude must be between -180 and 180 degrees.")
        return v


class LocationCreate(LocationBase):
    pass


class LocationResponse(LocationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --- Organization Schemas ---
class OrganizationBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    is_active: bool = True
    is_test_data: bool = False


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    is_active: Optional[bool] = None


class OrganizationResponse(OrganizationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --- Branch Schemas ---
class BranchCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    location: LocationCreate
    is_active: bool = True
    is_test_data: bool = False


class BranchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    is_active: Optional[bool] = None
    location: Optional[LocationCreate] = None


class BranchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    code: str
    name: str
    location_id: uuid.UUID
    location: Optional[LocationResponse] = None
    is_active: bool
    is_test_data: bool
    created_at: datetime
    updated_at: datetime


# --- Warehouse Schemas ---
class WarehouseCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    use_branch_location: bool = True
    custom_location: Optional[LocationCreate] = None
    is_active: bool = True
    is_test_data: bool = False


class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    is_active: Optional[bool] = None
    use_branch_location: Optional[bool] = None
    custom_location: Optional[LocationCreate] = None


class WarehouseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID
    code: str
    name: str
    location_id: uuid.UUID
    location: Optional[LocationResponse] = None
    is_active: bool
    is_test_data: bool
    created_at: datetime
    updated_at: datetime


# --- Role Schemas ---
class RoleBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    organization_id: Optional[uuid.UUID] = None
    is_system: bool = False
    is_active: bool = True
    is_test_data: bool = False


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class RoleResponse(RoleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --- Hierarchy Aggregate Schemas ---
class WarehouseHierarchyItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    is_active: bool
    is_test_data: bool
    location: Optional[LocationResponse] = None


class BranchHierarchyItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    is_active: bool
    is_test_data: bool
    location: Optional[LocationResponse] = None
    warehouses: List[WarehouseHierarchyItem] = []


class OrganizationHierarchyItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    is_active: bool
    is_test_data: bool
    branches: List[BranchHierarchyItem] = []


class StructureResponse(BaseModel):
    organizations: List[OrganizationHierarchyItem]
