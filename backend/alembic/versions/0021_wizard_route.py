"""记录首次进入时选择的示例/正式路线。"""

import sqlalchemy as sa

from alembic import op

revision = "0021_wizard_route"
down_revision = "0020_semester_demo_flag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wizard_state", sa.Column("route", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("wizard_state", "route")
