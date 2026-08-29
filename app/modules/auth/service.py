import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.core.rbac import AuthenticatedPrincipal
from app.modules.auth.models import AuthSession, User
from app.modules.auth.password import (
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.modules.auth.repository import (
    SessionRepository,
    UserRepository,
    UserRoleRepository,
)
from app.modules.auth.schemas import (
    LoginRequest,
    UserCreate,
    UserResponse,
    UserRoleAssignRequest,
    UserUpdate,
)
from app.modules.organization.models import Role
from app.modules.organization.repository import (
    OrganizationRepository,
    PermissionRepository,
    RolePermissionRepository,
    RoleRepository,
)
from app.shared.audit.contracts import AuditContext
from app.shared.audit.service import AuditService

settings = get_settings()


class AuthService:
    def __init__(self) -> None:
        self.user_repo = UserRepository()
        self.user_role_repo = UserRoleRepository()
        self.session_repo = SessionRepository()
        self.org_repo = OrganizationRepository()
        self.role_repo = RoleRepository()
        self.perm_repo = PermissionRepository()
        self.role_perm_repo = RolePermissionRepository()
        self.audit_service = AuditService()

    def _hash_token(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def _get_user_roles_and_permissions(
        self, db: Session, user_id: uuid.UUID
    ) -> Tuple[List[Role], List[str], Set[str]]:
        roles = self.user_role_repo.list_roles_by_user(db, user_id)
        active_roles = [r for r in roles if r.is_active]
        role_codes = [r.code for r in active_roles]

        all_permissions: Set[str] = set()
        for r in active_roles:
            perms = self.role_perm_repo.list_permissions_by_role(db, r.id)
            for p in perms:
                if p.is_active:
                    all_permissions.add(p.code)

        return active_roles, role_codes, all_permissions

    def login(
        self,
        db: Session,
        data: LoginRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Tuple[AuthSession, str, UserResponse, List[str], List[str]]:
        corr_id = correlation_id or uuid.uuid4()
        norm_email = data.email.strip().lower()
        user = self.user_repo.get_by_email_normalized(db, norm_email)

        # Constant-time-like generic verification
        if not user or not user.is_active or not verify_password(data.password, user.password_hash):
            # Record audit failure
            self.audit_service.record_event(
                db=db,
                context=AuditContext(
                    correlation_id=corr_id,
                    actor_type="UNAUTHENTICATED",
                    ip_address=ip_address,
                    user_agent=user_agent,
                ),
                resource_type="auth",
                action="auth.login",
                result="FAILURE",
                reason="INVALID_CREDENTIALS",
                metadata={"attempted_email": norm_email},
            )
            db.commit()
            raise UnauthorizedError(
                message="Credenciales invalidas.",
                code="INVALID_CREDENTIALS",
            )

        # Generate cryptographically secure random session token (256-bit entropy)
        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(raw_token)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=settings.SESSION_ABSOLUTE_TTL_MINUTES)

        session = AuthSession(
            user_id=user.id,
            token_hash=token_hash,
            created_at=now,
            expires_at=expires_at,
            last_seen_at=now,
            created_ip=ip_address[:45] if ip_address else None,
            created_user_agent=user_agent[:255] if user_agent else None,
            is_test_data=user.is_test_data,
        )
        self.session_repo.create(db, session)

        # Update last login timestamp
        user.last_login_at = now
        db.flush()

        # Audit successful login
        self.audit_service.record_event(
            db=db,
            context=AuditContext(
                correlation_id=corr_id,
                actor_type="AUTHENTICATED",
                actor_id=user.id,
                session_id=session.id,
                organization_id=user.organization_id,
                ip_address=ip_address,
                user_agent=user_agent,
                is_test_data=user.is_test_data,
            ),
            resource_type="auth",
            resource_id=user.id,
            action="auth.login",
            result="SUCCESS",
            metadata={"email": user.email},
        )
        db.commit()

        _, role_codes, permissions = self._get_user_roles_and_permissions(db, user.id)
        user_res = UserResponse(
            id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            is_test_data=user.is_test_data,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            roles=role_codes,
        )

        return session, raw_token, user_res, role_codes, sorted(list(permissions))

    def verify_session(self, db: Session, raw_token: str) -> AuthenticatedPrincipal:
        if not raw_token:
            raise UnauthorizedError(
                message="Autenticacion requerida.",
                code="AUTHENTICATION_REQUIRED",
            )

        token_hash = self._hash_token(raw_token)
        session = self.session_repo.get_by_token_hash(db, token_hash)
        now = datetime.now(timezone.utc)

        if not session or session.revoked_at is not None or session.expires_at <= now:
            raise UnauthorizedError(
                message="Sesion invalida o expirada.",
                code="AUTHENTICATION_REQUIRED",
            )

        # Check Idle Timeout
        idle_limit = timedelta(minutes=settings.SESSION_IDLE_TIMEOUT_MINUTES)
        if now - session.last_seen_at > idle_limit:
            session.revoked_at = now
            db.commit()
            raise UnauthorizedError(
                message="Sesion expirada por inactividad.",
                code="AUTHENTICATION_REQUIRED",
            )

        user = self.user_repo.get_by_id(db, session.user_id)
        if not user or not user.is_active:
            raise UnauthorizedError(
                message="Usuario inactivo o no encontrado.",
                code="AUTHENTICATION_REQUIRED",
            )

        # Update last seen timestamp
        session.last_seen_at = now
        db.flush()

        roles, role_codes, permissions = self._get_user_roles_and_permissions(db, user.id)
        role_ids = [r.id for r in roles]

        return AuthenticatedPrincipal(
            user_id=user.id,
            organization_id=user.organization_id,
            session_id=session.id,
            email=user.email,
            display_name=user.display_name,
            role_ids=role_ids,
            role_codes=role_codes,
            permissions=permissions,
            is_active=user.is_active,
        )

    def logout(
        self,
        db: Session,
        raw_token: Optional[str],
        principal: Optional[AuthenticatedPrincipal] = None,
        context: Optional[AuditContext] = None,
    ) -> None:
        if not raw_token:
            return

        token_hash = self._hash_token(raw_token)
        session = self.session_repo.get_by_token_hash(db, token_hash)
        if session and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            db.flush()

            ctx = context or AuditContext(
                actor_type="AUTHENTICATED",
                actor_id=session.user_id,
                session_id=session.id,
            )
            self.audit_service.record_event(
                db=db,
                context=ctx,
                resource_type="auth",
                resource_id=session.user_id,
                action="auth.logout",
                result="SUCCESS",
            )
            db.commit()

    # --- User Administration ---
    def create_user(
        self,
        db: Session,
        data: UserCreate,
        context: Optional[AuditContext] = None,
    ) -> UserResponse:
        ctx = context or AuditContext(
            organization_id=data.organization_id,
            is_test_data=data.is_test_data,
        )
        if data.is_test_data and settings.is_production:
            raise ForbiddenError(
                message="Synthetic test data cannot be created in production environment.",
                code="SYNTHETIC_DATA_FORBIDDEN_IN_PRODUCTION",
            )

        validate_password_policy(data.initial_password)

        org = self.org_repo.get_by_id(db, data.organization_id)
        if not org:
            raise NotFoundError(
                message="Organizacion no encontrada.",
                code="ORGANIZATION_NOT_FOUND",
                details={"organization_id": str(data.organization_id)},
            )

        norm_email = data.email.strip().lower()
        existing = self.user_repo.get_by_email_normalized(db, norm_email)
        if existing:
            raise ConflictError(
                message=f"El correo '{norm_email}' ya esta registrado.",
                code="DUPLICATE_EMAIL",
                details={"email": norm_email},
            )

        # Hash password with Argon2id
        pwd_hash = hash_password(data.initial_password)

        user = User(
            organization_id=data.organization_id,
            email=data.email.strip(),
            email_normalized=norm_email,
            display_name=data.display_name.strip(),
            password_hash=pwd_hash,
            is_active=True,
            is_test_data=data.is_test_data,
        )
        self.user_repo.create(db, user)
        db.flush()

        # Assign initial roles if specified
        assigned_roles: List[Role] = []
        if data.role_codes:
            for rcode in data.role_codes:
                role = self.role_repo.get_by_code(db, rcode, data.organization_id)
                if not role:
                    role = self.role_repo.get_by_code(db, rcode, None)
                if role:
                    assigned_roles.append(role)
            if assigned_roles:
                self.user_role_repo.set_user_roles(db, user.id, [r.id for r in assigned_roles])

        # Audit Event
        self.audit_service.record_event(
            db=db,
            context=ctx,
            resource_type="users",
            resource_id=user.id,
            action="users.create",
            result="SUCCESS",
            after_data={
                "id": str(user.id),
                "organization_id": str(user.organization_id),
                "email": user.email,
                "display_name": user.display_name,
                "roles": [r.code for r in assigned_roles],
            },
        )
        db.commit()
        db.refresh(user)

        return UserResponse(
            id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            is_test_data=user.is_test_data,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            roles=[r.code for r in assigned_roles],
        )

    def list_users(
        self, db: Session, organization_id: Optional[uuid.UUID] = None
    ) -> List[UserResponse]:
        users = self.user_repo.list_all(db, organization_id)
        result: List[UserResponse] = []
        for u in users:
            roles = self.user_role_repo.list_roles_by_user(db, u.id)
            result.append(
                UserResponse(
                    id=u.id,
                    organization_id=u.organization_id,
                    email=u.email,
                    display_name=u.display_name,
                    is_active=u.is_active,
                    is_test_data=u.is_test_data,
                    created_at=u.created_at,
                    last_login_at=u.last_login_at,
                    roles=[r.code for r in roles],
                )
            )
        return result

    def get_user(self, db: Session, user_id: uuid.UUID) -> UserResponse:
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise NotFoundError(
                message="Usuario no encontrado.",
                code="USER_NOT_FOUND",
                details={"user_id": str(user_id)},
            )
        roles = self.user_role_repo.list_roles_by_user(db, user.id)
        return UserResponse(
            id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            is_test_data=user.is_test_data,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            roles=[r.code for r in roles],
        )

    def update_user(
        self,
        db: Session,
        user_id: uuid.UUID,
        data: UserUpdate,
        context: Optional[AuditContext] = None,
    ) -> UserResponse:
        ctx = context or AuditContext()
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise NotFoundError(
                message="Usuario no encontrado.",
                code="USER_NOT_FOUND",
                details={"user_id": str(user_id)},
            )

        before_snapshot = {"display_name": user.display_name}

        if data.display_name is not None:
            user.display_name = data.display_name.strip()
        if data.password is not None:
            validate_password_policy(data.password)
            user.password_hash = hash_password(data.password)
            # Revoke previous sessions on password change
            self.session_repo.revoke_all_user_sessions(db, user.id)

        after_snapshot = {"display_name": user.display_name}

        self.audit_service.record_event(
            db=db,
            context=ctx,
            resource_type="users",
            resource_id=user.id,
            action="users.update",
            result="SUCCESS",
            before_data=before_snapshot,
            after_data=after_snapshot,
            metadata={"password_changed": data.password is not None},
        )
        db.commit()
        db.refresh(user)

        roles = self.user_role_repo.list_roles_by_user(db, user.id)
        return UserResponse(
            id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            is_test_data=user.is_test_data,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            roles=[r.code for r in roles],
        )

    def disable_user(
        self,
        db: Session,
        user_id: uuid.UUID,
        context: Optional[AuditContext] = None,
    ) -> UserResponse:
        ctx = context or AuditContext()
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise NotFoundError(
                message="Usuario no encontrado.",
                code="USER_NOT_FOUND",
                details={"user_id": str(user_id)},
            )

        user.is_active = False
        # Revoke all active sessions
        self.session_repo.revoke_all_user_sessions(db, user.id)

        self.audit_service.record_event(
            db=db,
            context=ctx,
            resource_type="users",
            resource_id=user.id,
            action="users.disable",
            result="SUCCESS",
            before_data={"is_active": True},
            after_data={"is_active": False},
        )
        db.commit()
        db.refresh(user)

        roles = self.user_role_repo.list_roles_by_user(db, user.id)
        return UserResponse(
            id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            is_test_data=user.is_test_data,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            roles=[r.code for r in roles],
        )

    def assign_user_roles(
        self,
        db: Session,
        user_id: uuid.UUID,
        data: UserRoleAssignRequest,
        context: Optional[AuditContext] = None,
    ) -> UserResponse:
        ctx = context or AuditContext()
        user = self.user_repo.get_by_id(db, user_id)
        if not user:
            raise NotFoundError(
                message="Usuario no encontrado.",
                code="USER_NOT_FOUND",
                details={"user_id": str(user_id)},
            )

        old_roles = self.user_role_repo.list_roles_by_user(db, user.id)
        old_codes = [r.code for r in old_roles]

        target_role_ids: List[uuid.UUID] = []
        if data.role_ids is not None:
            target_role_ids = data.role_ids
        elif data.role_codes is not None:
            for code in data.role_codes:
                role = self.role_repo.get_by_code(db, code, user.organization_id)
                if not role:
                    role = self.role_repo.get_by_code(db, code, None)
                if not role:
                    raise ValidationError(
                        message=f"Rol con codigo '{code}' no encontrado.",
                        code="ROLE_NOT_FOUND",
                        details={"role_code": code},
                    )
                # Organization scoping check
                if role.organization_id and role.organization_id != user.organization_id:
                    raise ForbiddenError(
                        message="No se puede asignar un rol perteneciente a otra organizacion.",
                        code="ROLE_ORGANIZATION_MISMATCH",
                    )
                target_role_ids.append(role.id)

        new_roles = self.user_role_repo.set_user_roles(db, user.id, target_role_ids)
        new_codes = [r.code for r in new_roles]

        self.audit_service.record_event(
            db=db,
            context=ctx,
            resource_type="users",
            resource_id=user.id,
            action="users.roles.assign",
            result="SUCCESS",
            before_data={"roles": old_codes},
            after_data={"roles": new_codes},
        )
        db.commit()

        return UserResponse(
            id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            is_test_data=user.is_test_data,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            roles=new_codes,
        )
