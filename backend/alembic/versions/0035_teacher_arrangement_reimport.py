"""Track safe teacher arrangement reimport outcomes."""

import sqlalchemy as sa

from alembic import op

revision = "0035_teacher_arrangement_reimport"
down_revision = "0034_teacher_arrangement_import"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teacher_arrangement_import_records",
        sa.Column(
            "outcome",
            sa.String(length=16),
            nullable=False,
            server_default="applied",
        ),
    )


def downgrade() -> None:
    op.drop_column("teacher_arrangement_import_records", "outcome")
