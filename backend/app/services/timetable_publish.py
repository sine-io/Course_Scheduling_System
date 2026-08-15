"""课表版本服务:完整性检查、复制草稿、发布(architecture.md D4)。

发布 = draft → published;同学期原有的 published 自动转 archived(仅一份 published)。
发布为快照:已发布/已归档的课表不可再编辑单元格(见 api/timetables._require_draft)。
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.models.assignment import (
    AssignmentTeacher,
    BlockRule,
    CourseAssignment,
    SchedulingUnit,
    SchedulingUnitMember,
)
from app.models.audit import AuditLog
from app.models.leave import AffectedPeriod, AffectedStatus, LeaveRequest, LeaveStatus
from app.models.semester import Semester
from app.models.timetable import ScheduleEntry, Timetable, TimetableStatus
from app.models.user import User
from app.services import semester_context

PUBLICATION_CHECK_TTL = timedelta(minutes=15)


def _reasons_by_assignment(timetable: Timetable) -> dict[int, str]:
    """把该课表存下的 solver 未排原因摊成 {教学任务 id: 原因}(M6-3)。

    「哪些教学任务还缺节数」统一由下方 completeness 从 DB 重算——那是唯一真相,连手动改过
    的课表都算得对。这里只补上 DB 推导不出来的那一半:**为什么排不下**。
    """
    out: dict[int, str] = {}
    for item in timetable.unscheduled or []:
        reason = item.get("reason") or ""
        if not reason:
            continue
        for aid in item.get("assignment_ids", []):
            out[aid] = reason
    return out


def completeness(db: Session, timetable: Timetable) -> dict:
    """比对每项教学任务的每周节数与已排入节数,返回未排完列表(H8 周节数守恒的发布面检查)。"""
    reasons = _reasons_by_assignment(timetable)
    placed_rows = db.execute(
        select(ScheduleEntry.course_assignment_id, func.sum(ScheduleEntry.span))
        .where(ScheduleEntry.timetable_id == timetable.id)
        .group_by(ScheduleEntry.course_assignment_id)
    ).all()
    placed_by = {aid: int(n or 0) for aid, n in placed_rows}

    assignments = db.scalars(
        select(CourseAssignment)
        .where(CourseAssignment.semester_id == timetable.semester_id)
        .order_by(CourseAssignment.id)
    ).all()

    unplaced = []
    required = 0
    placed_total = 0
    for a in assignments:
        required += a.periods_per_week
        placed = placed_by.get(a.id, 0)
        placed_total += placed
        if placed < a.periods_per_week:
            unplaced.append({
                "course_assignment_id": a.id,
                "subject": a.subject.name,
                "classes": [m.class_unit.name for m in a.scheduling_unit.members],
                "teachers": [at.teacher.name for at in a.teachers],
                "required": a.periods_per_week,
                "placed": placed,
                "remaining": a.periods_per_week - placed,
                "reason": reasons.get(a.id, ""),
            })
    return {
        "required": required,
        "placed": placed_total,
        "remaining": max(required - placed_total, 0),
        "complete": not unplaced,
        "unplaced": unplaced,
    }


def publication_fingerprint(db: Session, timetable: Timetable) -> str:
    """Return a stable digest for everything that can change a publication decision."""
    context, _ = semester_context.read_context(db)
    semester = db.get(Semester, timetable.semester_id)
    if semester is None:
        semester_data: list[object] = []
    else:
        semester_data = [
            semester.id,
            semester.status,
            semester.readiness,
            semester.start_date,
            semester.end_date,
        ]
    assignments = db.execute(
        select(
            CourseAssignment.id,
            CourseAssignment.scheduling_unit_id,
            CourseAssignment.subject_id,
            CourseAssignment.periods_per_week,
            CourseAssignment.required_room_type,
            CourseAssignment.room_id,
            CourseAssignment.lock_room,
        )
        .where(CourseAssignment.semester_id == timetable.semester_id)
        .order_by(CourseAssignment.id)
    ).all()
    assignment_teachers = db.execute(
        select(
            AssignmentTeacher.course_assignment_id,
            AssignmentTeacher.teacher_id,
            AssignmentTeacher.is_lead,
        )
        .join(CourseAssignment)
        .where(CourseAssignment.semester_id == timetable.semester_id)
        .order_by(AssignmentTeacher.course_assignment_id, AssignmentTeacher.teacher_id)
    ).all()
    block_rules = db.execute(
        select(
            BlockRule.course_assignment_id,
            BlockRule.block_size,
            BlockRule.count_per_week,
        )
        .join(CourseAssignment)
        .where(CourseAssignment.semester_id == timetable.semester_id)
        .order_by(
            BlockRule.course_assignment_id,
            BlockRule.block_size,
            BlockRule.count_per_week,
        )
    ).all()
    unit_members = db.execute(
        select(
            SchedulingUnitMember.scheduling_unit_id,
            SchedulingUnitMember.class_unit_id,
        )
        .join(SchedulingUnit)
        .where(SchedulingUnit.semester_id == timetable.semester_id)
        .order_by(
            SchedulingUnitMember.scheduling_unit_id,
            SchedulingUnitMember.class_unit_id,
        )
    ).all()
    entries = db.execute(
        select(
            ScheduleEntry.id,
            ScheduleEntry.course_assignment_id,
            ScheduleEntry.weekday,
            ScheduleEntry.period_no,
            ScheduleEntry.span,
            ScheduleEntry.room_id,
            ScheduleEntry.locked,
        )
        .where(ScheduleEntry.timetable_id == timetable.id)
        .order_by(ScheduleEntry.id)
    ).all()
    payload = {
        "context": [context.current_semester_id, context.revision],
        "semester": semester_data,
        "timetable": [
            timetable.id,
            timetable.semester_id,
            timetable.name,
            timetable.status,
            timetable.unscheduled,
        ],
        "assignments": [list(row) for row in assignments],
        "assignment_teachers": [list(row) for row in assignment_teachers],
        "block_rules": [list(row) for row in block_rules],
        "unit_members": [list(row) for row in unit_members],
        "entries": [list(row) for row in entries],
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def record_publication_check(
    db: Session, timetable: Timetable, *, passed: bool
) -> tuple[str, datetime]:
    fingerprint = publication_fingerprint(db, timetable)
    checked_at = datetime.now(UTC)
    timetable.publication_check_fingerprint = fingerprint
    timetable.publication_check_passed = passed
    timetable.publication_checked_at = checked_at
    db.flush()
    return fingerprint, checked_at


def _publication_check_expired(checked_at: datetime) -> bool:
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=UTC)
    else:
        checked_at = checked_at.astimezone(UTC)
    return datetime.now(UTC) - checked_at > PUBLICATION_CHECK_TTL


def publication_confirmation_error(
    db: Session, timetable: Timetable, fingerprint: str
) -> tuple[str, str] | None:
    if not fingerprint:
        return (
            "publication_confirmation_required",
            "请先运行发布检查并确认目标学期、版本和检查结果",
        )
    if (
        timetable.publication_check_fingerprint != fingerprint
        or timetable.publication_checked_at is None
    ):
        return "publication_check_stale", "发布检查已过期，请重新检查草稿后确认"
    if _publication_check_expired(timetable.publication_checked_at):
        return "publication_check_expired", "发布检查已超过 15 分钟，请重新检查后确认"
    if publication_fingerprint(db, timetable) != fingerprint:
        return "publication_check_stale", "草稿或当前学期已变化，请重新检查后确认"
    return None


def publication_state(db: Session, timetable: Timetable) -> str:
    if timetable.status != TimetableStatus.draft.value:
        return timetable.status
    if not (
        timetable.publication_check_passed
        and timetable.publication_check_fingerprint
        and timetable.publication_checked_at
    ):
        return TimetableStatus.draft.value
    if _publication_check_expired(timetable.publication_checked_at):
        return TimetableStatus.draft.value
    if publication_fingerprint(db, timetable) != timetable.publication_check_fingerprint:
        return TimetableStatus.draft.value
    return "checked"


def stale_future_affected_count(db: Session, semester_id: int) -> int:
    """今日之后仍待处理/已指派的受影响节次数。

    这些节次的快照是依**先前**已发布课表展开的;学期中重新发布课表后,它们可能指向
    已移走的单元格(代课老师被派去上一节新课表里不存在的课)。返回数量供发布后提醒排课管理员
    重新查看。完整解(重跑 expand + diff + 通知)见 tasks.md M5-0 条件 D。
    """
    return db.scalar(
        select(func.count())
        .select_from(AffectedPeriod)
        .join(LeaveRequest, AffectedPeriod.leave_request_id == LeaveRequest.id)
        .where(
            AffectedPeriod.semester_id == semester_id,
            LeaveRequest.status == LeaveStatus.registered.value,
            AffectedPeriod.status.in_(
                [AffectedStatus.pending.value, AffectedStatus.resolved.value]
            ),
            AffectedPeriod.date >= clock.school_today(),
        )
    ) or 0


def duplicate(db: Session, source: Timetable, name: str) -> Timetable:
    """复制为新草稿(含全部单元格与锁定状态);两份草稿完全独立。"""
    new = Timetable(semester_id=source.semester_id, name=name,
                    status=TimetableStatus.draft.value)
    db.add(new)
    db.flush()
    entries = db.scalars(
        select(ScheduleEntry).where(ScheduleEntry.timetable_id == source.id)
    ).all()
    for e in entries:
        db.add(ScheduleEntry(
            timetable_id=new.id, course_assignment_id=e.course_assignment_id,
            weekday=e.weekday, period_no=e.period_no, span=e.span, locked=e.locked,
            room_id=e.room_id,
        ))
    db.flush()
    return new


def record_publication_attempt(
    db: Session,
    user: User,
    timetable: Timetable | None,
    *,
    target_id: int,
    result: str,
    reason: str,
    detail: str,
) -> AuditLog:
    audit = AuditLog(
        user_id=user.id,
        username=user.username,
        actor_roles=sorted(user.role_names),
        action="publish_timetable",
        target_type="timetable",
        target_id=target_id,
        semester_id=timetable.semester_id if timetable else None,
        target_version=(
            f"{timetable.name} (#{timetable.id})" if timetable else f"#{target_id}"
        ),
        result=result,
        reason=reason,
        detail=detail[:500],
    )
    db.add(audit)
    db.flush()
    return audit


def publish(db: Session, timetable: Timetable, user: User, forced: bool) -> Timetable:
    """draft → published;同学期原 published 转 archived。调用方负责 commit。"""
    previous = db.scalars(
        select(Timetable).where(
            Timetable.semester_id == timetable.semester_id,
            Timetable.status == TimetableStatus.published.value,
            Timetable.id != timetable.id,
        )
    ).all()
    for p in previous:
        p.status = TimetableStatus.archived.value
    timetable.status = TimetableStatus.published.value

    record_publication_attempt(
        db,
        user,
        timetable,
        target_id=timetable.id,
        result="success",
        reason="",
        detail=(
            f"发布课表「{timetable.name}」"
            + (f",同时归档「{'、'.join(p.name for p in previous)}」" if previous else "")
            + ("(含未排完教学任务,强制发布)" if forced else "")
        ),
    )
    db.flush()
    return timetable
