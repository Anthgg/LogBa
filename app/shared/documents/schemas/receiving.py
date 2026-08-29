"""Specialized Document Context Schemas for Inbound Receiving Package (F016)."""

from typing import Optional

from pydantic import BaseModel, Field


class VehicleDriverEmbed(BaseModel):
    """Embedded vehicle and carrier details for gate and receiving documents."""

    plate: str = Field(..., description="Placa vehicular de la unidad de transporte")
    driver_name: str = Field(..., description="Nombres y apellidos del conductor")
    driver_doc: Optional[str] = Field(default=None, description="DNI o Licencia de conducir")
    carrier_company: Optional[str] = Field(default=None, description="Empresa de transportes")
    seal_number: Optional[str] = Field(default=None, description="Número de precinto de seguridad")


class InboundItemEmbed(BaseModel):
    item_no: int
    sku: str
    description: str
    ordered_qty: float
    received_qty: float
    accepted_qty: Optional[float] = None
    unit: str
    lot_number: Optional[str] = None
    serial_number: Optional[str] = None
    expiry_date: Optional[str] = None
    condition: Optional[str] = "CONFORME"
    notes: Optional[str] = None


class DiscrepancyItemEmbed(BaseModel):
    item_no: int
    sku: str
    description: str
    expected_qty: float
    received_qty: float
    difference_qty: float
    difference_type: str = Field(
        ...,
        description="SHORTAGE, EXCESS, DAMAGED, WRONG_PRODUCT, MISSING_DOCUMENT, BROKEN_SEAL",
    )
    severity: Optional[str] = "MEDIA"
    observation: str
    evidence_ref: Optional[str] = None


class NonConformityFindingEmbed(BaseModel):
    finding_no: int
    category: str = Field(..., description="EMPAQUE, ESPECIFICACION, CANTIDAD, DOCUMENTAL, CALIDAD")
    description: str
    evidence_ref: Optional[str] = None
    severity: str = Field(..., description="LEVE, MODERADA, CRITICA")
    proposed_disposition: str = Field(
        ...,
        description="DEVOLUCION_PROVEEDOR, CUARENTENA, ACEPTACION_BAJO_DESCUENTO, REPROCESO",
    )
