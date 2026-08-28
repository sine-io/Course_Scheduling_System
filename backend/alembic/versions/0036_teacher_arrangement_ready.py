"""Add stable school codes for imported period tables."""

import sqlalchemy as sa

from alembic import op

revision = "0036_teacher_arrangement_ready"
down_revision = "0035_teacher_arr_reimport"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "period_tables",
        sa.Column("school_code", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_period_tables_school_code",
        "period_tables",
        ["school_code"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_period_tables_semester_school_code",
        "period_tables",
        ["semester_id", "school_code"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_period_tables_semester_school_code",
        "period_tables",
        type_="unique",
    )
    op.drop_index("ix_period_tables_school_code", table_name="period_tables")
    op.drop_column("period_tables", "school_code")
