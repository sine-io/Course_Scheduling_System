"""Excel-only reference import plan and PostgreSQL SQL renderer.

The existing reference importer combines the teacher arrangement workbook with
the school's Word scheduling rules.  This module deliberately handles the
first, smaller import step: facts explicitly present in the workbook only.
It does not invent missing weekly periods, split ``3+2`` into unnamed courses,
or create a timetable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.models.basedata import ClassTrack
from app.services.reference_import import (
    CLASS_NAMES,
    MAJOR_SUBJECTS,
    TARGET_ACADEMIC_YEAR,
    TARGET_END,
    TARGET_START,
    TARGET_TERM,
    _canonical_subject,
    _parse_xlsx,
    _sha,
)

XLSX_ADAPTER_VERSION = "reference-xlsx-v1"
ZERO_SHA256 = "0" * 64
_PRIMARY_PERIOD_RE = re.compile(r"^\s*(\d+)")
_PHYSICAL_SPLIT_RE = re.compile(
    r"(?P<teacher>[\u4e00-\u9fff]{2,4})\s*7\.5班(?P<count>[一二两三四五六七八九十\d]+)节体育"
)
_CHINESE_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


@dataclass(frozen=True, slots=True)
class XlsxAssignment:
    class_name: str
    grade: int
    subject: str
    periods: int
    teacher: str | None
    source_key: str
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "grade": self.grade,
            "subject": self.subject,
            "periods": self.periods,
            "teacher": self.teacher,
            "source_key": self.source_key,
            "notes": self.notes,
        }


@dataclass(slots=True)
class XlsxReferencePlan:
    xlsx_filename: str
    xlsx_sha256: str
    fingerprint: str
    classes: list[dict[str, Any]] = field(default_factory=list)
    subjects: list[dict[str, Any]] = field(default_factory=list)
    teachers: dict[str, dict[str, Any]] = field(default_factory=dict)
    teacher_subjects: list[dict[str, str]] = field(default_factory=list)
    assignments: list[XlsxAssignment] = field(default_factory=list)
    source_rows: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    composite_periods: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_periods(self) -> int:
        return sum(row.periods for row in self.assignments)

    def as_dict(self) -> dict[str, Any]:
        return {
            "adapter_version": XLSX_ADAPTER_VERSION,
            "source_scope": "xlsx-only",
            "fingerprint": self.fingerprint,
            "semester": {
                "academic_year": TARGET_ACADEMIC_YEAR,
                "term": TARGET_TERM,
                "start_date": TARGET_START.isoformat(),
                "end_date": TARGET_END.isoformat(),
            },
            "counts": {
                "classes": len(self.classes),
                "subjects": len(self.subjects),
                "teachers": len(self.teachers),
                "teacher_subjects": len(self.teacher_subjects),
                "assignments": len(self.assignments),
                "periods": self.total_periods,
            },
            "source": {
                "xlsx_filename": self.xlsx_filename,
                "xlsx_sha256": self.xlsx_sha256,
                "word_processed": False,
            },
            "classes": self.classes,
            "subjects": self.subjects,
            "teachers": self.teachers,
            "teacher_subjects": self.teacher_subjects,
            "assignments": [row.as_dict() for row in self.assignments],
            "source_rows": self.source_rows,
            "warnings": self.warnings,
            "unresolved": self.unresolved,
            "composite_periods": self.composite_periods,
        }


def _canonical_xlsx_subject(name: str) -> str:
    canonical = _canonical_subject(name)
    return "心理健康教育" if canonical == "心理" else canonical


def _parse_period_value(value: str | int | float | None) -> tuple[int | None, str | None]:
    raw = str(value or "").strip()
    if not raw:
        return None, None
    match = _PRIMARY_PERIOD_RE.match(raw)
    if match is None:
        return None, raw
    primary = int(match.group(1))
    remainder = raw[match.end() :].strip()
    return primary, remainder or None


def _source_key(class_name: str, subject: str, teacher: str | None) -> str:
    return f"{XLSX_ADAPTER_VERSION}:{class_name}:{subject}:xlsx:{teacher or 'unassigned'}"[:160]


def _period_for(source: Any, subject: str, grade: int) -> tuple[int | None, str | None]:
    value = source.row_periods.get((subject, grade))
    if value is None:
        value = source.row_periods.get((subject, 0))
    # D24:D26 is one merged cell in the workbook; openpyxl exposes the value
    # only on the first row, although it applies to all three grades.
    if not str(value or "").strip() and subject == "体育与健康":
        value = source.row_periods.get((subject, 7))
    return _parse_period_value(value)


def _chinese_number(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    if value == "十":
        return 10
    if value.startswith("十"):
        return 10 + _CHINESE_DIGITS.get(value[1:], 0)
    if value.endswith("十"):
        return _CHINESE_DIGITS.get(value[0], 0) * 10
    if len(value) == 2 and value[0] in _CHINESE_DIGITS and value[1] in _CHINESE_DIGITS:
        return _CHINESE_DIGITS[value[0]] * 10 + _CHINESE_DIGITS[value[1]]
    return _CHINESE_DIGITS.get(value)


def _physical_split(source: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for raw_row in source.raw_rows:
        if "体育与健康" not in raw_row or "7.5班" not in raw_row:
            continue
        for match in _PHYSICAL_SPLIT_RE.finditer(raw_row):
            count = _chinese_number(match.group("count"))
            if count is not None:
                result[match.group("teacher")] = count
    return result


def build_xlsx_plan(
    xlsx_bytes: bytes,
    *,
    xlsx_filename: str = "教师安排8.24.xlsx",
) -> XlsxReferencePlan:
    """Normalize facts from the workbook without using the Word rules file."""

    source = _parse_xlsx(xlsx_bytes, include_word_history_fallback=False)
    xlsx_sha256 = _sha(xlsx_bytes)
    warnings = [
        "本批次只处理 Excel；未读取排课规则.docx，不生成排课规则、固定课位或草稿课表",
        "费用、现有人数和缺口只保留在来源行摘要中，不会冒充教师或课时",
        "复合课时只取周课时字段中的第一个数字；加号后的附加课时不拆成未命名课程",
        "空白周课时、没有明确班级的年级范围只保留为警告，不生成教学任务",
        "如果目标学期没有作息表，SQL 会补一个‘初中五天八节’基础作息表；这不是 Excel 课表",
        "已有人工数据只复用，不覆盖；SQL 发现关键字段冲突时会回滚",
    ]
    classes = [
        {
            "name": name,
            "grade": grade,
            "track": ClassTrack.junior_high.value,
            "homeroom_teacher": source.class_teachers.get(name),
        }
        for grade in (7, 8, 9)
        for name in CLASS_NAMES[grade]
    ]

    source_subjects = {
        _canonical_xlsx_subject(subject)
        for subject, _ in source.row_periods
        if subject != "校医"
    }
    source_subjects.update(
        _canonical_xlsx_subject(subject)
        for subject, _ in source.mappings
        if subject != "校医"
    )
    source_subjects.update(
        _canonical_xlsx_subject(subject)
        for names in source.teacher_subjects.values()
        for subject in names
        if subject != "校医"
    )
    subjects = [
        {
            "name": name,
            "is_major": name in MAJOR_SUBJECTS,
            "required_room_type": None,
        }
        for name in sorted(source_subjects)
    ]
    teachers = {
        name: {
            "notes": "；".join(info["notes"]),
            "external": bool(info.get("external")),
            "admin": bool(info.get("admin")),
            "maternity": bool(info.get("maternity")),
        }
        for name, info in sorted(source.teachers.items())
        if name != "金铭"
    }
    teacher_subjects = [
        {"teacher": teacher, "subject": _canonical_xlsx_subject(subject)}
        for teacher, source_names in sorted(source.teacher_subjects.items())
        if teacher != "金铭"
        for subject in sorted(source_names)
        if subject != "校医"
    ]

    assignments: list[XlsxAssignment] = []
    unresolved: list[dict[str, Any]] = []
    composite_periods: list[dict[str, Any]] = []
    physical_split = _physical_split(source)
    for (source_subject, grade), class_map in sorted(source.mappings.items()):
        subject = _canonical_xlsx_subject(source_subject)
        if subject == "心理健康教育":
            continue
        periods, extra = _period_for(source, source_subject, grade)
        if extra:
            composite_periods.append(
                {
                    "subject": subject,
                    "grade": grade,
                    "raw": str(source.row_periods.get((source_subject, grade))
                               or source.row_periods.get((source_subject, 0))
                               or ""),
                    "primary_periods": periods,
                    "unmodeled_suffix": extra,
                }
            )
        for class_name, names in sorted(class_map.items()):
            if periods is None:
                unresolved.append(
                    {
                        "class_name": class_name,
                        "grade": grade,
                        "subject": subject,
                        "teacher_names": names,
                        "reason": "周课时为空或无法解析",
                    }
                )
                continue
            if not names:
                unresolved.append(
                    {
                        "class_name": class_name,
                        "grade": grade,
                        "subject": subject,
                        "teacher_names": [],
                        "reason": "没有教师映射",
                    }
                )
                continue
            if subject == "体育与健康" and class_name == "7.5" and len(names) > 1:
                split_names = [(name, physical_split.get(name)) for name in names]
                if all(count is not None for _, count in split_names):
                    for teacher, count in split_names:
                        assignments.append(
                            XlsxAssignment(
                                class_name=class_name,
                                grade=grade,
                                subject=subject,
                                periods=int(count),
                                teacher=teacher,
                                source_key=_source_key(class_name, subject, teacher),
                                notes="Excel 明确的 7.5 班体育分工",
                            )
                        )
                    continue
                unresolved.append(
                    {
                        "class_name": class_name,
                        "grade": grade,
                        "subject": subject,
                        "teacher_names": names,
                        "reason": "多位教师但未能解析每位教师的分工课时",
                    }
                )
                continue
            teacher = names[0]
            if len(names) > 1:
                warnings.append(
                    f"{class_name} 的{subject}存在多位教师 {', '.join(names)}，"
                    f"只按首位教师 {teacher} 建立任务"
                )
            assignments.append(
                XlsxAssignment(
                    class_name=class_name,
                    grade=grade,
                    subject=subject,
                    periods=periods,
                    teacher=teacher,
                    source_key=_source_key(class_name, subject, teacher),
                    notes="Excel 周课时主值",
                )
            )

    for item in unresolved:
        warnings.append(
            f"{item['class_name']} 的{item['subject']}未生成教学任务：{item['reason']}"
        )
    for item in composite_periods:
        warnings.append(
            f"{item['subject']} {item['grade']}年级周课时 {item['raw']} "
            f"只写入 {item['primary_periods']} 节，"
            f"未命名附加课时 {item['unmodeled_suffix']} 留在来源摘要"
        )
    if "心理健康教育" in source_subjects:
        warnings.append("心理健康教育只有周期说明，没有明确班级教师映射，未生成教学任务")

    fingerprint_payload = {
        "adapter": XLSX_ADAPTER_VERSION,
        "xlsx": xlsx_sha256,
        "assignments": [row.as_dict() for row in assignments],
        "classes": classes,
        "teachers": teachers,
        "source_rows": source.source_rows,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return XlsxReferencePlan(
        xlsx_filename=xlsx_filename,
        xlsx_sha256=xlsx_sha256,
        fingerprint=fingerprint,
        classes=classes,
        subjects=subjects,
        teachers=teachers,
        teacher_subjects=teacher_subjects,
        assignments=assignments,
        source_rows=source.source_rows,
        warnings=list(dict.fromkeys(warnings)),
        unresolved=unresolved,
        composite_periods=composite_periods,
    )


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return f"'{encoded.replace(chr(39), chr(39) * 2)}'::json"
    text = str(value).replace("'", "''")
    return f"'{text}'"


def _values(rows: list[tuple[Any, ...]]) -> str:
    if not rows:
        return ""
    return ",\n".join(
        "    (" + ", ".join(_sql_literal(value) for value in row) + ")" for row in rows
    )


def render_sql(plan: XlsxReferencePlan) -> str:
    """Render a repeatable PostgreSQL script for an Excel-only plan."""

    teacher_rows = [
        (
            name,
            bool(info.get("external")),
            "行政" if info.get("admin") else None,
            info.get("notes", ""),
        )
        for name, info in plan.teachers.items()
    ]
    subject_rows = [
        (item["name"], item["is_major"], item.get("required_room_type"))
        for item in plan.subjects
    ]
    class_rows = [
        (item["name"], item["grade"], item["track"], item.get("homeroom_teacher"))
        for item in plan.classes
    ]
    teacher_subject_rows = [(item["teacher"], item["subject"]) for item in plan.teacher_subjects]
    assignment_rows = [
        (row.class_name, row.subject, row.periods, row.teacher, row.source_key)
        for row in plan.assignments
    ]
    summary = {
        "source_scope": "xlsx-only",
        "adapter_version": XLSX_ADAPTER_VERSION,
        "xlsx_filename": plan.xlsx_filename,
        "xlsx_sha256": plan.xlsx_sha256,
        "word_processed": False,
        "counts": plan.as_dict()["counts"],
        "classes": plan.classes,
        "subjects": plan.subjects,
        "teachers": plan.teachers,
        "teacher_subjects": plan.teacher_subjects,
        "assignments": [row.as_dict() for row in plan.assignments],
        "source_rows": plan.source_rows,
        "warnings": plan.warnings,
        "unresolved": plan.unresolved,
        "composite_periods": plan.composite_periods,
    }
    warning_comments = "\n".join(f"-- WARNING: {warning}" for warning in plan.warnings)
    zero_sha = _sql_literal(ZERO_SHA256)
    return f"""\\set ON_ERROR_STOP on
