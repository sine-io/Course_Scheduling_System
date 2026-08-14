"""首次成功状态与 P0 待办的权威业务读模型。

向导完成字段只是用户进度提示；首次成功必须由当前正式学期及其真实数据推导，
因此本模块不写入任何重复的完成标记，也不读取向导字段来决定业务状态。
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assignment import CourseAssignment
from app.models.basedata import ClassUnit, Room, Subject, Teacher
from app.models.period import Period, PeriodTable, PeriodType
from app.models.semester import Semester, SemesterStatus
from app.models.timetable import Timetable, TimetableStatus
from app.models.wizard import SINGLETON_ID, WizardState
from app.schemas.onboarding import OnboardingAction, OnboardingStatusOut, P0Stage
from app.schemas.semester import SemesterListItem
from app.services import semester_context
from app.services.calendar import readiness_issues
from app.services.solver_data import load_problem
from app.services.timetable_publish import completeness
from app.solver import preflight


def _action(stage: str, label: str, href: str) -> OnboardingAction:
    return OnboardingAction(stage=stage, label=label, href=href)


def _count(db: Session, model: Any, semester_id: int | None) -> int:
    if semester_id is None:
        return 0
    return int(
        db.scalar(
            select(func.count()).select_from(model).where(model.semester_id == semester_id)
        )
        or 0
    )


def _stage(
    key: str,
    label: str,
    complete: bool,
    reason: str,
    action: OnboardingAction,
    details: dict[str, Any] | None = None,
) -> P0Stage:
    return P0Stage(
        key=key,
        label=label,
        complete=complete,
        status="complete" if complete else "blocked",
        blocking_reason="" if complete else reason,
        next_action=None if complete else action.model_copy(update={"blocking_reason": reason}),
        details=details or {},
    )


def _current_semester_out(semester: Semester | None) -> SemesterListItem | None:
    if semester is None:
        return None
    return SemesterListItem.model_validate(semester).model_copy(update={"is_current": True})


def _first_reason(issues: list[dict[str, str]], default: str) -> str:
    return issues[0]["message"] if issues else default


def _load_preflight(db: Session, semester_id: int) -> tuple[bool, str, dict[str, object]]:
    """读取排课前置检查，统一把坏数据转换成可展示的阻塞原因。"""
    try:
        report = preflight.run(load_problem(db, semester_id))
    except Exception:  # noqa: BLE001 - 读模型不能让一个坏引用打挂仪表盘
        return False, "完整性检查暂不可用，请打开自动排课页面查看数据问题。", {}
    details: dict[str, object] = {
        "preflight_ok": report.ok,
        "error_count": len(report.errors),
        "warning_count": len(report.warnings),
    }
    if report.ok:
        return True, "", details
    return False, report.errors[0].message, details


def build_status(db: Session) -> OnboardingStatusOut:
    """实时计算当前正式学期的首次成功状态和有序 P0 阶段。"""
    _, semester = semester_context.read_context(db)
    wizard = db.get(WizardState, SINGLETON_ID)
    wizard_completed = bool(wizard and wizard.completed)
    sid = semester.id if semester is not None else None

    date_issues = readiness_issues(db, semester) if semester is not None else []
    formal = bool(
        semester
        and not semester.is_demo
        and semester.status != SemesterStatus.archived.value
    )
    semester_complete = bool(
        formal
        and semester is not None
        and semester.start_date is not None
        and semester.end_date is not None
        and semester.end_date >= semester.start_date
    )
    if semester is None:
        semester_reason = "尚未创建正式当前学期。"
    elif semester.is_demo:
        semester_reason = "当前是示例学期，示例数据不会计入正式首次成功；请创建正式学期。"
    elif semester.status == SemesterStatus.archived.value:
        semester_reason = "当前学期已归档，请切换到可写的正式学期。"
    else:
        semester_reason = _first_reason(date_issues, "请先设置学期起止日期。")

    regular_periods = 0
    period_table_count = 0
    if sid is not None:
        period_table_count = _count(db, PeriodTable, sid)
        regular_periods = int(
            db.scalar(
                select(func.count())
                .select_from(Period)
                .join(PeriodTable, Period.period_table_id == PeriodTable.id)
                .where(
                    PeriodTable.semester_id == sid,
                    Period.type == PeriodType.regular.value,
                )
            )
            or 0
        )
    periods_complete = bool(formal and period_table_count and regular_periods)
    periods_reason = (
        "请先创建至少一套包含可排课节次的作息时间表。"
        if not period_table_count or not regular_periods
        else "请先创建正式当前学期。"
        if not formal
        else ""
    )

    readiness_complete = bool(
        formal
        and semester is not None
        and semester.readiness == "ready"
        and not date_issues
    )
    calendar_reason = (
        "示例学期的校历准备不能替代正式学期。"
        if semester is not None and semester.is_demo
        else _first_reason(date_issues, "请在校历与排课准备中确认当前学期。")
        if not readiness_complete
        else ""
    )

    counts = {
        "subjects": _count(db, Subject, sid),
        "teachers": _count(db, Teacher, sid),
        "classes": _count(db, ClassUnit, sid),
        "rooms": _count(db, Room, sid),
    }
    missing = [name for name in ("subjects", "teachers", "classes") if not counts[name]]
    basedata_complete = bool(formal and not missing)
    basedata_reason = (
        "请补充基础数据："
        + "、".join(
            {"subjects": "科目", "teachers": "教师", "classes": "班级"}[x]
            for x in missing
        )
        if missing
        else "请先创建正式当前学期。"
        if not formal
        else ""
    )

    assignment_count = _count(db, CourseAssignment, sid)
    assignments_complete = bool(formal and assignment_count)
    assignments_reason = (
        "请至少创建一条教学任务。"
        if not assignment_count
        else "请先创建正式当前学期。"
        if not formal
        else ""
    )

    preflight_ok = False
    preflight_reason = "请先完成学期、作息、基础数据和教学任务。"
    preflight_details: dict[str, Any] = {}
    if (
        sid is not None
        and formal
        and periods_complete
        and basedata_complete
        and assignments_complete
    ):
        preflight_ok, preflight_reason, preflight_details = _load_preflight(db, sid)

    timetables = (
        list(
            db.scalars(
                select(Timetable)
                .where(Timetable.semester_id == sid)
                .order_by(Timetable.id)
            )
        )
        if sid is not None
        else []
    )
    reports = {tt.id: completeness(db, tt) for tt in timetables}
    complete_timetable = next(
        (tt for tt in timetables if reports[tt.id]["complete"]),
        None,
    )
    draft_complete = bool(formal and timetables)
    integrity_complete = bool(
        formal and preflight_ok and complete_timetable is not None
    )
    if (
        not preflight_ok
        and formal
        and periods_complete
        and basedata_complete
        and assignments_complete
    ):
        integrity_reason = preflight_reason
    elif complete_timetable is None:
        incomplete = next(
            (reports[tt.id] for tt in timetables if not reports[tt.id]["complete"]),
            None,
        )
        integrity_reason = (
            f"当前草稿尚有 {incomplete['remaining']} 节教学任务未排完。"
            if incomplete
            else "请先创建课表草稿并运行完整性检查。"
        )
    else:
        integrity_reason = "请先完成学期准备和排课前置检查。"
    integrity_details = {
        **preflight_details,
        "timetable_id": complete_timetable.id if complete_timetable else None,
        "complete_timetable": complete_timetable is not None,
    }
    if complete_timetable is not None:
        integrity_details.update({
            "required": reports[complete_timetable.id]["required"],
            "placed": reports[complete_timetable.id]["placed"],
            "remaining": reports[complete_timetable.id]["remaining"],
        })

    published = next(
        (tt for tt in timetables if tt.status == TimetableStatus.published.value),
        None,
    )
    published_report = reports[published.id] if published else None
    published_complete = bool(
        formal and preflight_ok and published_report is not None and published_report["complete"]
    )
    published_reason = (
        f"已发布课表尚有 {published_report['remaining']} 节教学任务未排完。"
        if published_report is not None and not published_report["complete"]
        else "请先发布一张通过完整性检查的正式课表。"
    )

    stages = [
        _stage(
            "semester", "学期", semester_complete, semester_reason,
            _action("semester", "创建正式学期", "/wizard"), {
            "semester_id": sid,
            "is_demo": bool(semester and semester.is_demo),
        }),
        _stage(
            "periods", "作息", periods_complete, periods_reason,
            _action("periods", "管理学期与作息时间表", "/settings/semesters"), {
            "period_table_count": period_table_count,
            "regular_period_count": regular_periods,
        }),
        _stage(
            "calendar", "校历", readiness_complete, calendar_reason,
            _action("calendar", "检查校历与排课准备", "/settings/calendar"), {
            "readiness": semester.readiness if semester else "draft",
            "issue_count": len(date_issues),
        }),
        _stage(
            "basedata", "基础数据", basedata_complete, basedata_reason,
            _action("basedata", "维护基础数据", "/basedata"), counts,
        ),
        _stage(
            "assignments", "教学任务", assignments_complete, assignments_reason,
            _action("assignments", "维护教学任务", "/scheduling/assignments"), {
            "assignment_count": assignment_count,
        }),
        _stage(
            "integrity", "完整性检查", integrity_complete, integrity_reason,
            _action("integrity", "运行完整性检查", "/scheduling/versions"), integrity_details,
        ),
        _stage(
            "draft", "课表草稿", draft_complete,
            "请先创建一份课表草稿。" if not draft_complete else "",
            _action("draft", "创建课表草稿", "/scheduling/versions"), {
            "timetable_count": len(timetables),
        }),
        _stage(
            "published", "课表发布", published_complete, published_reason,
            _action("published", "检查并发布课表", "/scheduling/versions"), {
            "published_timetable_id": published.id if published else None,
        }),
    ]
    todos = [stage for stage in stages if not stage.complete]
    first_action = todos[0].next_action if todos else None
    first_success = bool(formal and todos == [])
    return OnboardingStatusOut(
        first_success=first_success,
        wizard_completed=wizard_completed,
        current_semester=_current_semester_out(semester),
        stages=stages,
        p0_todos=todos,
        next_action=first_action,
    )
