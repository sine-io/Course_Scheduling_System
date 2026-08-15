"""允许示例与正式学期使用同一学年/学期。"""

import sqlalchemy as sa

from alembic import op

revision = "0022_formal_semester_year_index"
down_revision = "0021_wizard_route"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_semesters_academic_year", "semesters", type_="unique")
    op.create_index(
        "uq_semesters_formal_academic_year",
        "semesters",
        ["academic_year", "term"],
        unique=True,
        postgresql_where=sa.text("is_demo = false"),
        sqlite_where=sa.text("is_demo = 0"),
    )


def downgrade() -> None:
    op.drop_index("uq_semesters_formal_academic_year", table_name="semesters")
    op.create_unique_constraint(
        "uq_semesters_academic_year", "semesters", ["academic_year", "term"]
    )
