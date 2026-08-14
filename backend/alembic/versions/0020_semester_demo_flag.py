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
    # 旧版本示例接口已为每次生成写入审计记录；用它回填历史示例学期，
    # 避免升级后示例课表被误当成正式首次成功。
    op.execute(
        sa.text(
            """
            UPDATE semesters
            SET is_demo = TRUE
            WHERE EXISTS (
                SELECT 1
                FROM audit_logs
                WHERE audit_logs.action = 'create_demo_data'
                  AND audit_logs.target_type = 'semester'
                  AND audit_logs.target_id = semesters.id
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_column("semesters", "is_demo")
