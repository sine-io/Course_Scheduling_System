"""增加学期排课准备状态和校历特殊日期。

Revision ID: 0018_cn_foundation
Revises: 0017_class_name_unique
"""

import sqlalchemy as sa

from alembic import op

revision = "0018_cn_foundation"
down_revision = "0017_class_name_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "semesters",
        sa.Column("readiness", sa.String(length=20), nullable=False, server_default="draft"),
    )
    op.create_table(
        "semester_calendar_exceptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("semester_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("makeup_weekday", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("semester_id", "date", name="uq_calendar_exception_semester_date"),
    )
    op.create_index(
        "ix_semester_calendar_exceptions_semester_id",
        "semester_calendar_exceptions",
        ["semester_id"],
    )
    op.create_index(
        "ix_semester_calendar_exceptions_date",
        "semester_calendar_exceptions",
        ["date"],
    )


def downgrade() -> None:
    op.drop_index("ix_semester_calendar_exceptions_date", table_name="semester_calendar_exceptions")
    op.drop_index(
        "ix_semester_calendar_exceptions_semester_id", table_name="semester_calendar_exceptions"
    )
    op.drop_table("semester_calendar_exceptions")
    op.drop_column("semesters", "readiness")
