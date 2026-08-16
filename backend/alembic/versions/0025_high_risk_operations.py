"""Add idempotency keys for high-risk operation audit records."""

import sqlalchemy as sa

from alembic import op

revision = "0025_high_risk_operations"
down_revision = "0024_publication_protection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("operation_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        op.f("ix_audit_logs_operation_id"),
        "audit_logs",
        ["operation_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_operation_id"), table_name="audit_logs")
    op.drop_column("audit_logs", "operation_id")
