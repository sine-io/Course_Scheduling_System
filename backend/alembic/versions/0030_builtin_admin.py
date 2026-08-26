"""Mark the single bootstrap administrator explicitly.

Revision ID: 0030_builtin_admin
Revises: 0029_pause_setup_wizard
"""

import sqlalchemy as sa

from alembic import op

revision = "0030_builtin_admin"
down_revision = "0029_pause_setup_wizard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "uq_users_single_builtin",
        "users",
        ["is_builtin"],
        unique=True,
        postgresql_where=sa.text("is_builtin"),
        sqlite_where=sa.text("is_builtin = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_single_builtin", table_name="users")
    op.drop_column("users", "is_builtin")
