import csv
import io
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.shared.audit.contracts import AuditContext
from app.shared.audit.models import AuditEvent
from app.shared.audit.repository import AuditRepository
from app.shared.audit.sanitizer import sanitize_sensitive_data
from app.shared.audit.schemas import (
    AuditEventDetailResponse,
    AuditEventResponse,
    AuditListResponse,
)


class AuditService:
    """Unified service for recording, querying, and exporting append-only audit events."""

    def __init__(self) -> None:
        self.repository = AuditRepository()

    def record_event(
        self,
        db: Session,
        context: AuditContext,
        resource_type: str,
        action: str,
        result: str,
        resource_id: Optional[uuid.UUID] = None,
        reason: Optional[str] = None,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        # Sanitize sensitive data and secrets
        sanitized_before = sanitize_sensitive_data(before_data)
        sanitized_after = sanitize_sensitive_data(after_data)
        sanitized_meta = sanitize_sensitive_data(metadata)

        # Truncate request headers if needed
        bounded_ua = context.user_agent[:255] if context.user_agent else None
        bounded_ip = context.ip_address[:45] if context.ip_address else None

        event = AuditEvent(
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            session_id=context.session_id,
            ip_address=bounded_ip,
            user_agent=bounded_ua,
            organization_id=context.organization_id,
            branch_id=context.branch_id,
            warehouse_id=context.warehouse_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            reason=reason,
            before_data=sanitized_before,
            after_data=sanitized_after,
            metadata_=sanitized_meta,
            correlation_id=context.correlation_id,
            request_id=context.request_id,
            is_test_data=context.is_test_data,
        )
        self.repository.create(db, event)
        return event

    def get_event(self, db: Session, event_id: uuid.UUID) -> AuditEventDetailResponse:
        event = self.repository.get_by_id(db, event_id)
        if not event:
            raise NotFoundError(
                message="Audit event not found.",
                code="AUDIT_EVENT_NOT_FOUND",
                details={"audit_event_id": str(event_id)},
            )
        return AuditEventDetailResponse.model_validate(event)

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
    ) -> AuditListResponse:
        total = self.repository.count_events(
            db=db,
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
        events = self.repository.list_events(
            db=db,
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
            limit=limit,
            offset=offset,
        )
        items = [AuditEventResponse.model_validate(e) for e in events]
        return AuditListResponse(total=total, limit=limit, offset=offset, items=items)

    def export_csv(
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
        max_rows: int = 5000,
    ) -> str:
        events = self.repository.list_events(
            db=db,
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
            limit=max_rows,
            offset=0,
        )
        output = io.StringIO()
        fieldnames = [
            "id",
            "occurred_at",
            "actor_type",
            "actor_id",
            "session_id",
            "ip_address",
            "user_agent",
            "organization_id",
            "branch_id",
            "warehouse_id",
            "resource_type",
            "resource_id",
            "action",
            "result",
            "reason",
            "correlation_id",
            "is_test_data",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for e in events:
            writer.writerow(
                {
                    "id": str(e.id),
                    "occurred_at": e.occurred_at.isoformat() if e.occurred_at else "",
                    "actor_type": e.actor_type,
                    "actor_id": str(e.actor_id) if e.actor_id else "",
                    "session_id": str(e.session_id) if e.session_id else "",
                    "ip_address": e.ip_address or "",
                    "user_agent": e.user_agent or "",
                    "organization_id": str(e.organization_id) if e.organization_id else "",
                    "branch_id": str(e.branch_id) if e.branch_id else "",
                    "warehouse_id": str(e.warehouse_id) if e.warehouse_id else "",
                    "resource_type": e.resource_type,
                    "resource_id": str(e.resource_id) if e.resource_id else "",
                    "action": e.action,
                    "result": e.result,
                    "reason": e.reason or "",
                    "correlation_id": str(e.correlation_id),
                    "is_test_data": str(e.is_test_data),
                }
            )

        return output.getvalue()
