"""Pydantic Document Context Schemas for Outbound Document Package (F018).

Defines strongly-typed data structures for:
1. Outbound Request (Solicitud / Pedido de Salida) - OUT_REQ / outbound_request_v1
2. Outbound Order (Orden de Salida / Despacho) - ODS / outbound_order_v1
3. Picking List (Hoja / Lista de Picking) - PICK / picking_list_v1
4. Packing List (Lista de Empaque) - PACK / packing_list_v1
5. Cargo Manifest (Manifiesto de Carga) - MNF / manifest_v1
6. Dispatch Report (Guía / Acta de Despacho) - DSP / dispatch_report_v1
7. Seal Control (Acta de Control de Precintos) - SEAL / seal_control_v1
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class OutboundItemRowContext(BaseModel):
    """Represents a product item row across outbound documents."""

    item_no: str = Field(..., description="Correlativo de ítem (e.g. '1', '2')")
    sku: str = Field(..., description="Código de producto / SKU")
    description: str = Field(..., description="Descripción detallada del material")
    requested_qty: Optional[str] = Field(None, description="Cantidad solicitada")
    authorized_qty: Optional[str] = Field(None, description="Cantidad autorizada")
    picked_qty: Optional[str] = Field(None, description="Cantidad recolectada")
    packed_qty: Optional[str] = Field(None, description="Cantidad empacada")
    uom: str = Field(..., description="Unidad de medida (e.g. UN, CAJ, KG, BOL)")
    lot_number: Optional[str] = Field(None, description="Número de lote asignado")
    serial_number: Optional[str] = Field(None, description="Número de serie de equipo")
    location_code: Optional[str] = Field(None, description="Código de ubicación física en almacén")
    observations: Optional[str] = Field(None, description="Observaciones específicas del ítem")


class OutboundPackageItemContext(BaseModel):
    """Represents an item packed within a specific box/package."""

    sku: str
    description: str
    qty: str
    uom: str
    lot_number: Optional[str] = None


class OutboundPackageContext(BaseModel):
    """Represents a box/pallet/container in Packing List or Cargo Manifest."""

    package_no: str = Field(..., description="Identificador o número de bulto (e.g. 'CX-001')")
    package_type: str = Field(
        ..., description="Tipo de empaque (e.g. 'Caja de Cartón Corrugado', 'Pallet')"
    )
    logistic_unit_code: Optional[str] = Field(None, description="Código SSCC o unidad logística")
    seal_number: Optional[str] = Field(None, description="Precinto específico de la caja/bulto")
    gross_weight_kg: str = Field(..., description="Peso bruto en kilogramos")
    dimensions_cm: Optional[str] = Field(None, description="Dimensiones L x W x H en cm")
    volume_m3: Optional[str] = Field(None, description="Volumen en metros cúbicos")
    destination_ref: Optional[str] = Field(None, description="Referencia de destino o cliente")
    items_count: Optional[int] = Field(None, description="Cantidad de ítems contenidos")
    items: Optional[List[OutboundPackageItemContext]] = Field(default_factory=list)


class OutboundTransportSnapshotContext(BaseModel):
    """Snapshot of transport details for manifest and dispatch documents."""

    carrier_name: str = Field(..., description="Razón social de la empresa transportista")
    carrier_ruc: Optional[str] = Field(None, description="RUC de la empresa transportista")
    vehicle_plate: str = Field(..., description="Placa principal de la unidad vehicular")
    trailer_plate: Optional[str] = Field(None, description="Placa de la carreta o semirremolque")
    driver_name: str = Field(..., description="Nombres completos del conductor")
    driver_dni: str = Field(..., description="Documento de identidad del conductor")
    driver_license: Optional[str] = Field(None, description="Número de licencia de conducir")
    transport_mode: Optional[str] = Field(
        "TERRESTRE PRIVADO", description="Modalidad de transporte"
    )


class OutboundSealDetailContext(BaseModel):
    """Detail of a security seal applied to a vehicle or container."""

    seal_number: str = Field(..., description="Número de serie único del precinto")
    seal_type: str = Field("BOTELLA ALTA SEGURIDAD (ISO 17712)", description="Tipo de precinto")
    applied_to: str = Field(
        ..., description="Ubicación física colocada (e.g. 'Puerta Trasera Derecha')"
    )
    applied_at: str = Field(..., description="Fecha y hora de colocación")
    applied_by: str = Field(..., description="Nombre del operador/supervisor que colocó")
    verified_at: Optional[str] = Field(None, description="Fecha y hora de verificación")
    verified_by: Optional[str] = Field(None, description="Nombre de quien verificó")
    status: str = Field("COLOCADO CONFORME", description="Estado del precinto")
    observation: Optional[str] = Field(None, description="Observaciones o notas")
    is_replacement: Optional[bool] = Field(False, description="Indica si es un reemplazo")
    previous_seal_number: Optional[str] = Field(
        None, description="Número de precinto anterior retirado"
    )
    replacement_reason: Optional[str] = Field(None, description="Motivo del reemplazo")
