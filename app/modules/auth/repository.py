import uuid
from datetime import datetime, timezone
from typing import List, Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.auth.models import AuthSession, User, UserRole
from app.modules.organization.models import Role


class UserRepository:
    def create(self, db: Session, user: User) -> User:
        db.add(user)
        db.flush()
        return user

    def get_by_id(self, db: Session, user_id: uuid.UUID) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        return db.scalar(stmt)

    def get_by_email_normalized(self, db: Session, email_normalized: str) -> Optional[User]:
        stmt = select(User).where(User.email_normalized == email_normalized)
        return db.scalar(stmt)

    def list_all(self, db: Session, organization_id: Optional[uuid.UUID] = None) -> List[User]:
        stmt = select(User)
        if organization_id:
            stmt = stmt.where(User.organization_id == organization_id)
        stmt = stmt.order_by(User.created_at.asc())
        return list(db.scalars(stmt).all())

    def update(self, db: Session, user: User) -> User:
        db.flush()
        return user


class UserRoleRepository:
    def set_user_roles(
        self, db: Session, user_id: uuid.UUID, role_ids: Sequence[uuid.UUID]
    ) -> List[Role]:
        # Delete existing role mappings
        db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        db.flush()

        # Insert new role mappings
        for rid in role_ids:
            ur = UserRole(user_id=user_id, role_id=rid)
            db.add(ur)
        db.flush()

        return self.list_roles_by_user(db, user_id)

    def list_roles_by_user(self, db: Session, user_id: uuid.UUID) -> List[Role]:
        stmt = (
            select(Role)
            .join(UserRole, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.code.asc())
        )
        return list(db.scalars(stmt).all())


class SessionRepository:
    def create(self, db: Session, session: AuthSession) -> AuthSession:
        db.add(session)
        db.flush()
        return session

    def get_by_token_hash(self, db: Session, token_hash: str) -> Optional[AuthSession]:
        stmt = select(AuthSession).where(AuthSession.token_hash == token_hash)
        return db.scalar(stmt)

    def update(self, db: Session, session: AuthSession) -> AuthSession:
        db.flush()
        return session

    def revoke_session(self, db: Session, session_id: uuid.UUID) -> None:
        stmt = select(AuthSession).where(AuthSession.id == session_id)
        session = db.scalar(stmt)
        if session:
            session.revoked_at = datetime.now(timezone.utc)
            db.flush()

    def revoke_all_user_sessions(self, db: Session, user_id: uuid.UUID) -> None:
        stmt = select(AuthSession).where(
            AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
        )
        sessions = db.scalars(stmt).all()
        now = datetime.now(timezone.utc)
        for s in sessions:
            s.revoked_at = now
        db.flush()
