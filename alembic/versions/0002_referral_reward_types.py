"""add referral reward types and idempotency indexes

Revision ID: 0002_referral_reward_types
Revises: 0001_initial
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_referral_reward_types"
down_revision: str | None = "0001_initial"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "referral_rewards",
        sa.Column(
            "reward_type",
            sa.String(length=32),
            server_default="payment",
            nullable=False,
        ),
    )
    op.create_index(
        "uq_referral_rewards_payment_id",
        "referral_rewards",
        ["payment_id"],
        unique=True,
        postgresql_where=sa.text("payment_id IS NOT NULL"),
    )
    op.create_index(
        "uq_referral_rewards_registration_referral_id",
        "referral_rewards",
        ["referral_id"],
        unique=True,
        postgresql_where=sa.text(
            "reward_type = 'registration'"
        ),
    )
    op.alter_column(
        "referral_rewards",
        "reward_type",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_referral_rewards_registration_referral_id",
        table_name="referral_rewards",
    )
    op.drop_index(
        "uq_referral_rewards_payment_id",
        table_name="referral_rewards",
    )
    op.drop_column("referral_rewards", "reward_type")
