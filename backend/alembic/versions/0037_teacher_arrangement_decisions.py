"""Retain teacher arrangement import decisions for audit."""

import sqlalchemy as sa

from alembic import op

revision = "0037_teacher_arr_decisions"
down_revision = "0036_teacher_arrangement_ready"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teacher_arrangement_import_batches",
        sa.Column("decisions", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("teacher_arrangement_import_batches", "decisions")
