import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentSeries(Base):
    __tablename__ = "document_series"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "document_type_id",
            "branch_id",
            "period_year",
            name="uq_document_series_scope",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    document_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    series_prefix: Mapped[str] = mapped_column(String(50), nullable=False)
    next_correlative: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    correlative_width: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_test_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    organization = relationship("Organization")
    document_type = relationship("DocumentType")
    branch = relationship("Branch")
    reservations = relationship(
        "DocumentNumberReservation",
        back_populates="series",
        cascade="all, delete-orphan",
        order_by="desc(DocumentNumberReservation.reserved_at)",
    )
    numbers = relationship(
        "DocumentSeriesNumber",
        back_populates="series",
        cascade="all, delete-orphan",
        order_by="DocumentSeriesNumber.correlative",
    )


class DocumentNumberReservation(Base):
    __tablename__ = "document_number_reservations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_series.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    start_correlative: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_correlative: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reserved_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_test_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    series = relationship("DocumentSeries", back_populates="reservations")
    user = relationship("User")
    numbers = relationship(
        "DocumentSeriesNumber",
        back_populates="reservation",
        cascade="all, delete-orphan",
        order_by="DocumentSeriesNumber.correlative",
    )


class DocumentSeriesNumber(Base):
    __tablename__ = "document_series_numbers"
    __table_args__ = (
        UniqueConstraint("series_id", "correlative", name="uq_series_numbers_series_correlative"),
        UniqueConstraint("series_id", "display_code", name="uq_series_numbers_series_display_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_series.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reservation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_number_reservations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    correlative: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    display_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="RESERVED", nullable=False, index=True)
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    void_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_test_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    series = relationship("DocumentSeries", back_populates="numbers")
    reservation = relationship("DocumentNumberReservation", back_populates="numbers")
    voided_by = relationship("User", foreign_keys=[voided_by_user_id])
