"""Persist an explicit setup-wizard pause.

Revision ID: 0029_pause_setup_wizard
Revises: 0028_remove_demo_onboarding
"""

import sqlalchemy as sa

from alembic import op

revision = "0029_pause_setup_wizard"
down_revision = "0028_remove_demo_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "wizard_state",
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("wizard_state", "paused")
