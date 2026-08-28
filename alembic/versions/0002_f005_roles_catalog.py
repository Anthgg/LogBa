"""f005_roles_catalog

Revision ID: 0002_f005
Revises: 0001_f004
Create Date: 2026-08-28 02:26:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_f005"
down_revision: Union[str, None] = "0001_f004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_test_data", sa.Boolean(), server_default=sa.false(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_roles_organization_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_roles_organization_id", "roles", ["organization_id"])
    op.create_index("ix_roles_code", "roles", ["code"])

    # Unique partial indexes: system roles (NULL org) and custom roles (per org)
    op.create_index(
        "uq_roles_system_code",
        "roles",
        ["code"],
        unique=True,
        postgresql_where=sa.text("organization_id IS NULL"),
    )
    op.create_index(
        "uq_roles_org_code",
        "roles",
        ["organization_id", "code"],
        unique=True,
        postgresql_where=sa.text("organization_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_roles_org_code", table_name="roles")
    op.drop_index("uq_roles_system_code", table_name="roles")
    op.drop_index("ix_roles_code", table_name="roles")
    op.drop_index("ix_roles_organization_id", table_name="roles")
    op.drop_table("roles")
