import uuid
from typing import Callable, Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.rbac import AuthenticatedPrincipal
from app.db.connection import get_db
from app.modules.auth.csrf import require_csrf
from app.modules.auth.service import AuthService
from app.modules.auth.step_up import StepUpPolicyEngine
from app.shared.audit.contracts import AuditContext
from app.shared.audit.service import AuditService

settings = get_settings()
auth_service = AuthService()
audit_service = AuditService()
step_up_engine = StepUpPolicyEngine()


def validate_csrf(request: Request) -> None:
    """Validates CSRF token header for mutating requests."""
    token = request.headers.get("X-CSRF-Token")
    if not token:
        raise UnauthorizedError(
            message="CSRF token requerido en header X-CSRF-Token.",
            code="CSRF_TOKEN_REQUIRED",
        )
    require_csrf(token)


def get_current_principal(
    request: Request, db: Session = Depends(get_db)
) -> AuthenticatedPrincipal:
    """Extracts and verifies session from HttpOnly cookie, returning the AuthenticatedPrincipal."""
    raw_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not raw_token:
        raise UnauthorizedError(
            message="Sesion no encontrada. Autenticacion requerida.",
            code="AUTHENTICATION_REQUIRED",
        )
    return auth_service.verify_session(db, raw_token)


def get_audit_context(
    request: Request,
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_principal),
) -> AuditContext:
    """Constructs AuditContext bound to the current authenticated principal."""
    correlation_id = getattr(request.state, "correlation_id", None) or uuid.uuid4()
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    if principal:
        return AuditContext(
            correlation_id=correlation_id,
            actor_type="AUTHENTICATED",
            actor_id=principal.user_id,
            session_id=principal.session_id,
            organization_id=principal.organization_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    return AuditContext(
        correlation_id=correlation_id,
        actor_type="UNAUTHENTICATED",
        actor_id=None,
        session_id=None,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def require_permission(permission_code: str) -> Callable:
    """Factory creating an endpoint dependency that enforces action-based RBAC
    permissions and Step-Up policies.
    """

    def _permission_dependency(
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
        db: Session = Depends(get_db),
    ) -> AuthenticatedPrincipal:
        correlation_id = getattr(request.state, "correlation_id", None) or uuid.uuid4()

        # 1. RBAC Authorization check (Must fail first with 403 if unauthorized)
        if not principal.has_permission(permission_code):
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

            audit_service.record_event(
                db=db,
                context=AuditContext(
                    correlation_id=correlation_id,
                    actor_type="AUTHENTICATED",
                    actor_id=principal.user_id,
                    session_id=principal.session_id,
                    organization_id=principal.organization_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                ),
                resource_type="rbac",
                action=permission_code,
                result="DENIED",
                reason="PERMISSION_DENIED",
                metadata={"required_permission": permission_code},
            )
            db.commit()

            raise ForbiddenError(
                message=f"Acceso denegado: falta el permiso requerido '{permission_code}'.",
                code="PERMISSION_DENIED",
                details={"required_permission": permission_code},
            )

        # 2. Step-Up Policy Engine check (Evaluated only after RBAC permission is granted)
        step_up_engine.evaluate_step_up(
            db=db,
            principal=principal,
            permission_code=permission_code,
            correlation_id=correlation_id,
        )

        return principal

    return _permission_dependency
