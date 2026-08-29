"""Specialized Document Context Schemas for Purchasing Package (F015)."""

from typing import List, Optional

from pydantic import BaseModel, Field


class SupplierContactEmbed(BaseModel):
    """Embedded supplier information for procurement document rendering."""

    name: str = Field(..., description="Razón Social / Nombre Comercial del Proveedor")
    tax_id: Optional[str] = Field(default=None, description="RUC / Tax ID del Proveedor")
    address: Optional[str] = Field(default=None, description="Dirección legal o fiscal")
    contact_name: Optional[str] = Field(default=None, description="Persona de contacto")
    email: Optional[str] = Field(default=None, description="Correo electrónico de contacto")
    phone: Optional[str] = Field(default=None, description="Teléfono de contacto")


class RequisitionItemEmbed(BaseModel):
    item_no: int
    sku: Optional[str] = None
    description: str
    quantity: float
    unit: str
    required_date: Optional[str] = None
    notes: Optional[str] = None


class RFQItemEmbed(BaseModel):
    item_no: int
    sku: Optional[str] = None
    description: str
    quantity: float
    unit: str
    technical_spec: Optional[str] = None
    target_date: Optional[str] = None


class ComparativeSupplierOffer(BaseModel):
    supplier_name: str
    supplier_tax_id: Optional[str] = None
    unit_price: float
    total_price: float
    delivery_days: int
    payment_terms: str
    warranty: Optional[str] = None
    rank_score: Optional[str] = None  # Pre-calculated presentation score (e.g. 1er Lugar / 94 pts)
    is_recommended: bool = False


class ComparativeRowEmbed(BaseModel):
    item_no: int
    sku: Optional[str] = None
    description: str
    quantity: float
    unit: str
    offers: List[ComparativeSupplierOffer] = Field(default_factory=list)


class PurchaseOrderItemEmbed(BaseModel):
    item_no: int
    sku: Optional[str] = None
    description: str
    quantity: float
    unit: str
    unit_price: float
    subtotal: float
    delivery_date: Optional[str] = None
    specifications: Optional[str] = None


class DeliveryScheduleEmbed(BaseModel):
    installment_no: int
    scheduled_date: str
    quantity: float
    destination_branch_or_warehouse: str
    notes: Optional[str] = None
