"""Add normalized teacher arrangement import state."""

import sqlalchemy as sa

from alembic import op

revision = "0034_teacher_arrangement_import"
down_revision = "0033_versioned_scheduling_rules"
branch_labels = None
depends_on = None


def _add_school_code(table: str, constraint: str) -> None:
    op.add_column(table, sa.Column("school_code", sa.String(length=64), nullable=True))
    op.create_index(f"ix_{table}_school_code", table, ["school_code"])
    op.create_unique_constraint(constraint, table, ["semester_id", "school_code"])


def _drop_school_code(table: str, constraint: str) -> None:
    op.drop_constraint(constraint, table, type_="unique")
    op.drop_index(f"ix_{table}_school_code", table_name=table)
    op.drop_column(table, "school_code")


def upgrade() -> None:
    _add_school_code("subjects", "uq_subjects_semester_school_code")
    _add_school_code("teachers", "uq_teachers_semester_school_code")
    _add_school_code("rooms", "uq_rooms_semester_school_code")
    _add_school_code("class_units", "uq_class_units_semester_school_code")
    op.add_column(
        "teachers",
        sa.Column(
            "arrangement_status",
            sa.String(length=20),
            nullable=False,
            server_default="normal",
        ),
    )
    op.add_column(
        "class_units",
        sa.Column("planned_weekly_periods", sa.Integer(), nullable=True),
    )
    op.add_column(
        "course_assignments",
        sa.Column("task_code", sa.String(length=96), nullable=True),
    )
    op.add_column(
        "course_assignments",
        sa.Column(
            "component",
            sa.String(length=64),
            nullable=False,
            server_default="基础课",
        ),
    )
    op.create_index(
        "ix_course_assignments_task_code", "course_assignments", ["task_code"]
    )
    op.create_unique_constraint(
        "uq_course_assignments_semester_task_code",
        "course_assignments",
        ["semester_id", "task_code"],
    )

    op.create_table(
        "teacher_arrangement_import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("semester_id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("workbook_sha256", sa.String(length=64), nullable=False),
        sa.Column("template_version", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "semester_id",
            "fingerprint",
            name="uq_teacher_arrangement_batches_fingerprint",
        ),
    )
    op.create_index(
        "ix_teacher_arrangement_import_batches_semester_id",
        "teacher_arrangement_import_batches",
        ["semester_id"],
    )
    op.create_index(
        "ix_teacher_arrangement_import_batches_fingerprint",
        "teacher_arrangement_import_batches",
        ["fingerprint"],
    )
    op.create_index(
        "ix_teacher_arrangement_import_batches_workbook_sha256",
        "teacher_arrangement_import_batches",
        ["workbook_sha256"],
    )
    op.create_table(
        "teacher_arrangement_source_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("semester_id", sa.Integer(), nullable=False),
        sa.Column("record_code", sa.String(length=96), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("task_code", sa.String(length=96), nullable=True),
        sa.Column("content", sa.String(length=1000), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "semester_id",
            "record_code",
            name="uq_teacher_arrangement_source_record_code",
        ),
    )
    op.create_index(
        "ix_teacher_arrangement_source_records_semester_id",
        "teacher_arrangement_source_records",
        ["semester_id"],
    )
    op.create_table(
        "teacher_arrangement_import_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("semester_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("source_key", sa.String(length=160), nullable=False),
        sa.Column("sheet_name", sa.String(length=31), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("applied_values", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("raw_values", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["teacher_arrangement_import_batches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            "entity_type",
            "source_key",
            name="uq_teacher_arrangement_records_source",
        ),
    )
    op.create_index(
        "ix_teacher_arrangement_import_records_batch_id",
        "teacher_arrangement_import_records",
        ["batch_id"],
    )
    op.create_index(
        "ix_teacher_arrangement_import_records_semester_id",
        "teacher_arrangement_import_records",
        ["semester_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_teacher_arrangement_import_records_semester_id",
        table_name="teacher_arrangement_import_records",
    )
    op.drop_index(
        "ix_teacher_arrangement_import_records_batch_id",
        table_name="teacher_arrangement_import_records",
    )
    op.drop_table("teacher_arrangement_import_records")
    op.drop_index(
        "ix_teacher_arrangement_source_records_semester_id",
        table_name="teacher_arrangement_source_records",
    )
    op.drop_table("teacher_arrangement_source_records")
    op.drop_index(
        "ix_teacher_arrangement_import_batches_workbook_sha256",
        table_name="teacher_arrangement_import_batches",
    )
    op.drop_index(
        "ix_teacher_arrangement_import_batches_fingerprint",
        table_name="teacher_arrangement_import_batches",
    )
    op.drop_index(
        "ix_teacher_arrangement_import_batches_semester_id",
        table_name="teacher_arrangement_import_batches",
    )
    op.drop_table("teacher_arrangement_import_batches")
    op.drop_constraint(
        "uq_course_assignments_semester_task_code",
        "course_assignments",
        type_="unique",
    )
    op.drop_index("ix_course_assignments_task_code", table_name="course_assignments")
    op.drop_column("course_assignments", "component")
    op.drop_column("course_assignments", "task_code")
    op.drop_column("class_units", "planned_weekly_periods")
    op.drop_column("teachers", "arrangement_status")
    _drop_school_code("class_units", "uq_class_units_semester_school_code")
    _drop_school_code("rooms", "uq_rooms_semester_school_code")
    _drop_school_code("teachers", "uq_teachers_semester_school_code")
    _drop_school_code("subjects", "uq_subjects_semester_school_code")