-- Generated by {XLSX_ADAPTER_VERSION}; source: {plan.xlsx_filename}
-- This script processes the workbook only. It does not create a timetable.
-- Re-run is idempotent by business keys and reference_source_key.
{warning_comments}

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $$
BEGIN
    IF to_regclass('public.reference_import_batches') IS NULL
       OR NOT EXISTS (
           SELECT 1
           FROM information_schema.columns
           WHERE table_schema = 'public'
             AND table_name = 'course_assignments'
             AND column_name = 'reference_source_key'
       ) THEN
        RAISE EXCEPTION
            '数据库未执行到迁移 0032_reference_file_import 或更高版本，不能运行教师安排 SQL';
    END IF;
END $$;

CREATE TEMP TABLE _xlsx_semester (id integer PRIMARY KEY) ON COMMIT DROP;
CREATE TEMP TABLE _xlsx_period_table (id integer PRIMARY KEY) ON COMMIT DROP;
CREATE TEMP TABLE _xlsx_teachers (
    name varchar(32) PRIMARY KEY,
    is_external boolean NOT NULL,
    admin_title varchar(32),
    notes text NOT NULL
) ON COMMIT DROP;
CREATE TEMP TABLE _xlsx_subjects (
    name varchar(64) PRIMARY KEY,
    is_major boolean NOT NULL,
    required_room_type varchar(20)
) ON COMMIT DROP;
CREATE TEMP TABLE _xlsx_classes (
    name varchar(32) PRIMARY KEY,
    grade integer NOT NULL,
    track varchar(20) NOT NULL,
    homeroom_teacher varchar(32)
) ON COMMIT DROP;
CREATE TEMP TABLE _xlsx_teacher_subjects (
    teacher_name varchar(32) NOT NULL,
    subject_name varchar(64) NOT NULL,
    PRIMARY KEY (teacher_name, subject_name)
) ON COMMIT DROP;
CREATE TEMP TABLE _xlsx_assignments (
    class_name varchar(32) NOT NULL,
    subject_name varchar(64) NOT NULL,
    periods integer NOT NULL,
    teacher_name varchar(32),
    source_key varchar(160) PRIMARY KEY
) ON COMMIT DROP;

