"""Add persisted timetable publication checks and structured audit snapshots."""

import sqlalchemy as sa

from alembic import op

revision = "0024_publication_protection"
down_revision = "0023_navigation_preference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "timetables",
        sa.Column("publication_check_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "timetables",
        sa.Column(
            "publication_check_passed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "timetables",
        sa.Column("publication_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_timetables_one_published_per_semester",
        "timetables",
        ["semester_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
        sqlite_where=sa.text("status = 'published'"),
    )
    op.add_column(
        "audit_logs",
        sa.Column("actor_roles", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column("audit_logs", sa.Column("semester_id", sa.Integer(), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column("target_version", sa.String(length=128), nullable=False, server_default=""),
    )
    op.add_column(
        "audit_logs",
        sa.Column("result", sa.String(length=20), nullable=False, server_default=""),
    )
    op.add_column(
        "audit_logs",
        sa.Column("reason", sa.String(length=64), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("audit_logs", "reason")
    op.drop_column("audit_logs", "result")
    op.drop_column("audit_logs", "target_version")
    op.drop_column("audit_logs", "semester_id")
    op.drop_column("audit_logs", "actor_roles")
    op.drop_index("uq_timetables_one_published_per_semester", table_name="timetables")
    op.drop_column("timetables", "publication_checked_at")
    op.drop_column("timetables", "publication_check_passed")
    op.drop_column("timetables", "publication_check_fingerprint")
