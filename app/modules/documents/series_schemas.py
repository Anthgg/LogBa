import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentSeriesCreate(BaseModel):
    document_type_id: uuid.UUID = Field(
        ..., description="ID del tipo documental (alcance INTERNAL)"
    )
    branch_id: uuid.UUID = Field(..., description="ID de la sede emisora")
    period_year: int = Field(..., ge=2000, le=2100, description="Año del periodo de emisión")


class DocumentSeriesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    document_type_id: uuid.UUID
    document_type_code: Optional[str] = None
    document_type_name: Optional[str] = None
    branch_id: uuid.UUID
    branch_code: Optional[str] = None
    branch_name: Optional[str] = None
    period_year: int
    series_prefix: str
    next_correlative: int
    correlative_width: int
    is_active: bool
    is_test_data: bool
    reserved_count: int = 0
    voided_count: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentSeriesReservationCreate(BaseModel):
    quantity: int = Field(
        1, ge=1, le=500, description="Cantidad de correlativos a reservar (máximo 500)"
    )
    reason: Optional[str] = Field(
        None, max_length=255, description="Motivo operacional de la reserva"
    )


class DocumentSeriesReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    series_id: uuid.UUID
    start_correlative: int
    end_correlative: int
    quantity: int
    first_display_code: str
    last_display_code: str
    reserved_by_user_id: uuid.UUID
    reserved_by_name: Optional[str] = None
    reserved_at: datetime
    reason: Optional[str] = None
    correlation_id: Optional[uuid.UUID] = None


class DocumentSeriesNumberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    series_id: uuid.UUID
    reservation_id: uuid.UUID
    correlative: int
    display_code: str
    status: str
    reserved_at: datetime
    voided_at: Optional[datetime] = None
    voided_by_user_id: Optional[uuid.UUID] = None
    voided_by_name: Optional[str] = None
    void_reason: Optional[str] = None


class VoidDocumentNumberRequest(BaseModel):
    reason: str = Field(
        ..., min_length=3, max_length=500, description="Motivo obligatorio de la anulación"
    )


class DocumentSeriesDetailResponse(DocumentSeriesResponse):
    reservations: List[DocumentSeriesReservationResponse] = []