INSERT INTO _xlsx_teachers (name, is_external, admin_title, notes) VALUES
{_values(teacher_rows)};
INSERT INTO _xlsx_subjects (name, is_major, required_room_type) VALUES
{_values(subject_rows)};
INSERT INTO _xlsx_classes (name, grade, track, homeroom_teacher) VALUES
{_values(class_rows)};
INSERT INTO _xlsx_teacher_subjects (teacher_name, subject_name) VALUES
{_values(teacher_subject_rows)};
INSERT INTO _xlsx_assignments (class_name, subject_name, periods, teacher_name, source_key) VALUES
{_values(assignment_rows)};

INSERT INTO _xlsx_semester (id)
SELECT id
FROM semesters
WHERE academic_year = {TARGET_ACADEMIC_YEAR} AND term = {TARGET_TERM}
FOR UPDATE;

DO $$
DECLARE
    semester_row record;
BEGIN
    SELECT s.* INTO semester_row
    FROM semesters AS s
    JOIN _xlsx_semester AS target ON target.id = s.id;
    IF NOT FOUND THEN
        RAISE EXCEPTION '找不到 2026-2027 第 1 学期';
    END IF;
    IF semester_row.start_date IS DISTINCT FROM DATE { _sql_literal(TARGET_START.isoformat()) }
       OR semester_row.end_date IS DISTINCT FROM DATE { _sql_literal(TARGET_END.isoformat()) } THEN
        RAISE EXCEPTION '目标学期日期不符：需要 2026-09-01 至 2027-01-25';
    END IF;
