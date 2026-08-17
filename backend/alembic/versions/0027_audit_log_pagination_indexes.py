"""Add online indexes for paged audit-log queries.

Revision ID: 0027_audit_pagination
Revises: 0026_remove_nav_preference
"""

from alembic import op

revision = "0027_audit_pagination"
down_revision = "0026_remove_nav_preference"
branch_labels = None
depends_on = None


SEARCH_INDEX_SQL = """
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_audit_logs_search_trgm
ON audit_logs USING gin (
    (lower(
        coalesce(username, '') || ' ' ||
        coalesce(CAST(actor_roles AS TEXT), '') || ' ' ||
        coalesce(action, '') || ' ' ||
        coalesce(target_type, '') || ' ' ||
        coalesce(CAST(target_id AS TEXT), '') || ' ' ||
        coalesce(target_version, '') || ' ' ||
        coalesce(result, '') || ' ' ||
        coalesce(reason, '') || ' ' ||
        coalesce(detail, '')
    )) gin_trgm_ops
)
"""


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        op.create_index("ix_audit_logs_created_at_id", "audit_logs", ["created_at", "id"])
        op.create_index(
            "ix_audit_logs_action_created_at_id",
            "audit_logs",
            ["action", "created_at", "id"],
        )
        return

    with op.get_context().autocommit_block():
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_audit_logs_created_at_id "
            "ON audit_logs (created_at DESC, id DESC)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_audit_logs_action_created_at_id "
            "ON audit_logs (action, created_at DESC, id DESC)"
        )
        op.execute(SEARCH_INDEX_SQL)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        op.drop_index("ix_audit_logs_action_created_at_id", table_name="audit_logs")
        op.drop_index("ix_audit_logs_created_at_id", table_name="audit_logs")
        return

    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_audit_logs_search_trgm")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_audit_logs_action_created_at_id")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_audit_logs_created_at_id")
