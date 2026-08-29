"""F013: Document Series, Reservations, and Series Numbers

Revision ID: 0008_f013
Revises: 0007_f011
Create Date: 2026-08-29 11:25:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_f013"
down_revision: Union[str, None] = "0007_f011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. document_series
    op.create_table(
        "document_series",
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
            sa.ForeignKey("document_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("series_prefix", sa.String(length=50), nullable=False),
        sa.Column("next_correlative", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("correlative_width", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_test_data", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "organization_id",
            "document_type_id",
            "branch_id",
            "period_year",
            name="uq_document_series_scope",
        ),
    )
    op.create_index("ix_document_series_organization_id", "document_series", ["organization_id"])
    op.create_index("ix_document_series_document_type_id", "document_series", ["document_type_id"])
    op.create_index("ix_document_series_branch_id", "document_series", ["branch_id"])
    op.create_index("ix_document_series_period_year", "document_series", ["period_year"])

    # 2. document_number_reservations
    op.create_table(
        "document_number_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "series_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_series.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("start_correlative", sa.BigInteger(), nullable=False),
        sa.Column("end_correlative", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "reserved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reserved_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "reserved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_test_data", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "ix_document_number_reservations_series_id", "document_number_reservations", ["series_id"]
    )
    op.create_index(
        "ix_document_number_reservations_reserved_by_user_id",
        "document_number_reservations",
        ["reserved_by_user_id"],
    )
    op.create_index(
        "ix_document_number_reservations_reserved_at",
        "document_number_reservations",
        ["reserved_at"],
    )

    # 3. document_series_numbers
    op.create_table(
        "document_series_numbers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "series_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_series.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reservation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_number_reservations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("correlative", sa.BigInteger(), nullable=False),
        sa.Column("display_code", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="RESERVED"),
        sa.Column(
            "reserved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "voided_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("void_reason", sa.String(length=500), nullable=True),
        sa.Column("is_test_data", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint(
            "series_id", "correlative", name="uq_series_numbers_series_correlative"
        ),
        sa.UniqueConstraint(
            "series_id", "display_code", name="uq_series_numbers_series_display_code"
        ),
    )
    op.create_index(
        "ix_document_series_numbers_series_id", "document_series_numbers", ["series_id"]
    )
    op.create_index(
        "ix_document_series_numbers_reservation_id", "document_series_numbers", ["reservation_id"]
    )
    op.create_index(
        "ix_document_series_numbers_correlative", "document_series_numbers", ["correlative"]
    )
    op.create_index(
        "ix_document_series_numbers_display_code", "document_series_numbers", ["display_code"]
    )
    op.create_index("ix_document_series_numbers_status", "document_series_numbers", ["status"])


def downgrade() -> None:
    op.drop_table("document_series_numbers")
    op.drop_table("document_number_reservations")
    op.drop_table("document_series")
