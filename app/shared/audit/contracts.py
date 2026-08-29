import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol


@dataclass
class AuditContext:
    """Canonical request context for transversal audit event recording."""

    correlation_id: uuid.UUID = field(default_factory=uuid.uuid4)
    actor_type: str = "UNAUTHENTICATED"
    actor_id: Optional[uuid.UUID] = None
    session_id: Optional[uuid.UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    organization_id: Optional[uuid.UUID] = None
    branch_id: Optional[uuid.UUID] = None
    warehouse_id: Optional[uuid.UUID] = None
    request_id: Optional[str] = None
    is_test_data: bool = False


class AuditServiceProtocol(Protocol):
    """Boundary contract for the transversal audit recording service."""

    def record_event(
        self,
        context: AuditContext,
        resource_type: str,
        action: str,
        result: str,
        resource_id: Optional[uuid.UUID] = None,
        reason: Optional[str] = None,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any: ...
