"""Benchmark the production audit pagination query against PostgreSQL.

The benchmark uses a connection-local temporary table, so it never writes to
the application's real audit log. Data generation and index creation are not
included in the measured query time.

Run inside the API container after migrations:
    python -m app.scripts.benchmark_audit_pagination
"""

from __future__ import annotations

import argparse
import statistics
import time
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.api.audit import build_audit_filters
from app.core.db import engine
from app.models.audit import AuditLog

SEARCH_INDEX_EXPRESSION = """
lower(
    coalesce(username, '') || ' ' ||
    coalesce(CAST(actor_roles AS TEXT), '') || ' ' ||
    coalesce(action, '') || ' ' ||
    coalesce(target_type, '') || ' ' ||
    coalesce(CAST(target_id AS TEXT), '') || ' ' ||
    coalesce(target_version, '') || ' ' ||
    coalesce(result, '') || ' ' ||
    coalesce(reason, '') || ' ' ||
    coalesce(detail, '')
)
"""


@dataclass(frozen=True)
class Scenario:
    name: str
    page: int = 1
    page_size: int = 20
    action: str | None = None
    query: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--threshold-ms", type=float, default=1_000.0)
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("--rows must be at least 1")
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.threshold_ms <= 0:
        parser.error("--threshold-ms must be positive")
    return args


def prepare_data(connection: Connection, rows: int) -> float:
    started = time.perf_counter()
    has_trgm = connection.scalar(
        text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')")
    )
    if not has_trgm:
        raise RuntimeError("pg_trgm is missing; run `alembic upgrade head` first")

    connection.execute(
        text(
            "CREATE TEMP TABLE audit_logs "
            "(LIKE public.audit_logs INCLUDING DEFAULTS) ON COMMIT PRESERVE ROWS"
        )
    )
    marker_id = min(rows, 424_242)
    connection.execute(
        text(
            """
            INSERT INTO audit_logs (
                id, operation_id, user_id, username, actor_roles, action,
                target_type, target_id, semester_id, target_version,
                result, reason, detail, created_at
            )
            SELECT
                series_id,
                NULL,
                NULL,
                'operator-' || (series_id % 50000),
                CASE
                    WHEN series_id % 3 = 0 THEN '["admin"]'::json
                    WHEN series_id % 3 = 1 THEN '["scheduler"]'::json
                    ELSE '["director"]'::json
                END,
                CASE series_id % 5
                    WHEN 0 THEN 'publish_timetable'
                    WHEN 1 THEN 'create_backup'
                    WHEN 2 THEN 'assign_substitution'
                    WHEN 3 THEN 'create_leave'
                    ELSE 'update_account'
                END,
                CASE series_id % 4
                    WHEN 0 THEN 'timetable'
                    WHEN 1 THEN 'backup'
                    WHEN 2 THEN 'affected_period'
                    ELSE 'account'
                END,
                series_id % 100000,
                series_id % 20,
                'version-' || (series_id % 10000),
                CASE WHEN series_id % 4 = 0 THEN 'rejected' ELSE 'success' END,
                CASE WHEN series_id % 4 = 0 THEN 'conflict' ELSE '' END,
                CASE
                    WHEN series_id = :marker_id THEN 'unique-marker-424242'
                    ELSE 'routine audit entry ' || series_id
                END,
                TIMESTAMPTZ '2026-01-01 00:00:00+00'
                    + series_id * INTERVAL '1 millisecond'
            FROM generate_series(1, :rows) AS series_id
            """
        ),
        {"rows": rows, "marker_id": marker_id},
    )
    connection.execute(
        text(
            "CREATE INDEX audit_bench_created_at_id "
            "ON audit_logs (created_at DESC, id DESC)"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX audit_bench_action_created_at_id "
            "ON audit_logs (action, created_at DESC, id DESC)"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX audit_bench_search_trgm ON audit_logs USING gin "
            f"(({SEARCH_INDEX_EXPRESSION}) gin_trgm_ops)"
        )
    )
    connection.execute(text("ANALYZE audit_logs"))
    return (time.perf_counter() - started) * 1_000


def execute_scenario(session: Session, scenario: Scenario) -> tuple[int, int]:
    filters = build_audit_filters(scenario.action, scenario.query)
    total = session.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    rows = session.scalars(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((scenario.page - 1) * scenario.page_size)
        .limit(scenario.page_size)
    ).all()
    session.expunge_all()
    return total, len(rows)


def scenarios_for(rows: int) -> list[Scenario]:
    last_page = max(1, (rows + 19) // 20)
    return [
        Scenario("latest-page"),
        Scenario("deep-last-page", page=last_page),
        Scenario("action-filter", page=100, action="create_backup"),
        Scenario("unique-search", query="unique-marker-424242"),
        Scenario("visible-label-search", query="发布课表 系统管理员"),
    ]


def main() -> None:
    args = parse_args()
    if engine.dialect.name != "postgresql":
        raise SystemExit("audit pagination benchmark requires PostgreSQL")

    failures: list[str] = []
    with engine.connect() as connection:
        setup_ms = prepare_data(connection, args.rows)
        print(f"prepared {args.rows:,} temporary rows in {setup_ms:,.1f} ms")
        with Session(bind=connection) as session:
            for scenario in scenarios_for(args.rows):
                execute_scenario(session, scenario)
                timings: list[float] = []
                total = returned = 0
                for _ in range(args.repeats):
                    started = time.perf_counter()
                    total, returned = execute_scenario(session, scenario)
                    timings.append((time.perf_counter() - started) * 1_000)
                median_ms = statistics.median(timings)
                worst_ms = max(timings)
                print(
                    f"{scenario.name:22} total={total:>9,} page_rows={returned:>3} "
                    f"median={median_ms:>8.1f} ms worst={worst_ms:>8.1f} ms"
                )
                if worst_ms > args.threshold_ms:
                    failures.append(f"{scenario.name} ({worst_ms:.1f} ms)")

    if failures:
        joined = ", ".join(failures)
        raise SystemExit(f"threshold {args.threshold_ms:.1f} ms exceeded: {joined}")
    print(f"all scenarios stayed within {args.threshold_ms:.1f} ms")


if __name__ == "__main__":
    main()