END $$;

DO $$
DECLARE
    duplicate_row record;
BEGIN
    FOR duplicate_row IN
        SELECT teacher.name, count(*) AS row_count
        FROM teachers AS teacher
        JOIN _xlsx_semester AS semester ON semester.id = teacher.semester_id
        GROUP BY teacher.name
        HAVING count(*) > 1
    LOOP
        RAISE EXCEPTION
            '目标学期教师 % 存在 % 条同名记录，无法按自然键导入，已中止且未覆盖',
            duplicate_row.name, duplicate_row.row_count;
    END LOOP;
    FOR duplicate_row IN
        SELECT subject.name, count(*) AS row_count
        FROM subjects AS subject
        JOIN _xlsx_semester AS semester ON semester.id = subject.semester_id
        GROUP BY subject.name
        HAVING count(*) > 1
    LOOP
        RAISE EXCEPTION
            '目标学期科目 % 存在 % 条同名记录，无法按自然键导入，已中止且未覆盖',
            duplicate_row.name, duplicate_row.row_count;
    END LOOP;
END $$;

DO $$
DECLARE
    source_row record;
    existing_row record;
BEGIN
    FOR source_row IN SELECT * FROM _xlsx_teachers ORDER BY name LOOP
        SELECT t.is_external INTO existing_row
        FROM teachers AS t
        JOIN _xlsx_semester AS semester ON semester.id = t.semester_id
        WHERE t.name = source_row.name;
        IF FOUND AND existing_row.is_external IS DISTINCT FROM source_row.is_external THEN
            RAISE EXCEPTION '教师 % 的 is_external 与 Excel 冲突，已中止且未覆盖', source_row.name;
        END IF;
    END LOOP;
    FOR source_row IN SELECT * FROM _xlsx_subjects ORDER BY name LOOP
        SELECT s.is_major INTO existing_row
        FROM subjects AS s
        JOIN _xlsx_semester AS semester ON semester.id = s.semester_id
        WHERE s.name = source_row.name;
        IF FOUND AND existing_row.is_major IS DISTINCT FROM source_row.is_major THEN
            RAISE EXCEPTION
                '科目 % 的 is_major 与 Excel 归一化结果冲突，已中止且未覆盖', source_row.name;
        END IF;
    END LOOP;
