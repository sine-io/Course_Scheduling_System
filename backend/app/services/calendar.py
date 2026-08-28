"""校历特殊日期解析与排课准备检查。"""

import logging
from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assignment import CourseAssignment
from app.models.basedata import ClassUnit
from app.models.calendar import CalendarExceptionKind, SemesterCalendarException
from app.models.period import Period, PeriodTable, PeriodType
from app.models.semester import Semester
from app.models.teacher_arrangement_import import TeacherArrangementImportBatch
from app.services.solver_data import load_problem
from app.solver import preflight

logger = logging.getLogger(__name__)


def exception_for(db: Session, semester_id: int, day: date) -> SemesterCalendarException | None:
    return db.scalar(
        select(SemesterCalendarException).where(
            SemesterCalendarException.semester_id == semester_id,
            SemesterCalendarException.date == day,
        )
    )


def effective_weekday(db: Session, semester_id: int, day: date) -> int | None:
    """把实际日期解析成该日使用的周课表星期。

    普通日返回自然星期；停课日返回 None；周末补课返回设置的星期一至六。
    """
    exception = exception_for(db, semester_id, day)
    if exception is None:
        return day.isoweekday()
    if exception.kind == CalendarExceptionKind.no_instruction.value:
        return None
    return exception.makeup_weekday


def is_instruction_day(
    db: Session, semester_id: int, day: date, period_table_id: int | None = None
) -> bool:
    weekday = effective_weekday(db, semester_id, day)
    if weekday is None:
        return False
    if period_table_id is None:
        return True
    return bool(
        db.scalar(
            select(func.count())
            .select_from(Period)
            .where(
                Period.period_table_id == period_table_id,
                Period.weekday == weekday,
                Period.type == PeriodType.regular.value,
            )
        )
    )


def _issue(code: str, message: str, subject_type: str, subject_id: int) -> dict[str, Any]:
    return {
        "level": "error",
        "code": code,
        "message": message,
        "subject_type": subject_type,
        "subject_id": subject_id,
    }


def _base_readiness_issues(db: Session, semester: Semester) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if semester.start_date is None or semester.end_date is None:
        issues.append(
            _issue("semester_dates_missing", "请先设置学期起止日期", "semester", semester.id)
        )
    elif semester.end_date < semester.start_date:
        issues.append(
            _issue(
                "semester_dates_invalid",
                "学期结束日期不能早于开始日期",
                "semester",
                semester.id,
            )
        )

    tables = list(
        db.scalars(select(PeriodTable).where(PeriodTable.semester_id == semester.id))
    )
    if not tables:
        issues.append(
            _issue(
                "period_table_missing",
                "请先创建至少一套作息时间表",
                "semester",
                semester.id,
            )
        )
    elif not any(
        db.scalar(
            select(func.count())
            .select_from(Period)
            .where(
                Period.period_table_id == table.id,
                Period.type == PeriodType.regular.value,
            )
        )
        for table in tables
    ):
        issues.append(
            _issue(
                "regular_period_missing",
                "作息时间表至少需要一个可排课节次",
                "semester",
                semester.id,
            )
        )
    return issues


def _has_ready_import(db: Session, semester_id: int) -> bool:
    return bool(
        db.scalar(
            select(func.count())
            .select_from(TeacherArrangementImportBatch)
            .where(
                TeacherArrangementImportBatch.semester_id == semester_id,
                TeacherArrangementImportBatch.mode == "scheduling_ready",
            )
        )
    )


