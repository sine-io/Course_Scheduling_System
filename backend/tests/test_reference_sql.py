"""教师安排 Excel-only SQL 导入器的纯解析契约测试。"""

from collections import Counter
from pathlib import Path

from app.services.reference_sql import build_xlsx_plan, render_sql

REPO_ROOT = Path(__file__).resolve().parents[2]
XLSX = REPO_ROOT / "ref" / "教师安排8.24.xlsx"


def test_xlsx_plan_preserves_explicit_assignments_and_source_rows():
    plan = build_xlsx_plan(XLSX.read_bytes(), xlsx_filename=XLSX.name)

    assert plan.as_dict()["counts"] == {
        "classes": 12,
        "subjects": 14,
        "teachers": 43,
        "teacher_subjects": 47,
        "assignments": 124,
        "periods": 369,
    }
    assert "金铭" not in plan.teachers
    assert len(plan.source_rows) == 28
    assert plan.source_rows[0]["fee"] == 2340
    assert plan.source_rows[0]["shortage_staff"] == "缺口2人"

    physical = [
        row for row in plan.assignments if row.class_name == "7.5" and row.subject == "体育与健康"
    ]
    assert {(row.teacher, row.periods) for row in physical} == {("刘锴", 2), ("周嘉辉", 3)}
    assert not any(row.subject == "心理健康教育" for row in plan.assignments)
    assert plan.unresolved == []
    assert len(plan.composite_periods) == 8
    assert any("附加课时" in warning for warning in plan.warnings)

    totals = Counter(row.class_name for row in plan.assignments for _ in range(row.periods))
    assert {name: totals[name] for name in ("7.1", "8.4", "9.1")} == {
        "7.1": 31,
        "8.4": 31,
        "9.1": 30,
    }


def test_rendered_sql_is_xlsx_only_repeatable_and_conflict_failing():
    plan = build_xlsx_plan(XLSX.read_bytes(), xlsx_filename=XLSX.name)
    sql = render_sql(plan)

    assert sql.startswith("\\set ON_ERROR_STOP on")
    assert "reference-xlsx-v1" in sql
    assert "source_rows" in sql
    assert "reference_scheduling_rules" not in sql
    assert "schedule_entries" not in sql
    assert "::json" in sql
    assert "::jsonb" not in sql
    assert "0032_reference_file_import 或更高版本" in sql
    assert "HAVING count(*) <> 1" in sql
    assert "ON CONFLICT (semester_id, reference_source_key) DO NOTHING" in sql
    assert "'" + "0" * 64 + "'" in sql
    assert sql.count("BEGIN;") == 1
    assert sql.count("COMMIT;") == 1
