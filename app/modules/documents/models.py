import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

import app.modules.auth.models  # noqa: F401
from app.db.base import Base


class DocumentFamily(Base):
    """Canonical classification family for logistics documents."""

    __tablename__ = "document_families"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    document_types: Mapped[List["DocumentType"]] = relationship(
        "DocumentType", back_populates="family", cascade="all, delete-orphan"
    )


class DocumentRetentionPolicy(Base):
    """Lifecycle retention policy for document types."""

    __tablename__ = "document_retention_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retention_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retain_forever: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    legal_hold_supported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    versions: Mapped[List["DocumentTypeVersion"]] = relationship(
        "DocumentTypeVersion", back_populates="retention_policy"
    )


class DocumentType(Base):
    """Canonical logistics document type specification."""

    __tablename__ = "document_types"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_families.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    document_scope: Mapped[str] = mapped_column(
        String(20), default="INTERNAL", nullable=False, index=True
    )  # "INTERNAL" or "EXTERNAL"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    phase_owner: Mapped[str] = mapped_column(String(50), default="F011", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    family: Mapped["DocumentFamily"] = relationship(
        "DocumentFamily", back_populates="document_types"
    )
    versions: Mapped[List["DocumentTypeVersion"]] = relationship(
        "DocumentTypeVersion",
        back_populates="document_type",
        cascade="all, delete-orphan",
        order_by="DocumentTypeVersion.version_number.desc()",
    )


class DocumentTypeVersion(Base):
    """Immutable versioned definition of document requirements, rules, and schemas."""

    __tablename__ = "document_type_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_type_id", "version_number", name="uq_document_type_version_number"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_definition: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    emission_rules: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    status_definition: Mapped[List[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    template_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    retention_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_retention_policies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    read_permission: Mapped[str] = mapped_column(
        String(100), default="documents.read", nullable=False
    )
    emit_permission: Mapped[str] = mapped_column(
        String(100), default="documents.emit", nullable=False
    )
    download_permission: Mapped[str] = mapped_column(
        String(100), default="documents.download", nullable=False
    )
    reprint_permission: Mapped[str] = mapped_column(
        String(100), default="documents.reprint", nullable=False
    )
    void_permission: Mapped[str] = mapped_column(
        String(100), default="documents.void", nullable=False
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    document_type: Mapped["DocumentType"] = relationship("DocumentType", back_populates="versions")
    retention_policy: Mapped["DocumentRetentionPolicy"] = relationship(
        "DocumentRetentionPolicy", back_populates="versions"
    )