END $$;

INSERT INTO period_tables (semester_id, name, num_weekdays, is_default)
SELECT semester.id, '初中五天八节', 5, TRUE
FROM _xlsx_semester AS semester
WHERE NOT EXISTS (
    SELECT 1 FROM period_tables AS table_row WHERE table_row.semester_id = semester.id
);
INSERT INTO _xlsx_period_table (id)
SELECT id
FROM period_tables
WHERE semester_id = (SELECT id FROM _xlsx_semester)
ORDER BY is_default DESC, id
LIMIT 1;
INSERT INTO periods (period_table_id, weekday, period_no, name, type)
SELECT table_row.id, weekday_no, period_no, '第' || period_no || '节', 'regular'
FROM _xlsx_period_table AS table_row
CROSS JOIN generate_series(1, 5) AS weekday_no
CROSS JOIN generate_series(1, 8) AS period_no
ON CONFLICT (period_table_id, weekday, period_no) DO NOTHING;

INSERT INTO teachers (
    semester_id, name, base_periods, admin_title, admin_reduction,
    is_external, is_active
)
SELECT semester.id, source_row.name, 0, source_row.admin_title, 0,
       source_row.is_external, TRUE
FROM _xlsx_teachers AS source_row
CROSS JOIN _xlsx_semester AS semester
WHERE NOT EXISTS (
    SELECT 1 FROM teachers AS existing
    WHERE existing.semester_id = semester.id AND existing.name = source_row.name
);
INSERT INTO subjects (semester_id, name, is_major, required_room_type)
SELECT semester.id, source_row.name, source_row.is_major, source_row.required_room_type
FROM _xlsx_subjects AS source_row
CROSS JOIN _xlsx_semester AS semester
WHERE NOT EXISTS (
    SELECT 1 FROM subjects AS existing
    WHERE existing.semester_id = semester.id AND existing.name = source_row.name
);

DO $$
DECLARE
    source_row record;
    existing_row record;
    teacher_id integer;
