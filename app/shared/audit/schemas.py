import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditEventBase(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    actor_type: str
    actor_id: Optional[uuid.UUID] = None
    session_id: Optional[uuid.UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    organization_id: Optional[uuid.UUID] = None
    branch_id: Optional[uuid.UUID] = None
    warehouse_id: Optional[uuid.UUID] = None
    resource_type: str
    resource_id: Optional[uuid.UUID] = None
    action: str
    result: str
    reason: Optional[str] = None
    correlation_id: uuid.UUID
    request_id: Optional[str] = None
    is_test_data: bool


class AuditEventResponse(AuditEventBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AuditEventDetailResponse(AuditEventBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    before_data: Optional[Dict[str, Any]] = None
    after_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata_")


class AuditListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[AuditEventResponse]
