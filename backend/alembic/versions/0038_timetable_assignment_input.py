"""Track the teaching-assignment inputs used by a timetable."""

import sqlalchemy as sa

from alembic import op

revision = "0038_timetable_assignment_input"
down_revision = "0037_teacher_arr_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "timetables",
        sa.Column("assignment_input_fingerprint", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("timetables", "assignment_input_fingerprint")