BEGIN
    FOR source_row IN SELECT * FROM _xlsx_classes ORDER BY name LOOP
        SELECT c.grade, c.track, c.homeroom_teacher_id INTO existing_row
        FROM class_units AS c
        JOIN _xlsx_semester AS semester ON semester.id = c.semester_id
        WHERE c.name = source_row.name;
        IF NOT FOUND THEN
            CONTINUE;
        END IF;
        IF existing_row.grade IS DISTINCT FROM source_row.grade THEN
            RAISE EXCEPTION '班级 % 的年级与 Excel 冲突，已中止且未覆盖', source_row.name;
        END IF;
        IF existing_row.track IS DISTINCT FROM source_row.track THEN
            RAISE EXCEPTION '班级 % 的学制与 Excel 冲突，已中止且未覆盖', source_row.name;
        END IF;
        IF source_row.homeroom_teacher IS NOT NULL THEN
            SELECT t.id INTO teacher_id
            FROM teachers AS t
            JOIN _xlsx_semester AS semester ON semester.id = t.semester_id
            WHERE t.name = source_row.homeroom_teacher;
            IF existing_row.homeroom_teacher_id IS NOT NULL
               AND existing_row.homeroom_teacher_id IS DISTINCT FROM teacher_id THEN
                RAISE EXCEPTION '班级 % 的班主任与 Excel 冲突，已中止且未覆盖', source_row.name;
            END IF;
        END IF;
    END LOOP;
END $$;

INSERT INTO class_units (
    semester_id, grade, name, track, homeroom_teacher_id, period_table_id
)
SELECT semester.id, source_row.grade, source_row.name, source_row.track,
       teacher.id, (SELECT id FROM _xlsx_period_table)
FROM _xlsx_classes AS source_row
CROSS JOIN _xlsx_semester AS semester
LEFT JOIN teachers AS teacher
    ON teacher.semester_id = semester.id AND teacher.name = source_row.homeroom_teacher
WHERE NOT EXISTS (
    SELECT 1 FROM class_units AS existing
    WHERE existing.semester_id = semester.id AND existing.name = source_row.name
);
UPDATE class_units AS class_row
SET period_table_id = (SELECT id FROM _xlsx_period_table)
FROM _xlsx_classes AS source_row
JOIN _xlsx_semester AS semester ON TRUE
WHERE class_row.semester_id = semester.id
  AND class_row.name = source_row.name
  AND class_row.period_table_id IS NULL;
UPDATE class_units AS class_row
SET homeroom_teacher_id = teacher.id
FROM _xlsx_classes AS source_row
JOIN _xlsx_semester AS semester ON TRUE
JOIN teachers AS teacher
  ON teacher.semester_id = semester.id AND teacher.name = source_row.homeroom_teacher
WHERE class_row.semester_id = semester.id
  AND class_row.name = source_row.name
  AND class_row.homeroom_teacher_id IS NULL
  AND source_row.homeroom_teacher IS NOT NULL;

INSERT INTO scheduling_units (semester_id, unit_type, name)
SELECT semester.id, 'single', class_row.name
FROM class_units AS class_row
JOIN _xlsx_semester AS semester ON semester.id = class_row.semester_id
JOIN _xlsx_classes AS source_row ON source_row.name = class_row.name
WHERE NOT EXISTS (
    SELECT 1
    FROM scheduling_units AS unit
    JOIN scheduling_unit_members AS member ON member.scheduling_unit_id = unit.id
    WHERE unit.semester_id = semester.id
      AND unit.unit_type = 'single'
      AND member.class_unit_id = class_row.id
);
INSERT INTO scheduling_unit_members (scheduling_unit_id, class_unit_id)
SELECT unit.id, class_row.id
FROM scheduling_units AS unit
JOIN class_units AS class_row
  ON class_row.semester_id = unit.semester_id AND class_row.name = unit.name
JOIN _xlsx_semester AS semester ON semester.id = unit.semester_id
WHERE unit.unit_type = 'single'
  AND NOT EXISTS (
      SELECT 1 FROM scheduling_unit_members AS member
      WHERE member.scheduling_unit_id = unit.id AND member.class_unit_id = class_row.id
  );

DO $$
DECLARE
    duplicate_row record;
BEGIN
    FOR duplicate_row IN
        SELECT class_row.name, count(*) AS unit_count
        FROM _xlsx_classes AS source_row
        JOIN _xlsx_semester AS semester ON TRUE
        JOIN class_units AS class_row
          ON class_row.semester_id = semester.id AND class_row.name = source_row.name
        JOIN scheduling_unit_members AS member ON member.class_unit_id = class_row.id
        JOIN scheduling_units AS unit
          ON unit.id = member.scheduling_unit_id AND unit.unit_type = 'single'
        GROUP BY class_row.name
        HAVING count(*) <> 1
    LOOP
        RAISE EXCEPTION '班级 % 存在 % 个 single 排课单位，无法确定导入目标，已中止且未覆盖',
            duplicate_row.name, duplicate_row.unit_count;
    END LOOP;
END $$;

