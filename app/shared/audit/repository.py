import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.audit.models import AuditEvent


class AuditRepository:
    """Strictly append-only repository for audit events.

    Invariants:
    - AUDIT_UPDATE_API = 0
    - AUDIT_DELETE_API = 0
    - AUDIT_UPDATE_SERVICE = 0
    - AUDIT_DELETE_SERVICE = 0
    """

    def create(self, db: Session, event: AuditEvent) -> AuditEvent:
        db.add(event)
        db.flush()
        return event

    def get_by_id(self, db: Session, event_id: uuid.UUID) -> Optional[AuditEvent]:
        stmt = select(AuditEvent).where(AuditEvent.id == event_id)
        return db.scalar(stmt)

    def _build_filter_stmt(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        actor_type: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        branch_id: Optional[uuid.UUID] = None,
        warehouse_id: Optional[uuid.UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        result: Optional[str] = None,
        correlation_id: Optional[uuid.UUID] = None,
        is_test_data: Optional[bool] = None,
    ):
        stmt = select(AuditEvent)
        if date_from:
            stmt = stmt.where(AuditEvent.occurred_at >= date_from)
        if date_to:
            stmt = stmt.where(AuditEvent.occurred_at <= date_to)
        if actor_type:
            stmt = stmt.where(AuditEvent.actor_type == actor_type)
        if actor_id:
            stmt = stmt.where(AuditEvent.actor_id == actor_id)
        if organization_id:
            stmt = stmt.where(AuditEvent.organization_id == organization_id)
        if branch_id:
            stmt = stmt.where(AuditEvent.branch_id == branch_id)
        if warehouse_id:
            stmt = stmt.where(AuditEvent.warehouse_id == warehouse_id)
        if resource_type:
            stmt = stmt.where(AuditEvent.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(AuditEvent.resource_id == resource_id)
        if action:
            stmt = stmt.where(AuditEvent.action == action)
        if result:
            stmt = stmt.where(AuditEvent.result == result)
        if correlation_id:
            stmt = stmt.where(AuditEvent.correlation_id == correlation_id)
        if is_test_data is not None:
            stmt = stmt.where(AuditEvent.is_test_data == is_test_data)
        return stmt

    def list_events(
        self,
        db: Session,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        actor_type: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        branch_id: Optional[uuid.UUID] = None,
        warehouse_id: Optional[uuid.UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        result: Optional[str] = None,
        correlation_id: Optional[uuid.UUID] = None,
        is_test_data: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AuditEvent]:
        stmt = self._build_filter_stmt(
            date_from=date_from,
            date_to=date_to,
            actor_type=actor_type,
            actor_id=actor_id,
            organization_id=organization_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            correlation_id=correlation_id,
            is_test_data=is_test_data,
        )
        stmt = stmt.order_by(AuditEvent.occurred_at.desc()).limit(limit).offset(offset)
        return list(db.scalars(stmt).all())

    def count_events(
        self,
        db: Session,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        actor_type: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        branch_id: Optional[uuid.UUID] = None,
        warehouse_id: Optional[uuid.UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        result: Optional[str] = None,
        correlation_id: Optional[uuid.UUID] = None,
        is_test_data: Optional[bool] = None,
    ) -> int:
        stmt = self._build_filter_stmt(
            date_from=date_from,
            date_to=date_to,
            actor_type=actor_type,
            actor_id=actor_id,
            organization_id=organization_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            correlation_id=correlation_id,
            is_test_data=is_test_data,
        )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_val = db.scalar(count_stmt)
        return int(count_val or 0)
