"""聚合工作空间首页所需的当前学期只读数据。"""

import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.models.basedata import ClassUnit, Teacher
from app.models.leave import AffectedPeriod, AffectedStatus, LeaveRequest, LeaveStatus
from app.models.notification import Notification
from app.models.semester import Semester
from app.models.timetable import Timetable, TimetableStatus
from app.schemas.workspace_overview import (
    WorkspaceActionItemOut,
    WorkspaceMetricsOut,
    WorkspaceOverviewOut,
    WorkspacePreflightOut,
    WorkspaceTimetableOut,
)
from app.services import setup_check, timetable_publish
from app.services.solver_data import load_problem
from app.solver import preflight
from app.solver.preflight import Issue

logger = logging.getLogger(__name__)


def _count(db: Session, model, *criteria) -> int:
    return int(
        db.scalar(select(func.count()).select_from(model).where(*criteria)) or 0
    )


def _selected_timetable(db: Session, semester_id: int) -> Timetable | None:
    for timetable_status in (TimetableStatus.draft, TimetableStatus.published):
        timetable = db.scalar(
            select(Timetable)
            .where(
                Timetable.semester_id == semester_id,
                Timetable.status == timetable_status.value,
            )
            .order_by(Timetable.updated_at.desc(), Timetable.id.desc())
            .limit(1)
        )
        if timetable is not None:
            return timetable
    return None


def _timetable_summary(db: Session, timetable: Timetable | None) -> WorkspaceTimetableOut:
    if timetable is None:
        return WorkspaceTimetableOut()
    summary = timetable_publish.completeness(db, timetable)
    required = int(summary["required"])
    placed = int(summary["placed"])
    return WorkspaceTimetableOut(
        id=timetable.id,
        name=timetable.name,
        status=timetable.status,
        updated_at=timetable.updated_at,
        required_periods=required,
        placed_periods=placed,
        remaining_periods=int(summary["remaining"]),
        completion_rate=round(placed * 100 / required) if required else None,
    )


def _preflight_summary(
    db: Session, semester_id: int
) -> tuple[WorkspacePreflightOut, tuple[Issue, ...]]:
    try:
        report = preflight.run(load_problem(db, semester_id))
    except Exception:  # noqa: BLE001 - 单一派生区块失败不应清空整个首页
        logger.exception("工作空间首页的排课前置检查计算失败", extra={"semester_id": semester_id})
        return (
            WorkspacePreflightOut(
                available=False,
                unavailable_message="排课前置检查暂时无法读取",
            ),
            (),
        )
    return (
        WorkspacePreflightOut(
            error_count=len(report.errors),
            warning_count=len(report.warnings),
        ),
        report.issues,
    )


def _action(
    code: str,
    title: str,
    description: str,
    tone: str,
    target: str,
    count: int | None = None,
) -> WorkspaceActionItemOut:
    return WorkspaceActionItemOut(
        code=code,
        title=title,
        description=description,
        tone=tone,  # type: ignore[arg-type]
        target=target,
        count=count,
    )


_SETUP_WARNING_TITLES = {
    "rooms_missing": "补充教室与场地",
    "teacher_accounts_missing": "绑定教师账号",
    "special_dates_missing": "登记特殊日期",
    "bell_times_missing": "完善铃声时间",
}

_SETUP_WARNING_TARGETS = {
    "rooms_missing": "basedata",
    "teacher_accounts_missing": "wizard",
    "special_dates_missing": "calendar",
    "bell_times_missing": "semesters",
}


