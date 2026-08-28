"""Add versioned, typed scheduling rules and pin timetables to revisions."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0033_versioned_scheduling_rules"
down_revision = "0032_reference_file_import"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduling_rule_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("semester_id", sa.Integer(), nullable=False),
        sa.Column("active_revision_no", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("semester_id", name="uq_scheduling_rule_sets_semester"),
    )
    op.create_index(
        "ix_scheduling_rule_sets_semester_id", "scheduling_rule_sets", ["semester_id"]
    )
    op.create_table(
        "scheduling_rule_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_set_id", sa.Integer(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["rule_set_id"], ["scheduling_rule_sets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'superseded')",
            name="valid_scheduling_rule_revision_status",
        ),
        sa.UniqueConstraint(
            "rule_set_id", "revision_no", name="uq_scheduling_rule_revisions_number"
        ),
    )
    op.create_index(
        "ix_scheduling_rule_revisions_rule_set_id",
        "scheduling_rule_revisions",
        ["rule_set_id"],
    )
    op.create_index(
        "ix_scheduling_rule_revisions_status", "scheduling_rule_revisions", ["status"]
    )
    op.create_index(
        "uq_scheduling_rule_revisions_one_draft",
        "scheduling_rule_revisions",
        ["rule_set_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
        sqlite_where=sa.text("status = 'draft'"),
    )
    op.create_index(
        "uq_scheduling_rule_revisions_one_active",
        "scheduling_rule_revisions",
        ["rule_set_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "scheduling_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("rule_key", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("template", sa.String(length=40), nullable=False),
        sa.Column(
            "target",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "timing",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("operator", sa.String(length=24), nullable=False),
        sa.Column("strength", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.String(length=12), nullable=False, server_default="medium"),
        sa.Column("source_kind", sa.String(length=20), nullable=False, server_default="custom"),
        sa.Column("source_text", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "compiler_version", sa.String(length=24), nullable=False, server_default="rules-v1"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["revision_id"], ["scheduling_rule_revisions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "revision_id", "rule_key", name="uq_scheduling_rules_revision_key"
        ),
    )
    op.create_index("ix_scheduling_rules_revision_id", "scheduling_rules", ["revision_id"])
    op.create_index("ix_scheduling_rules_rule_key", "scheduling_rules", ["rule_key"])

    op.add_column("timetables", sa.Column("rule_revision_id", sa.Integer(), nullable=True))
    op.create_index("ix_timetables_rule_revision_id", "timetables", ["rule_revision_id"])
    op.create_foreign_key(
        "fk_timetables_rule_revision_id_scheduling_rule_revisions",
        "timetables",
        "scheduling_rule_revisions",
        ["rule_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_timetables_rule_revision_id_scheduling_rule_revisions",
        "timetables",
        type_="foreignkey",
    )
    op.drop_index("ix_timetables_rule_revision_id", table_name="timetables")
    op.drop_column("timetables", "rule_revision_id")
    op.drop_index("ix_scheduling_rules_rule_key", table_name="scheduling_rules")
    op.drop_index("ix_scheduling_rules_revision_id", table_name="scheduling_rules")
    op.drop_table("scheduling_rules")
    op.drop_index(
        "uq_scheduling_rule_revisions_one_active",
        table_name="scheduling_rule_revisions",
    )
    op.drop_index(
        "uq_scheduling_rule_revisions_one_draft",
        table_name="scheduling_rule_revisions",
    )
    op.drop_index(
        "ix_scheduling_rule_revisions_status", table_name="scheduling_rule_revisions"
    )
    op.drop_index(
        "ix_scheduling_rule_revisions_rule_set_id",
        table_name="scheduling_rule_revisions",
    )
    op.drop_table("scheduling_rule_revisions")
    op.drop_index("ix_scheduling_rule_sets_semester_id", table_name="scheduling_rule_sets")
    op.drop_table("scheduling_rule_sets")