DO $$
DECLARE
    source_row record;
    existing_row record;
    unit_id integer;
    expected_subject_id integer;
    expected_teacher_id integer;
    existing_teacher_count integer;
BEGIN
    FOR source_row IN SELECT * FROM _xlsx_assignments ORDER BY source_key LOOP
        SELECT unit.id, subject.id INTO unit_id, expected_subject_id
        FROM scheduling_units AS unit
        JOIN scheduling_unit_members AS member ON member.scheduling_unit_id = unit.id
        JOIN class_units AS class_row ON class_row.id = member.class_unit_id
        JOIN subjects AS subject
          ON subject.semester_id = unit.semester_id AND subject.name = source_row.subject_name
        JOIN _xlsx_semester AS semester ON semester.id = unit.semester_id
        WHERE unit.unit_type = 'single' AND class_row.name = source_row.class_name;
        IF NOT FOUND THEN
            RAISE EXCEPTION
                '班级 % 或科目 % 尚未建立可用的 single 排课单位，已中止且未覆盖',
                source_row.class_name, source_row.subject_name;
        END IF;
        SELECT assignment.periods_per_week, assignment.scheduling_unit_id, assignment.subject_id
            INTO existing_row
        FROM course_assignments AS assignment
        JOIN _xlsx_semester AS semester ON semester.id = assignment.semester_id
        WHERE assignment.reference_source_key = source_row.source_key;
        IF NOT FOUND THEN
            IF EXISTS (
                SELECT 1
                FROM course_assignments AS assignment
                JOIN scheduling_unit_members AS member
                  ON member.scheduling_unit_id = assignment.scheduling_unit_id
                JOIN class_units AS class_row ON class_row.id = member.class_unit_id
                JOIN _xlsx_semester AS semester ON semester.id = assignment.semester_id
                WHERE class_row.name = source_row.class_name
                  AND assignment.subject_id = expected_subject_id
                  AND NOT EXISTS (
                      SELECT 1
                      FROM _xlsx_assignments AS incoming
                      WHERE incoming.source_key = assignment.reference_source_key
                  )
            ) THEN
                RAISE EXCEPTION
                    '班级 % 的科目 % 已存在未被本次 Excel 识别的教学任务，已中止且未覆盖',
                    source_row.class_name, source_row.subject_name;
            END IF;
            CONTINUE;
        END IF;
        IF existing_row.periods_per_week IS DISTINCT FROM source_row.periods
           OR existing_row.scheduling_unit_id IS DISTINCT FROM unit_id
           OR existing_row.subject_id IS DISTINCT FROM expected_subject_id THEN
            RAISE EXCEPTION
                '教学任务 % 的关键字段与 Excel 冲突，已中止且未覆盖', source_row.source_key;
        END IF;
        SELECT t.id INTO expected_teacher_id
        FROM teachers AS t
        JOIN _xlsx_semester AS semester ON semester.id = t.semester_id
        WHERE t.name = source_row.teacher_name;
        SELECT count(*) INTO existing_teacher_count
        FROM assignment_teachers AS assignment_teacher
        JOIN course_assignments AS assignment
          ON assignment.id = assignment_teacher.course_assignment_id
        WHERE assignment.reference_source_key = source_row.source_key;
        IF source_row.teacher_name IS NULL AND existing_teacher_count <> 0 THEN
            RAISE EXCEPTION
                '教学任务 % 已有教师关联，与 Excel 冲突，已中止且未覆盖', source_row.source_key;
        END IF;
        IF source_row.teacher_name IS NOT NULL AND (
            existing_teacher_count <> 1
            OR NOT EXISTS (
                SELECT 1
                FROM assignment_teachers AS assignment_teacher
                JOIN course_assignments AS assignment
                  ON assignment.id = assignment_teacher.course_assignment_id
                WHERE assignment.reference_source_key = source_row.source_key
                  AND assignment_teacher.teacher_id = expected_teacher_id
            )
        ) THEN
            RAISE EXCEPTION
                '教学任务 % 的教师关联与 Excel 冲突，已中止且未覆盖', source_row.source_key;
        END IF;
    END LOOP;
END $$;

INSERT INTO course_assignments (
    semester_id, scheduling_unit_id, subject_id, periods_per_week,
    required_room_type, reference_source_key
)
SELECT semester.id, unit.id, subject.id, source_row.periods,
       subject.required_room_type, source_row.source_key
FROM _xlsx_assignments AS source_row
JOIN _xlsx_semester AS semester ON TRUE
JOIN subjects AS subject
  ON subject.semester_id = semester.id AND subject.name = source_row.subject_name
