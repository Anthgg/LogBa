import uuid

from fastapi import Request

from app.shared.audit.contracts import AuditContext


def get_audit_context(request: Request) -> AuditContext:
    """Extract standard request metadata into an AuditContext.

    Pre-F008: actor_type is strictly UNAUTHENTICATED, actor_id and session_id are None.
    Zero fake users or mock headers.
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    if not correlation_id:
        correlation_id = uuid.uuid4()

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return AuditContext(
        correlation_id=correlation_id,
        actor_type="UNAUTHENTICATED",
        actor_id=None,
        session_id=None,
        ip_address=ip_address,
        user_agent=user_agent,
    )
