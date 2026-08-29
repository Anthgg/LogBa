import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- Allowed Field Types ---
ALLOWED_FIELD_TYPES = {
    "text",
    "long_text",
    "integer",
    "decimal",
    "date",
    "datetime",
    "boolean",
    "uuid",
    "enum",
    "reference",
    "file",
}


class FieldDefinition(BaseModel):
    key: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., description="Data type of the field")
    required: bool = True
    description: Optional[str] = None
    options: Optional[List[str]] = None

    @field_validator("type")
    @classmethod
    def validate_field_type(cls, v: str) -> str:
        v_lower = v.strip().lower()
        if v_lower not in ALLOWED_FIELD_TYPES:
            raise ValueError(
                f"Tipo de campo '{v}' invalido. Permitidos: {sorted(list(ALLOWED_FIELD_TYPES))}"
            )
        return v_lower


class EmissionRules(BaseModel):
    requires_organization: bool = True
    requires_branch: bool = True
    requires_warehouse: bool = False
    requires_approval: bool = False
    requires_reason: bool = False
    requires_related_resource: bool = False
    requires_attachments: bool = False
    requires_step_up: bool = False
    preserve_external_number: bool = False
    future_numbering_policy: str = "SYSTEM_INTERNAL"


# --- Document Family Schemas ---
class DocumentFamilyBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    is_active: bool = True


class DocumentFamilyCreate(DocumentFamilyBase):
    pass


class DocumentFamilyResponse(DocumentFamilyBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Retention Policy Schemas ---
class DocumentRetentionPolicyBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    retention_days: Optional[int] = None
    retain_forever: bool = False
    legal_hold_supported: bool = False
    is_active: bool = True


class DocumentRetentionPolicyCreate(DocumentRetentionPolicyBase):
    pass


class DocumentRetentionPolicyResponse(DocumentRetentionPolicyBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Document Type Version Schemas ---
class DocumentTypeVersionCreate(BaseModel):
    schema_definition: List[FieldDefinition] = Field(default_factory=list)
    emission_rules: EmissionRules = Field(default_factory=EmissionRules)
    status_definition: List[str] = Field(
        default_factory=lambda: ["DRAFT", "PENDING", "APPROVED", "ISSUED", "VOID"]
    )
    template_key: Optional[str] = None
    retention_policy_id: uuid.UUID
    read_permission: str = "documents.read"
    emit_permission: str = "documents.emit"
    download_permission: str = "documents.download"
    reprint_permission: str = "documents.reprint"
    void_permission: str = "documents.void"


class DocumentTypeVersionResponse(BaseModel):
    id: uuid.UUID
    document_type_id: uuid.UUID
    version_number: int
    schema_definition: List[Dict[str, Any]]
    emission_rules: Dict[str, Any]
    status_definition: List[str]
    template_key: Optional[str] = None
    retention_policy_id: uuid.UUID
    read_permission: str
    emit_permission: str
    download_permission: str
    reprint_permission: str
    void_permission: str
    effective_from: datetime
    effective_to: Optional[datetime] = None
    is_current: bool
    created_at: datetime
    created_by_user_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)


# --- Document Type Schemas ---
class DocumentTypeBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    family_id: uuid.UUID
    document_scope: Literal["INTERNAL", "EXTERNAL"] = "INTERNAL"
    is_active: bool = True
    phase_owner: str = "F011"


class DocumentTypeCreate(DocumentTypeBase):
    initial_version: Optional[DocumentTypeVersionCreate] = None


class DocumentTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    phase_owner: Optional[str] = None


class DocumentTypeResponse(DocumentTypeBase):
    id: uuid.UUID
    family_name: Optional[str] = None
    current_version_number: Optional[int] = None
    current_template_key: Optional[str] = None
    retention_policy_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentTypeDetailResponse(DocumentTypeResponse):
    current_version: Optional[DocumentTypeVersionResponse] = None
    versions: List[DocumentTypeVersionResponse] = Field(default_factory=list)
