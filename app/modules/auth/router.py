import uuid
from typing import List, Literal, Optional, cast

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rbac import AuthenticatedPrincipal
from app.db.connection import get_db
from app.modules.auth.csrf import generate_csrf_token
from app.modules.auth.dependencies import (
    get_audit_context,
    get_current_principal,
    require_permission,
    validate_csrf,
)
from app.modules.auth.schemas import (
    AuthMeResponse,
    CsrfResponse,
    LoginRequest,
    UserCreate,
    UserResponse,
    UserRoleAssignRequest,
    UserUpdate,
)
from app.modules.auth.service import AuthService
from app.shared.audit.contracts import AuditContext

settings = get_settings()
auth_service = AuthService()

auth_router = APIRouter(prefix="/api/auth", tags=["Authentication & Sessions"])
users_router = APIRouter(prefix="/users", tags=["User Administration"])


# --- Public Authentication Endpoints ---
@auth_router.get(
    "/csrf",
    response_model=CsrfResponse,
    summary="Get signed CSRF token for mutating requests",
)
def get_csrf_token() -> CsrfResponse:
    return CsrfResponse(csrf_token=generate_csrf_token())


@auth_router.post(
    "/login",
    response_model=AuthMeResponse,
    summary="Authenticate user and establish server-side session with HttpOnly cookie",
    dependencies=[Depends(validate_csrf)],
)
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthMeResponse:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    correlation_id = getattr(request.state, "correlation_id", None)

    session, raw_token, user_res, role_codes, permissions = auth_service.login(
        db=db,
        data=data,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id,
    )

    # Set HttpOnly session cookie
    samesite_val = cast(Literal["lax", "strict", "none"], settings.SESSION_COOKIE_SAMESITE.lower())
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=samesite_val,
        path="/",
        max_age=settings.SESSION_ABSOLUTE_TTL_MINUTES * 60,
    )

    return AuthMeResponse(
        user=user_res,
        organization_id=user_res.organization_id,
        roles=role_codes,
        permissions=permissions,
    )


@auth_router.post(
    "/logout",
    summary="Revoke session and clear session cookie",
    dependencies=[Depends(validate_csrf)],
)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    raw_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    auth_service.logout(db, raw_token)

    samesite_val = cast(Literal["lax", "strict", "none"], settings.SESSION_COOKIE_SAMESITE.lower())
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=samesite_val,
    )
    return {"status": "logged_out"}


@auth_router.get(
    "/me",
    response_model=AuthMeResponse,
    summary="Get authenticated principal profile and effective permissions",
)
def get_me(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> AuthMeResponse:
    from sqlalchemy import select

    from app.modules.auth.models import UserMfaFactor

    factor_stmt = select(UserMfaFactor).where(
        UserMfaFactor.user_id == principal.user_id,
        UserMfaFactor.status == "ACTIVE",
    )
    has_mfa = db.execute(factor_stmt).scalars().first() is not None

    user_res = UserResponse(
        id=principal.user_id,
        organization_id=principal.organization_id,
        email=principal.email,
        display_name=principal.display_name,
        is_active=principal.is_active,
        is_test_data=False,
        created_at=None,
        last_login_at=None,
        roles=principal.role_codes,
    )
    return AuthMeResponse(
        user=user_res,
        organization_id=principal.organization_id,
        roles=principal.role_codes,
        permissions=sorted(list(principal.permissions)),
        mfa_enabled=has_mfa,
    )


# --- User Administration Endpoints ---
@users_router.get(
    "",
    response_model=List[UserResponse],
    summary="List organization users",
    dependencies=[Depends(require_permission("users.read"))],
)
def list_users(
    organization_id: Optional[uuid.UUID] = None,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> List[UserResponse]:
    target_org_id = organization_id or principal.organization_id
    return auth_service.list_users(db, organization_id=target_org_id)


@users_router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization user",
    dependencies=[Depends(require_permission("users.create")), Depends(validate_csrf)],
)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> UserResponse:
    return auth_service.create_user(db, data, context=context)


@users_router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    dependencies=[Depends(require_permission("users.read"))],
)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> UserResponse:
    return auth_service.get_user(db, user_id)


@users_router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user details or password",
    dependencies=[Depends(require_permission("users.update")), Depends(validate_csrf)],
)
def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> UserResponse:
    return auth_service.update_user(db, user_id, data, context=context)


@users_router.patch(
    "/{user_id}/disable",
    response_model=UserResponse,
    summary="Disable user and revoke active sessions",
    dependencies=[Depends(require_permission("users.disable")), Depends(validate_csrf)],
)
def disable_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> UserResponse:
    return auth_service.disable_user(db, user_id, context=context)


@users_router.put(
    "/{user_id}/roles",
    response_model=UserResponse,
    summary="Assign roles to user",
    dependencies=[Depends(require_permission("users.roles.assign")), Depends(validate_csrf)],
)
def assign_user_roles(
    user_id: uuid.UUID,
    data: UserRoleAssignRequest,
    db: Session = Depends(get_db),
    context: AuditContext = Depends(get_audit_context),
) -> UserResponse:
    return auth_service.assign_user_roles(db, user_id, data, context=context)
