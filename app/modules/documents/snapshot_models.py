"""SQLAlchemy models for Immutable Document Render Snapshots and Artifacts."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentRenderSnapshot(Base):
    """Immutable, append-only historical snapshot of rendered document state."""

    __tablename__ = "document_render_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    document_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_type_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_type_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    template_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    template_version: Mapped[str] = mapped_column(String(50), nullable=False)
    renderer_name: Mapped[str] = mapped_column(String(50), nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(50), nullable=False)
    document_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    snapshot_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    correlation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_test_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    artifacts = relationship(
        "DocumentRenderArtifact",
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )


class DocumentRenderArtifact(Base):
    """Rendered binary/text output artifact linked to an immutable snapshot."""

    __tablename__ = "document_render_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_render_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False)  # PDF, HTML
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    snapshot = relationship("DocumentRenderSnapshot", back_populates="artifacts")
