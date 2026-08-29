"""Template manifest schema and metadata definition."""

from typing import List

from pydantic import BaseModel, Field


class TemplateManifest(BaseModel):
    """Metadata defining a document rendering template."""

    template_key: str = Field(
        ..., description="Unique immutable template identifier, e.g. base_document_v1"
    )
    family: str = Field(
        ...,
        description="Template family (base, purchasing, receiving, inventory, outbound, transport)",
    )
    version: str = Field(..., description="Semantic version of template, e.g. 1.0.0")
    title: str = Field(..., description="Human-readable title")
    description: str = Field(..., description="Detailed description of layout and intended usage")
    page_size: str = Field(default="A4", description="Standard page size: A4, LETTER")
    orientation: str = Field(default="portrait", description="portrait or landscape")
    supported_renderer: str = Field(
        default="WeasyPrint", description="Underlying PDF rendering engine"
    )
    required_context_fields: List[str] = Field(
        default_factory=list, description="Mandatory top-level context keys"
    )
    supported_statuses: List[str] = Field(
        default_factory=lambda: ["DRAFT", "APPROVED", "ISSUED", "VOID"],
        description="Status values handled by template",
    )
    created_at: str = Field(default="2026-08-29T00:00:00Z")