def _ready_import_issues(db: Session, semester: Semester) -> list[dict[str, Any]]:
    if not _has_ready_import(db, semester.id):
        return []
    classes = list(
        db.scalars(select(ClassUnit).where(ClassUnit.semester_id == semester.id))
    )
    assignments = list(
        db.scalars(
            select(CourseAssignment).where(CourseAssignment.semester_id == semester.id)
        )
    )
    issues: list[dict[str, Any]] = []
    assigned_by_class: dict[int, int] = defaultdict(int)
    for assignment in assignments:
        if not assignment.teachers:
            issues.append(
                _issue(
                    "assignment_teacher_missing",
                    f"教学任务“{assignment.task_code or assignment.id}”尚未指定教师",
                    "assignment",
                    assignment.id,
                )
            )
        for member in assignment.scheduling_unit.members:
            assigned_by_class[member.class_unit_id] += assignment.periods_per_week

    referenced_table_ids = {
        class_unit.period_table_id
        for class_unit in classes
        if class_unit.period_table_id is not None
    }
    periods = list(
        db.scalars(
            select(Period).where(Period.period_table_id.in_(referenced_table_ids))
        )
    ) if referenced_table_ids else []
    periods_by_table: dict[int, list[Period]] = defaultdict(list)
    for period in periods:
        periods_by_table[period.period_table_id].append(period)
        if (
            period.start_time is None
            or period.end_time is None
            or period.end_time <= period.start_time
        ):
            issues.append(
                _issue(
                    "period_time_invalid",
                    f"作息节次“{period.name}”缺少有效的开始或结束时间",
                    "period",
                    period.id,
                )
            )

    for class_unit in classes:
        if class_unit.period_table_id is None:
            issues.append(
                _issue(
                    "class_period_table_missing",
                    f"班级“{class_unit.name}”尚未绑定作息时间表",
                    "class",
                    class_unit.id,
                )
            )
            continue
        planned = class_unit.planned_weekly_periods
        assigned = assigned_by_class.get(class_unit.id, 0)
        if planned is None or assigned != planned:
            issues.append(
                _issue(
                    "class_assignment_periods_mismatch",
                    (
                        f"班级“{class_unit.name}”计划周课时为 {planned or 0}，"
                        f"教学任务合计为 {assigned}"
                    ),
                    "class",
                    class_unit.id,
                )
            )
        capacity = sum(
            period.type == PeriodType.regular.value
            for period in periods_by_table.get(class_unit.period_table_id, [])
        )
        if planned is not None and planned > capacity:
            issues.append(
                _issue(
                    "class_period_capacity_exceeded",
                    f"班级“{class_unit.name}”计划周课时 {planned} 超过常规课时容量 {capacity}",
                    "class",
                    class_unit.id,
                )
            )
    return issues


def readiness_report(db: Session, semester: Semester) -> dict[str, Any]:
    data_issues = [
        *_base_readiness_issues(db, semester),
        *_ready_import_issues(db, semester),
    ]
    try:
        solver_report = preflight.run(load_problem(db, semester.id))
        solver_issues = [
            {
                "level": issue.level,
                "code": issue.code,
                "message": issue.message,
                "subject_type": issue.subject_type,
                "subject_id": issue.subject_id,
                "detail": issue.detail,
            }
            for issue in solver_report.issues
        ]
    except Exception:
        logger.exception("学期 %s 排课就绪预检失败", semester.id)
        solver_issues = [
            _issue(
                "solver_preflight_failed",
                "求解预检暂时无法完成，请检查排课数据后重试",
                "semester",
                semester.id,
            )
        ]
    solver_errors = [issue for issue in solver_issues if issue["level"] == "error"]
    solver_warnings = [issue for issue in solver_issues if issue["level"] == "warning"]
    checks = [
        {
            "key": "data_integrity",
            "label": "数据完整性",
            "ok": not data_issues,
            "error_count": len(data_issues),
            "warning_count": 0,
            "issues": data_issues,
        },
        {
            "key": "solver_preflight",
            "label": "求解预检",
            "ok": not solver_errors,
            "error_count": len(solver_errors),
            "warning_count": len(solver_warnings),
            "issues": solver_issues,
        },
    ]
    return {"issues": [*data_issues, *solver_errors], "checks": checks}


def readiness_issues(db: Session, semester: Semester) -> list[dict[str, Any]]:
    return readiness_report(db, semester)["issues"]


def validate_exception_date(semester: Semester, day: date) -> None:
    if semester.start_date is not None and day < semester.start_date:
        raise ValueError("特殊日期不能早于学期开始日期")
    if semester.end_date is not None and day > semester.end_date:
        raise ValueError("特殊日期不能晚于学期结束日期")


def validate_exception_fields(kind: str, makeup_weekday: int | None) -> None:
    if kind not in {x.value for x in CalendarExceptionKind}:
        raise ValueError("未知的特殊日期类型")
    if kind == CalendarExceptionKind.makeup_instruction.value and makeup_weekday is None:
        raise ValueError("补课日必须指定使用周一至周六中的课表")
    if kind == CalendarExceptionKind.no_instruction.value and makeup_weekday is not None:
        raise ValueError("停课日不能指定补课课表星期")
