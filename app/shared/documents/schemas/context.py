"""Canonical Document Render Context Schemas."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OrganizationHeaderContext(BaseModel):
    name: str = Field(..., description="Legal or commercial name")
    code: Optional[str] = Field(default=None, description="Organization code")
    tax_id: Optional[str] = Field(default=None, description="Tax ID / RUC")
    logo_base64: Optional[str] = Field(default=None, description="Base64 data URI PNG/SVG logo")


class BranchHeaderContext(BaseModel):
    name: str = Field(..., description="Branch / Sede name")
    code: str = Field(..., description="Branch code")
    address: Optional[str] = Field(default=None, description="Physical location address")


class DocumentHeaderContext(BaseModel):
    type_code: str = Field(..., description="Document type code, e.g. PO, GRN")
    type_name: str = Field(..., description="Human readable document type name")
    display_code: str = Field(
        ..., description="Official canonical document code, e.g. PO-DEMO-LIM-2026-000001"
    )
    status: str = Field(default="DRAFT", description="DRAFT, APPROVED, ISSUED, VOID")
    version_number: int = Field(default=1, description="Catalog version number")
    emission_date: Optional[str] = Field(default=None, description="Emission date in ISO format")


class TableColumnContext(BaseModel):
    key: str
    label: str
    align: str = "left"  # left, right, center
    width: Optional[str] = None  # e.g. 10%, 40%


class TableRowContext(BaseModel):
    cells: Dict[str, Any]


class DocumentTableContext(BaseModel):
    title: Optional[str] = None
    columns: List[TableColumnContext] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    summary_rows: Optional[List[Dict[str, Any]]] = None


class VisualSignatureContext(BaseModel):
    signer_name: str
    signer_role: str
    signer_id: Optional[str] = None
    signed_at: Optional[str] = None
    signature_image_base64: Optional[str] = None  # Optional PNG signature drawing


class DocumentMetadataContext(BaseModel):
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    generated_by: Optional[str] = None
    correlation_id: Optional[str] = None
    template_key: str = "base_document_v1"
    template_version: str = "1.0.0"
    renderer_name: str = "WeasyPrint"
    renderer_version: str = "69.0"


class DocumentRenderContext(BaseModel):
    """Complete structured context consumed by the rendering engine."""

    organization: OrganizationHeaderContext
    branch: BranchHeaderContext
    document: DocumentHeaderContext
    metadata: DocumentMetadataContext
    summary_fields: List[Dict[str, str]] = Field(
        default_factory=list, description="Key-value pairs for metadata grid"
    )
    tables: List[DocumentTableContext] = Field(default_factory=list)
    notes: Optional[str] = None
    custom_content: Dict[str, Any] = Field(default_factory=dict)
    visual_signature: Optional[VisualSignatureContext] = None
    watermark_text: Optional[str] = None  # e.g. BORRADOR, ANULADO
    snapshot_hash: Optional[str] = None  # Populated deterministically before rendering
    qr_data_uri: Optional[str] = None  # Populated dynamically by QR service
