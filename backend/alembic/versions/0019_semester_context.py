"""建立单校唯一的当前学期上下文。

Revision ID: 0019_semester_context
Revises: 0018_cn_foundation
"""

import sqlalchemy as sa

from alembic import op

revision = "0019_semester_context"
down_revision = "0018_cn_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semester_context",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("current_semester_id", sa.Integer(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("id = 1", name="singleton"),
        sa.ForeignKeyConstraint(
            ["current_semester_id"], ["semesters.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("current_semester_id", name="uq_semester_context_current_semester"),
    )
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO semester_context (id, current_semester_id, revision)
            SELECT 1,
                (
                    SELECT id FROM semesters
                    WHERE status <> 'archived'
                    ORDER BY CASE status
                        WHEN 'active' THEN 0
                        WHEN 'preparing' THEN 1
                        ELSE 2
                    END, academic_year DESC, term DESC
                    LIMIT 1
                ),
                CASE WHEN EXISTS (
                    SELECT 1 FROM semesters WHERE status <> 'archived'
                ) THEN 1 ELSE 0 END
            """
        )
    )


def downgrade() -> None:
    op.drop_table("semester_context")
