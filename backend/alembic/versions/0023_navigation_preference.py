"""按账号保存常用导航偏好。"""

import sqlalchemy as sa

from alembic import op

revision = "0023_navigation_preference"
down_revision = "0022_formal_semester_year_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "navigation_preference",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "navigation_preference")
