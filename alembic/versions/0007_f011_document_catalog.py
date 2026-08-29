"""f011 document catalog and versioning

Revision ID: 0007_f011
Revises: 0006_f009
Create Date: 2026-08-29 00:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_f011"
down_revision: Union[str, None] = "0006_f009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. document_families
    op.create_table(
        "document_families",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # 2. document_retention_policies
    op.create_table(
        "document_retention_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("retain_forever", sa.Boolean(), nullable=False, default=False),
        sa.Column("legal_hold_supported", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # 3. document_types
    op.create_table(
        "document_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "family_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_families.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "document_scope", sa.String(length=20), nullable=False, default="INTERNAL", index=True
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("phase_owner", sa.String(length=50), nullable=False, default="F011"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # 4. document_type_versions
    op.create_table(
        "document_type_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_types.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "schema_definition",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "emission_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "status_definition",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("template_key", sa.String(length=100), nullable=True),
        sa.Column(
            "retention_policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_retention_policies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "read_permission", sa.String(length=100), nullable=False, default="documents.read"
        ),
        sa.Column(
            "emit_permission", sa.String(length=100), nullable=False, default="documents.emit"
        ),
        sa.Column(
            "download_permission",
            sa.String(length=100),
            nullable=False,
            default="documents.download",
        ),
        sa.Column(
            "reprint_permission", sa.String(length=100), nullable=False, default="documents.reprint"
        ),
        sa.Column(
            "void_permission", sa.String(length=100), nullable=False, default="documents.void"
        ),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, default=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "document_type_id", "version_number", name="uq_document_type_version_number"
        ),
    )

    # Create partial unique index to enforce exactly one is_current=true per document_type_id
    op.create_index(
        "ix_document_type_versions_current_unique",
        "document_type_versions",
        ["document_type_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_document_type_versions_current_unique", table_name="document_type_versions")
    op.drop_table("document_type_versions")
    op.drop_table("document_types")
    op.drop_table("document_retention_policies")
    op.drop_table("document_families")
