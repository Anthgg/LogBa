"""F014 Document Render Snapshots and Artifacts

Revision ID: 0009_f014
Revises: 0008_f013
Create Date: 2026-08-29 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_f014"
down_revision: Union[str, None] = "0008_f013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. document_render_snapshots table
    op.create_table(
        "document_render_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "document_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_types.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "document_type_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_type_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("template_key", sa.String(100), nullable=False),
        sa.Column("template_version", sa.String(50), nullable=False),
        sa.Column("renderer_name", sa.String(50), nullable=False),
        sa.Column("renderer_version", sa.String(50), nullable=False),
        sa.Column("document_code", sa.String(100), nullable=False),
        sa.Column("snapshot_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_test_data", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index(
        "ix_document_render_snapshots_org", "document_render_snapshots", ["organization_id"]
    )
    op.create_index(
        "ix_document_render_snapshots_type", "document_render_snapshots", ["document_type_id"]
    )
    op.create_index(
        "ix_document_render_snapshots_version",
        "document_render_snapshots",
        ["document_type_version_id"],
    )
    op.create_index(
        "ix_document_render_snapshots_template", "document_render_snapshots", ["template_key"]
    )
    op.create_index(
        "ix_document_render_snapshots_code", "document_render_snapshots", ["document_code"]
    )
    op.create_index(
        "ix_document_render_snapshots_hash", "document_render_snapshots", ["snapshot_hash"]
    )

    # 2. document_render_artifacts table
    op.create_table(
        "document_render_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_render_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_document_render_artifacts_snapshot", "document_render_artifacts", ["snapshot_id"]
    )
    op.create_index(
        "ix_document_render_artifacts_hash", "document_render_artifacts", ["content_hash"]
    )


def downgrade() -> None:
    op.drop_table("document_render_artifacts")
    op.drop_table("document_render_snapshots")
