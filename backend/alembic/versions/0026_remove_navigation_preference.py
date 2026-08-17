"""Remove the retired per-user sidebar navigation preference."""

from alembic import op

revision = "0026_remove_nav_preference"
down_revision = "0025_high_risk_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "navigation_preference")


def downgrade() -> None:
    import sqlalchemy as sa

    op.add_column("users", sa.Column("navigation_preference", sa.JSON(), nullable=True))
