"""Remove demo data and onboarding route state.

Revision ID: 0028_remove_demo_onboarding
Revises: 0027_audit_pagination
"""

import sqlalchemy as sa

from alembic import op

revision = "0028_remove_demo_onboarding"
down_revision = "0027_audit_pagination"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Demo records are generated fixtures. The product was not deployed with
    # this feature, so they can be removed before restoring the normal key.
    op.execute(sa.text("DELETE FROM semesters WHERE is_demo = true"))
    op.drop_index("uq_semesters_formal_academic_year", table_name="semesters")
    op.drop_column("wizard_state", "route")
    op.drop_column("semesters", "is_demo")
    op.create_unique_constraint(
        "uq_semesters_academic_year", "semesters", ["academic_year", "term"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_semesters_academic_year", "semesters", type_="unique")
    op.add_column(
        "semesters",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "uq_semesters_formal_academic_year",
        "semesters",
        ["academic_year", "term"],
        unique=True,
        postgresql_where=sa.text("is_demo = false"),
        sqlite_where=sa.text("is_demo = 0"),
    )
    op.add_column("wizard_state", sa.Column("route", sa.String(length=20), nullable=True))
