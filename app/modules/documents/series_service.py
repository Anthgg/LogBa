import csv
import io
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.rbac import AuthenticatedPrincipal
from app.modules.documents.models import DocumentType
from app.modules.documents.numbering_standard import (
    DECISION_F012_CORRELATIVE_WIDTH,
    format_canonical_document_code,
)
from app.modules.documents.series_models import (
    DocumentNumberReservation,
    DocumentSeries,
    DocumentSeriesNumber,
)
from app.modules.documents.series_schemas import (
    DocumentSeriesCreate,
    DocumentSeriesReservationCreate,
    DocumentSeriesResponse,
    VoidDocumentNumberRequest,
)
from app.modules.organization.models import Branch
from app.shared.audit.contracts import AuditContext
from app.shared.audit.service import AuditService

MAX_RESERVATION_SIZE = 500
MAX_CORRELATIVE_LIMIT = 999999


class DocumentSeriesService:
    @staticmethod
    def _map_series_response(series: DocumentSeries, db: Session) -> DocumentSeriesResponse:
        reserved_count = (
            db.query(func.count(DocumentSeriesNumber.id))
            .filter(
                DocumentSeriesNumber.series_id == series.id,
                DocumentSeriesNumber.status == "RESERVED",
            )
            .scalar()
            or 0
        )
        voided_count = (
            db.query(func.count(DocumentSeriesNumber.id))
            .filter(
                DocumentSeriesNumber.series_id == series.id,
                DocumentSeriesNumber.status == "VOIDED",
            )
            .scalar()
            or 0
        )
        return DocumentSeriesResponse(
            id=series.id,
            organization_id=series.organization_id,
            document_type_id=series.document_type_id,
            document_type_code=series.document_type.code if series.document_type else None,
            document_type_name=series.document_type.name if series.document_type else None,
            branch_id=series.branch_id,
            branch_code=series.branch.code if series.branch else None,
            branch_name=series.branch.name if series.branch else None,
            period_year=series.period_year,
            series_prefix=series.series_prefix,
            next_correlative=series.next_correlative,
            correlative_width=series.correlative_width,
            is_active=series.is_active,
            is_test_data=series.is_test_data,
            reserved_count=reserved_count,
            voided_count=voided_count,
            created_at=series.created_at,
            updated_at=series.updated_at,
        )

    @staticmethod
    def create_series(
        db: Session,
        payload: DocumentSeriesCreate,
        principal: AuthenticatedPrincipal,
        context: AuditContext,
    ) -> DocumentSeries:
        audit_service = AuditService()

        # 1. Validate Document Type
        doc_type = db.get(DocumentType, payload.document_type_id)
        if not doc_type:
            raise NotFoundError(
                message="El tipo documental especificado no existe.",
                code="DOCUMENT_TYPE_NOT_FOUND",
            )
        if not doc_type.is_active:
            raise DomainError(
                code="DOCUMENT_TYPE_INACTIVE",
                message=f"El tipo documental '{doc_type.code}' se encuentra inactivo.",
            )
        if doc_type.document_scope != "INTERNAL":
            raise DomainError(
                code="EXTERNAL_DOCUMENT_SERIES_FORBIDDEN",
                message=(
                    f"El tipo documental '{doc_type.code}' tiene alcance EXTERNAL. "
                    "Solo los documentos con alcance INTERNAL admiten la creación de series "
                    "digitales internas."
                ),
            )

        # 2. Validate Branch
        branch = db.get(Branch, payload.branch_id)
        if not branch:
            raise NotFoundError(
                message="La sede especificada no existe.",
                code="BRANCH_NOT_FOUND",
            )
        if principal.organization_id and branch.organization_id != principal.organization_id:
            raise DomainError(
                code="BRANCH_ORGANIZATION_MISMATCH",
                message=(
                    "La sede especificada no pertenece a la organización del usuario autenticado."
                ),
            )

        org_id = branch.organization_id

        # 3. Check for existing series in same scope
        existing = (
            db.query(DocumentSeries)
            .filter(
                DocumentSeries.organization_id == org_id,
                DocumentSeries.document_type_id == doc_type.id,
                DocumentSeries.branch_id == branch.id,
                DocumentSeries.period_year == payload.period_year,
            )
            .first()
        )
        if existing:
            raise ConflictError(
                code="DUPLICATE_SERIES",
                message=(
                    f"Ya existe una serie documental para el tipo '{doc_type.code}', "
                    f"sede '{branch.code}' y periodo {payload.period_year}."
                ),
            )

        # 4. Build Canonical Prefix & Create Series
        prefix = (
            f"{doc_type.code.upper().strip()}-{branch.code.upper().strip()}-{payload.period_year}"
        )
        series = DocumentSeries(
            organization_id=org_id,
            document_type_id=doc_type.id,
            branch_id=branch.id,
            period_year=payload.period_year,
            series_prefix=prefix,
            next_correlative=1,
            correlative_width=DECISION_F012_CORRELATIVE_WIDTH,
            is_active=True,
            is_test_data=branch.is_test_data or doc_type.phase_owner == "F011",
        )
        db.add(series)
        db.flush()

        # 5. Record Audit Event
        audit_service.record_event(
            db,
            context,
            resource_type="document_series",
            action="document_series.create",
            result="SUCCESS",
            resource_id=series.id,
            after_data={
                "id": str(series.id),
                "organization_id": str(org_id),
                "document_type_code": doc_type.code,
                "branch_code": branch.code,
                "period_year": series.period_year,
                "series_prefix": series.series_prefix,
                "next_correlative": series.next_correlative,
            },
        )
        db.commit()
        db.refresh(series)
        return series

    @staticmethod
    def get_series_list(
        db: Session,
        principal: AuthenticatedPrincipal,
        document_type_id: Optional[uuid.UUID] = None,
        branch_id: Optional[uuid.UUID] = None,
        period_year: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> List[DocumentSeriesResponse]:
        query = db.query(DocumentSeries).options(
            joinedload(DocumentSeries.document_type),
            joinedload(DocumentSeries.branch),
        )
        if principal.organization_id:
            query = query.filter(DocumentSeries.organization_id == principal.organization_id)
        if document_type_id:
            query = query.filter(DocumentSeries.document_type_id == document_type_id)
        if branch_id:
            query = query.filter(DocumentSeries.branch_id == branch_id)
        if period_year:
            query = query.filter(DocumentSeries.period_year == period_year)
        if is_active is not None:
            query = query.filter(DocumentSeries.is_active == is_active)

        series_items = query.order_by(DocumentSeries.created_at.desc()).all()
        return [DocumentSeriesService._map_series_response(s, db) for s in series_items]

    @staticmethod
    def get_series_by_id(
        db: Session,
        series_id: uuid.UUID,
        principal: AuthenticatedPrincipal,
    ) -> DocumentSeries:
        series = (
            db.query(DocumentSeries)
            .options(
                joinedload(DocumentSeries.document_type),
                joinedload(DocumentSeries.branch),
                joinedload(DocumentSeries.reservations),
            )
            .filter(DocumentSeries.id == series_id)
            .first()
        )
        if not series or (
            principal.organization_id and series.organization_id != principal.organization_id
        ):
            raise NotFoundError(
                message="Serie documental no encontrada.",
                code="DOCUMENT_SERIES_NOT_FOUND",
            )
        return series

    @staticmethod
    def reserve_correlatives(
        db: Session,
        series_id: uuid.UUID,
        payload: DocumentSeriesReservationCreate,
        principal: AuthenticatedPrincipal,
        context: AuditContext,
    ) -> DocumentNumberReservation:
        audit_service = AuditService()

        # 1. Lock Series with SELECT FOR UPDATE
        series = (
            db.query(DocumentSeries)
            .filter(DocumentSeries.id == series_id)
            .with_for_update()
            .first()
        )
        if not series or (
            principal.organization_id and series.organization_id != principal.organization_id
        ):
            raise NotFoundError(
                message="Serie documental no encontrada.",
                code="DOCUMENT_SERIES_NOT_FOUND",
            )

        if not series.is_active:
            raise DomainError(
                code="DOCUMENT_SERIES_INACTIVE",
                message="La serie documental se encuentra inactiva y no admite reservas.",
            )

        # 2. Validate Reservation Quantity Bounds
        qty = payload.quantity
        if qty < 1 or qty > MAX_RESERVATION_SIZE:
            raise DomainError(
                code="INVALID_RESERVATION_QUANTITY",
                message=f"La cantidad de correlativos debe estar entre 1 y {MAX_RESERVATION_SIZE}.",
            )

        # 3. Calculate Range and Check Overflow
        start_corr = series.next_correlative
        end_corr = start_corr + qty - 1

        if end_corr > MAX_CORRELATIVE_LIMIT:
            raise DomainError(
                code="CORRELATIVE_RANGE_EXHAUSTED",
                message=(
                    f"La reserva solicitada ({qty} números) excede el límite máximo de correlativo "
                    f"({MAX_CORRELATIVE_LIMIT}) para esta serie."
                ),
            )

        # 4. Strictly Monotonic Increment of next_correlative
        series.next_correlative = end_corr + 1
        db.add(series)

        # 5. Create Reservation Entry
        reservation = DocumentNumberReservation(
            series_id=series.id,
            start_correlative=start_corr,
            end_correlative=end_corr,
            quantity=qty,
            reserved_by_user_id=principal.user_id,
            reserved_session_id=principal.session_id,
            reason=payload.reason,
            correlation_id=context.correlation_id,
            is_test_data=series.is_test_data,
        )
        db.add(reservation)
        db.flush()

        # 6. Generate Individual Series Numbers
        type_code = series.document_type.code
        branch_code = series.branch.code
        width = series.correlative_width

        for corr in range(start_corr, end_corr + 1):
            disp_code = format_canonical_document_code(
                type_code=type_code,
                branch_code=branch_code,
                period_year=series.period_year,
                correlative=corr,
                width=width,
            )
            num_entry = DocumentSeriesNumber(
                series_id=series.id,
                reservation_id=reservation.id,
                correlative=corr,
                display_code=disp_code,
                status="RESERVED",
                is_test_data=series.is_test_data,
            )
            db.add(num_entry)

        # 7. Record Append-Only Audit Event
        first_code = format_canonical_document_code(
            type_code, branch_code, series.period_year, start_corr, width
        )
        last_code = format_canonical_document_code(
            type_code, branch_code, series.period_year, end_corr, width
        )

        audit_service.record_event(
            db,
            context,
            resource_type="document_number_reservation",
            action="document_series.reservation.create",
            result="SUCCESS",
            resource_id=reservation.id,
            after_data={
                "reservation_id": str(reservation.id),
                "series_id": str(series.id),
                "start_correlative": start_corr,
                "end_correlative": end_corr,
                "quantity": qty,
                "first_code": first_code,
                "last_code": last_code,
            },
        )

        db.commit()
        db.refresh(reservation)
        return reservation

    @staticmethod
    def get_reservation_by_id(
        db: Session,
        reservation_id: uuid.UUID,
        principal: AuthenticatedPrincipal,
    ) -> DocumentNumberReservation:
        reservation = (
            db.query(DocumentNumberReservation)
            .options(
                joinedload(DocumentNumberReservation.series).joinedload(
                    DocumentSeries.document_type
                ),
                joinedload(DocumentNumberReservation.series).joinedload(DocumentSeries.branch),
                joinedload(DocumentNumberReservation.user),
                joinedload(DocumentNumberReservation.numbers),
            )
            .filter(DocumentNumberReservation.id == reservation_id)
            .first()
        )
        if not reservation or (
            principal.organization_id
            and reservation.series.organization_id != principal.organization_id
        ):
            raise NotFoundError(
                message="Reserva documental no encontrada.",
                code="RESERVATION_NOT_FOUND",
            )
        return reservation

    @staticmethod
    def get_series_numbers(
        db: Session,
        series_id: uuid.UUID,
        principal: AuthenticatedPrincipal,
        status: Optional[str] = None,
        reservation_id: Optional[uuid.UUID] = None,
        from_correlative: Optional[int] = None,
        to_correlative: Optional[int] = None,
    ) -> List[DocumentSeriesNumber]:
        # Validate series ownership
        series = DocumentSeriesService.get_series_by_id(db, series_id, principal)

        query = (
            db.query(DocumentSeriesNumber)
            .options(joinedload(DocumentSeriesNumber.voided_by))
            .filter(DocumentSeriesNumber.series_id == series.id)
        )
        if status:
            query = query.filter(DocumentSeriesNumber.status == status)
        if reservation_id:
            query = query.filter(DocumentSeriesNumber.reservation_id == reservation_id)
        if from_correlative:
            query = query.filter(DocumentSeriesNumber.correlative >= from_correlative)
        if to_correlative:
            query = query.filter(DocumentSeriesNumber.correlative <= to_correlative)

        return query.order_by(DocumentSeriesNumber.correlative.asc()).all()

    @staticmethod
    def void_number(
        db: Session,
        number_id: uuid.UUID,
        payload: VoidDocumentNumberRequest,
        principal: AuthenticatedPrincipal,
        context: AuditContext,
    ) -> DocumentSeriesNumber:
        audit_service = AuditService()

        number = (
            db.query(DocumentSeriesNumber)
            .filter(DocumentSeriesNumber.id == number_id)
            .with_for_update()
            .first()
        )
        if not number or (
            principal.organization_id and number.series.organization_id != principal.organization_id
        ):
            raise NotFoundError(
                message="Número correlativo no encontrado.",
                code="DOCUMENT_NUMBER_NOT_FOUND",
            )

        if number.status == "VOIDED":
            raise ConflictError(
                code="DOCUMENT_NUMBER_ALREADY_VOIDED",
                message=f"El número documental '{number.display_code}' ya se encuentra anulado.",
            )

        before_state = {
            "id": str(number.id),
            "status": number.status,
            "correlative": number.correlative,
            "display_code": number.display_code,
        }

        # Mark as VOIDED with audit timestamp and reason without decrementing next_correlative
        number.status = "VOIDED"
        number.voided_at = datetime.now(timezone.utc)
        number.voided_by_user_id = principal.user_id
        number.void_reason = payload.reason.strip()
        db.add(number)

        audit_service.record_event(
            db,
            context,
            resource_type="document_series_number",
            action="document_series.number.void",
            result="SUCCESS",
            resource_id=number.id,
            before_data=before_state,
            after_data={
                "id": str(number.id),
                "status": "VOIDED",
                "correlative": number.correlative,
                "display_code": number.display_code,
                "void_reason": number.void_reason,
                "voided_at": number.voided_at.isoformat(),
            },
        )

        db.commit()
        db.refresh(number)
        return number

    @staticmethod
    def generate_booklet_csv(
        db: Session,
        reservation_id: uuid.UUID,
        principal: AuthenticatedPrincipal,
        context: AuditContext,
    ) -> str:
        audit_service = AuditService()
        reservation = DocumentSeriesService.get_reservation_by_id(db, reservation_id, principal)

        series = reservation.series
        doc_type_code = series.document_type.code
        branch_code = series.branch.code
        year = series.period_year

        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")

        # Canonical Booklet CSV Header
        writer.writerow(
            [
                "DOCUMENT_TYPE",
                "BRANCH",
                "YEAR",
                "CORRELATIVE",
                "DISPLAY_CODE",
                "STATUS",
                "RESERVED_AT",
                "VOIDED_AT",
                "VOID_REASON",
                "RESERVATION_ID",
            ]
        )

        for num in reservation.numbers:
            writer.writerow(
                [
                    doc_type_code,
                    branch_code,
                    year,
                    num.correlative,
                    num.display_code,
                    num.status,
                    num.reserved_at.isoformat() if num.reserved_at else "",
                    num.voided_at.isoformat() if num.voided_at else "",
                    num.void_reason or "",
                    str(reservation.id),
                ]
            )

        audit_service.record_event(
            db,
            context,
            resource_type="document_number_reservation",
            action="document_series.booklet.download",
            result="SUCCESS",
            resource_id=reservation.id,
            after_data={
                "reservation_id": str(reservation.id),
                "series_id": str(series.id),
                "quantity": reservation.quantity,
                "format": "CSV",
            },
        )
        db.commit()

        return output.getvalue()
