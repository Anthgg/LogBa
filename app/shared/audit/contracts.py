from typing import Any, Dict, Optional, Protocol


class AuditServiceProtocol(Protocol):
    """Boundary contract for the transversal audit recording service (Target: F007)."""

    def record_event(
        self,
        actor_id: str,
        action: str,
        resource: str,
        result: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None: ...
