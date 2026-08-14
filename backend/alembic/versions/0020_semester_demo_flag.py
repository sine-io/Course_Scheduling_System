"""标记示例学期，避免示例体验改变正式首次成功状态。"""

import sqlalchemy as sa

from alembic import op

revision = "0020_semester_demo_flag"
down_revision = "0019_semester_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "semesters",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("semesters", "is_demo")