JOIN class_units AS class_row
  ON class_row.semester_id = semester.id AND class_row.name = source_row.class_name
JOIN scheduling_unit_members AS member ON member.class_unit_id = class_row.id
JOIN scheduling_units AS unit
  ON unit.id = member.scheduling_unit_id AND unit.unit_type = 'single'
ON CONFLICT (semester_id, reference_source_key) DO NOTHING;

INSERT INTO assignment_teachers (course_assignment_id, teacher_id, is_lead)
SELECT assignment.id, teacher.id, TRUE
FROM course_assignments AS assignment
JOIN _xlsx_assignments AS source_row
  ON source_row.source_key = assignment.reference_source_key
JOIN _xlsx_semester AS semester ON semester.id = assignment.semester_id
JOIN teachers AS teacher
  ON teacher.semester_id = semester.id AND teacher.name = source_row.teacher_name
WHERE source_row.teacher_name IS NOT NULL
ON CONFLICT (course_assignment_id, teacher_id) DO NOTHING;

INSERT INTO teacher_subjects (teacher_id, subject_id)
SELECT teacher.id, subject.id
FROM _xlsx_teacher_subjects AS source_row
JOIN _xlsx_semester AS semester ON TRUE
JOIN teachers AS teacher
  ON teacher.semester_id = semester.id AND teacher.name = source_row.teacher_name
JOIN subjects AS subject
  ON subject.semester_id = semester.id AND subject.name = source_row.subject_name
ON CONFLICT (teacher_id, subject_id) DO NOTHING;

DO $$
DECLARE
    expected_count integer := {len(plan.assignments)};
    actual_count integer;
    expected_periods integer := {plan.total_periods};
    actual_periods integer;
BEGIN
    SELECT count(*), coalesce(sum(assignment.periods_per_week), 0)
        INTO actual_count, actual_periods
    FROM course_assignments AS assignment
    JOIN _xlsx_assignments AS source_row
      ON source_row.source_key = assignment.reference_source_key
    JOIN _xlsx_semester AS semester ON semester.id = assignment.semester_id;
    IF actual_count <> expected_count OR actual_periods <> expected_periods THEN
        RAISE EXCEPTION 'Excel 教学任务校验失败：需要 % 条/% 节，实际 % 条/% 节',
            expected_count, expected_periods, actual_count, actual_periods;
    END IF;
END $$;

INSERT INTO reference_import_batches (
    semester_id, fingerprint, adapter_version, word_filename, xlsx_filename,
    word_sha256, xlsx_sha256, decisions, summary
)
SELECT semester.id,
       {_sql_literal(plan.fingerprint)},
       {_sql_literal(XLSX_ADAPTER_VERSION)},
       '(not processed)',
       {_sql_literal(plan.xlsx_filename)},
       {zero_sha},
       {_sql_literal(plan.xlsx_sha256)},
       {_sql_literal({"source_scope": "xlsx-only", "word_processed": False})},
       {_sql_literal(summary)}
FROM _xlsx_semester AS semester
WHERE NOT EXISTS (
    SELECT 1
    FROM reference_import_batches AS batch
    WHERE batch.semester_id = semester.id
      AND batch.fingerprint = {_sql_literal(plan.fingerprint)}
);

COMMIT;
"""


def write_outputs(plan: XlsxReferencePlan, sql_path: Path, report_path: Path) -> None:
    sql_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    sql_path.write_text(render_sql(plan), encoding="utf-8")
    report_path.write_text(
        json.dumps(plan.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="根据教师安排 Excel 生成 PostgreSQL 导入 SQL")
    parser.add_argument("--xlsx", type=Path, required=True, help="教师安排工作簿路径")
    parser.add_argument("--sql", type=Path, required=True, help="SQL 输出路径")
    parser.add_argument("--report", type=Path, required=True, help="归一化报告 JSON 输出路径")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="发现未解析周课时或复合课时时以非零状态退出",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    plan = build_xlsx_plan(args.xlsx.read_bytes(), xlsx_filename=args.xlsx.name)
    if args.strict and (plan.unresolved or plan.composite_periods):
        for warning in plan.warnings:
            print(f"WARNING: {warning}")
        return 2
    write_outputs(plan, args.sql, args.report)
    print(
        f"generated SQL={args.sql} report={args.report} "
        f"assignments={len(plan.assignments)} periods={plan.total_periods} "
        f"warnings={len(plan.warnings)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
