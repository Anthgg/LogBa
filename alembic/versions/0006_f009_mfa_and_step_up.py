"""f009_mfa_and_step_up

Revision ID: 0006_f009
Revises: 0005_f008
Create Date: 2026-08-28 22:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_f009"
down_revision: Union[str, None] = "0005_f008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. user_mfa_factors
    op.create_table(
        "user_mfa_factors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("factor_type", sa.String(32), nullable=False, server_default="TOTP"),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING", index=True),
        sa.Column("secret_ciphertext", sa.String(512), nullable=False),
        sa.Column("secret_nonce", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_counter", sa.BigInteger(), nullable=True),
        sa.Column("is_test_data", sa.Boolean(), default=False, nullable=False),
    )

    # 2. mfa_recovery_codes
    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "factor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_mfa_factors.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("code_hash", sa.String(64), nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. step_up_challenges
    op.create_table(
        "step_up_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auth_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("policy_code", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING", index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("attempt_count", sa.Integer(), default=0, nullable=False),
        sa.Column("max_attempts", sa.Integer(), default=5, nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
    )

    # 4. step_up_grants
    op.create_table(
        "step_up_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auth_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("policy_code", sa.String(64), nullable=False, index=True),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column(
            "factor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_mfa_factors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("step_up_grants")
    op.drop_table("step_up_challenges")
    op.drop_table("mfa_recovery_codes")
    op.drop_table("user_mfa_factors")