def build_overview(db: Session, semester: Semester) -> WorkspaceOverviewOut:
    """Return a role-neutral overview; route permissions decide who may read it."""
    semester_id = semester.id
    today = clock.school_today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    active_teacher_count = _count(
        db,
        Teacher,
        Teacher.semester_id == semester_id,
        Teacher.is_active.is_(True),
    )
    class_count = _count(db, ClassUnit, ClassUnit.semester_id == semester_id)
    weekly_affected = _count(
        db,
        AffectedPeriod,
        AffectedPeriod.semester_id == semester_id,
        AffectedPeriod.date >= week_start,
        AffectedPeriod.date <= week_end,
        AffectedPeriod.status != AffectedStatus.cancelled.value,
        AffectedPeriod.leave_request_id.in_(
            select(LeaveRequest.id).where(
                LeaveRequest.status == LeaveStatus.registered.value
            )
        ),
    )
    today_pending = _count(
        db,
        AffectedPeriod,
        AffectedPeriod.semester_id == semester_id,
        AffectedPeriod.date == today,
        AffectedPeriod.status == AffectedStatus.pending.value,
        AffectedPeriod.leave_request_id.in_(
            select(LeaveRequest.id).where(
                LeaveRequest.status == LeaveStatus.registered.value
            )
        ),
    )
    unacknowledged = _count(
        db,
        Notification,
        Notification.semester_id == semester_id,
        Notification.acknowledged_at.is_(None),
    )

    check = setup_check.build_check(db, semester)
    timetable = _timetable_summary(db, _selected_timetable(db, semester_id))
    preflight_summary, preflight_issues = _preflight_summary(db, semester_id)

    focus_items: list[WorkspaceActionItemOut] = []
    if check.blockers:
        focus_items.append(
            _action(
                "setup_blockers",
                "完成学期准备",
                check.blockers[0].message,
                "critical",
                "wizard",
                len(check.blockers),
            )
        )
    errors = [issue for issue in preflight_issues if issue.level == "error"]
    if errors:
        focus_items.append(
            _action(
                "preflight_errors",
                "处理前置检查问题",
                errors[0].message,
                "critical",
                "auto_schedule",
                len(errors),
            )
        )
    if today_pending:
        focus_items.append(
            _action(
                "today_pending_periods",
                "处理今日调代课",
                "今日仍有受影响节次尚未设置处理方式。",
                "warning",
                "substitutions",
                today_pending,
            )
        )
    if timetable.id is not None and timetable.remaining_periods:
        focus_items.append(
            _action(
                "remaining_periods",
                "继续完成课表",
                f"课表“{timetable.name}”仍有课时尚未排入。",
                "warning",
                "workbench",
                timetable.remaining_periods,
            )
        )
    if unacknowledged:
        focus_items.append(
            _action(
                "unacknowledged_notifications",
                "跟进未确认通知",
                "当前学期仍有通知尚未收到确认。",
                "info",
                "notifications",
                unacknowledged,
            )
        )
    if timetable.id is None:
        focus_items.append(
            _action(
                "no_timetable",
                "尚未创建课表",
                "当前学期还没有草稿或已发布课表，请先创建课表版本。",
                "info",
                "versions",
            )
        )
    focus_items = focus_items[:4]

    recommendations: list[WorkspaceActionItemOut] = []
    for warning in check.warnings:
        recommendations.append(
            _action(
                f"setup_warning:{warning.code}",
                _SETUP_WARNING_TITLES.get(warning.code, "完善学期设置"),
                warning.message,
                "warning",
                _SETUP_WARNING_TARGETS.get(warning.code, "wizard"),
            )
        )
    for issue in preflight_issues:
        if issue.level != "warning":
            continue
        recommendations.append(
            _action(
                f"preflight_warning:{issue.code}",
                "检查排课提醒",
                issue.message,
                "warning",
                "auto_schedule",
            )
        )
    recommendations = recommendations[:4]

    return WorkspaceOverviewOut(
        semester_id=semester_id,
        semester_label=semester.label,
        generated_at=clock.school_now(),
        metrics=WorkspaceMetricsOut(
            active_teacher_count=active_teacher_count,
            class_count=class_count,
            weekly_affected_periods=weekly_affected,
            week_start=week_start,
            week_end=week_end,
        ),
        timetable=timetable,
        preflight=preflight_summary,
        today_pending_periods=today_pending,
        unacknowledged_notifications=unacknowledged,
        focus_items=focus_items,
        recommendations=recommendations,
    )
