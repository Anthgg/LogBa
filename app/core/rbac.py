import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Set

from app.core.errors import ForbiddenError


@dataclass
class AuthorizationContext:
    """Canonical domain representation of an authorization context.

    Enforces DEFAULT DENY: any unknown, inactive, or unassigned action
    is strictly rejected.
    """

    role_ids: List[uuid.UUID] = field(default_factory=list)
    role_codes: List[str] = field(default_factory=list)
    permissions: Set[str] = field(default_factory=set)
    organization_id: Optional[uuid.UUID] = None
    is_active: bool = True

    def has_permission(self, permission_code: str) -> bool:
        """Evaluate if the current context possesses the specified permission."""
        if not self.is_active:
            return False
        if not permission_code:
            return False
        return permission_code.strip().lower() in {p.lower() for p in self.permissions}

    def require_permission(self, permission_code: str) -> None:
        """Assert permission existence under default-deny policy.

        Raises ForbiddenError (HTTP 403) with code 'PERMISSION_DENIED' on failure.
        """
        if not self.has_permission(permission_code):
            raise ForbiddenError(
                message=f"Access denied: missing required permission '{permission_code}'.",
                code="PERMISSION_DENIED",
                details={"required_permission": permission_code},
            )
