import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.shared.audit.schemas import (
    AuditEventDetailResponse,
    AuditListResponse,
)
from app.shared.audit.service import AuditService

router = APIRouter(prefix="/audit-events", tags=["Audit Trail"])
audit_service = AuditService()


@router.get(
    "/export",
    summary="Export audit events log as CSV",
    response_class=Response,
)
def export_audit_events_csv(
    date_from: Optional[datetime] = Query(None, description="Start timestamp filter (ISO 8601)"),
    date_to: Optional[datetime] = Query(None, description="End timestamp filter (ISO 8601)"),
    actor_type: Optional[str] = Query(
        None, description="Filter by actor type (SYSTEM, UNAUTHENTICATED, AUTHENTICATED)"
    ),
    actor_id: Optional[uuid.UUID] = Query(None, description="Filter by actor ID"),
    organization_id: Optional[uuid.UUID] = Query(None, description="Filter by organization ID"),
    branch_id: Optional[uuid.UUID] = Query(None, description="Filter by branch ID"),
    warehouse_id: Optional[uuid.UUID] = Query(None, description="Filter by warehouse ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[uuid.UUID] = Query(None, description="Filter by resource ID"),
    action: Optional[str] = Query(None, description="Filter by action code"),
    result: Optional[str] = Query(
        None, description="Filter by execution result (SUCCESS, FAILURE, DENIED)"
    ),
    correlation_id: Optional[uuid.UUID] = Query(None, description="Filter by correlation ID"),
    is_test_data: Optional[bool] = Query(None, description="Filter by test/demo data flag"),
    max_rows: int = Query(5000, le=10000, description="Maximum rows to export"),
    db: Session = Depends(get_db),
) -> Response:
    csv_data = audit_service.export_csv(
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
        max_rows=max_rows,
    )
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"audit_trail_{timestamp_str}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "",
    response_model=AuditListResponse,
    summary="Query and filter append-only audit trail",
)
def list_audit_events(
    date_from: Optional[datetime] = Query(None, description="Start timestamp filter (ISO 8601)"),
    date_to: Optional[datetime] = Query(None, description="End timestamp filter (ISO 8601)"),
    actor_type: Optional[str] = Query(None, description="Filter by actor type"),
    actor_id: Optional[uuid.UUID] = Query(None, description="Filter by actor ID"),
    organization_id: Optional[uuid.UUID] = Query(None, description="Filter by organization ID"),
    branch_id: Optional[uuid.UUID] = Query(None, description="Filter by branch ID"),
    warehouse_id: Optional[uuid.UUID] = Query(None, description="Filter by warehouse ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[uuid.UUID] = Query(None, description="Filter by resource ID"),
    action: Optional[str] = Query(None, description="Filter by action code"),
    result: Optional[str] = Query(None, description="Filter by result"),
    correlation_id: Optional[uuid.UUID] = Query(None, description="Filter by correlation ID"),
    is_test_data: Optional[bool] = Query(None, description="Filter by test/demo data flag"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
) -> AuditListResponse:
    return audit_service.list_events(
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


@router.get(
    "/{audit_event_id}",
    response_model=AuditEventDetailResponse,
    summary="Get audit event detailed snapshot",
)
def get_audit_event(
    audit_event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> AuditEventDetailResponse:
    return audit_service.get_event(db, audit_event_id)
