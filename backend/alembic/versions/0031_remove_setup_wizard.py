"""Remove the runtime setup wizard."""

import sqlalchemy as sa

from alembic import op

revision = "0031_remove_setup_wizard"
down_revision = "0030_builtin_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("wizard_state")


def downgrade() -> None:
    op.create_table(
        "wizard_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("semester_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["semester_id"], ["semesters.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wizard_state"),
        sa.CheckConstraint("id = 1", name="singleton"),
    )
