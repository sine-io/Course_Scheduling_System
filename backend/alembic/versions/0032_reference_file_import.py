"""Add source tracking for Word/Excel reference imports."""

import sqlalchemy as sa

from alembic import op


revision = "0032_reference_file_import"
down_revision = "0031_remove_setup_wizard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "course_assignments",
        sa.Column("reference_source_key", sa.String(length=160), nullable=True),
    )
    op.create_index(
        "ix_course_assignments_reference_source_key",
        "course_assignments",
        ["reference_source_key"],
    )
    op.create_unique_constraint(
        "uq_course_assignments_reference_source",
        "course_assignments",
        ["semester_id", "reference_source_key"],
    )
    op.create_table(
        "reference_import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("semester_id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("adapter_version", sa.String(length=32), nullable=False),
        sa.Column("word_filename", sa.String(length=255), nullable=False),
        sa.Column("xlsx_filename", sa.String(length=255), nullable=False),
        sa.Column("word_sha256", sa.String(length=64), nullable=False),
        sa.Column("xlsx_sha256", sa.String(length=64), nullable=False),
        sa.Column("decisions", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("semester_id", "fingerprint", name="uq_reference_import_batch_fingerprint"),
    )
    op.create_index("ix_reference_import_batches_semester_id", "reference_import_batches", ["semester_id"])
    op.create_index("ix_reference_import_batches_fingerprint", "reference_import_batches", ["fingerprint"])
    op.create_table(
        "reference_scheduling_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("semester_id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=True),
        sa.Column("subject_name", sa.String(length=64), nullable=True),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("period_no", sa.Integer(), nullable=True),
        sa.Column("rule_type", sa.String(length=20), nullable=False),
        sa.Column("source_key", sa.String(length=160), nullable=False),
        sa.Column("source_text", sa.String(length=500), nullable=False),
        sa.Column("enforced", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("semester_id", "source_key", name="uq_reference_rule_source"),
    )
    op.create_index("ix_reference_scheduling_rules_semester_id", "reference_scheduling_rules", ["semester_id"])


def downgrade() -> None:
    op.drop_index("ix_reference_scheduling_rules_semester_id", table_name="reference_scheduling_rules")
    op.drop_table("reference_scheduling_rules")
    op.drop_index("ix_reference_import_batches_fingerprint", table_name="reference_import_batches")
    op.drop_index("ix_reference_import_batches_semester_id", table_name="reference_import_batches")
    op.drop_table("reference_import_batches")
    op.drop_constraint("uq_course_assignments_reference_source", "course_assignments", type_="unique")
    op.drop_index("ix_course_assignments_reference_source_key", table_name="course_assignments")
    op.drop_column("course_assignments", "reference_source_key")
