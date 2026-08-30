"""Specialized Document Context Schemas for Inventory Package (F017)."""

from typing import Optional

from pydantic import BaseModel, Field


class LocationHierarchyEmbed(BaseModel):
    """Hierarchy and attributes for location label printing."""

    warehouse_code: str = Field(..., description="Código de almacén")
    warehouse_name: str = Field(..., description="Nombre del almacén")
    zone_code: str = Field(..., description="Zona o sector del almacén")
    aisle: str = Field(..., description="Pasillo")
    rack: str = Field(..., description="Estante / Rack")
    level: str = Field(..., description="Nivel / Altura")
    position: str = Field(..., description="Posición / Gaveta")
    location_code: str = Field(
        ..., description="Código canónico de ubicación, e.g. ALM01-ZONA-A-P01-R02-N03"
    )
    location_type: Optional[str] = "RACK_PALLET"
    capacity_kg: Optional[float] = None
    max_volume_m3: Optional[float] = None
    barcode_text: Optional[str] = None


class InventoryMovementItemEmbed(BaseModel):
    item_no: int
    sku: str
    description: str
    source_location: str
    target_location: str
    quantity: float
    uom: str
    lot_number: Optional[str] = None
    serial_number: Optional[str] = None
    notes: Optional[str] = None


class InventoryAdjustmentItemEmbed(BaseModel):
    item_no: int
    sku: str
    description: str
    location: str
    quantity_before: float
    adjustment_quantity: float
    quantity_after: float
    uom: str
    unit_cost: float
    total_cost_impact: float
    lot_number: Optional[str] = None
    reason: str


class PhysicalCountItemEmbed(BaseModel):
    item_no: int
    location: str
    sku: str
    description: str
    uom: str
    lot_number: Optional[str] = None
    system_qty: Optional[float] = None  # Omitted during blind counts
    counted_qty: Optional[float] = None
    difference_qty: Optional[float] = None
    observations: Optional[str] = None


class CountDifferenceItemEmbed(BaseModel):
    item_no: int
    location: str
    sku: str
    description: str
    uom: str
    system_qty: float
    counted_qty: float
    difference_qty: float
    difference_type: str = Field(..., description="SHORTAGE, OVERAGE, DAMAGE, OBSOLETE")
    unit_cost: float
    total_variance_value: float
    justification: str
    proposed_action: Optional[str] = "REGULARIZACION"


class WarehouseTransferItemEmbed(BaseModel):
    item_no: int
    sku: str
    description: str
    requested_qty: float
    dispatched_qty: float
    uom: str
    lot_number: Optional[str] = None
    origin_location: Optional[str] = None
    destination_location: Optional[str] = None
    weight_kg: Optional[float] = None


class TransferReceiptItemEmbed(BaseModel):
    item_no: int
    sku: str
    description: str
    sent_qty: float
    received_qty: float
    difference_qty: float
    uom: str
    condition: str = "CONFORME"
    lot_number: Optional[str] = None
    discrepancy_type: Optional[str] = None
    observation: Optional[str] = None
