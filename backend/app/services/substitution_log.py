"""今日调课与代课看板与调课与代课日志(M4-4)。

这一层把「特定日期的受影响节次 + 其处理方式」摊平成一列列可读的记录,供两个出口共用:

1. **今日看板**:某一天全校的变更——谁请假、哪一节、由谁接手、教室在哪。
2. **历史日志**:依教师/日期/请假类型筛选的查询。

数据真相仍在 `affected_period`(受影响节次快照)与 `substitution`(处理方式决定);这里只做
join + 摊平 + 中文标签,不新增任何真相。看板的「今日」以固定学校时区判定,
不是 UTC，避免 UTC 日期与学校本地日期不一致（architecture.md D6）。
"""

from dataclasses import dataclass
from datetime import date, time

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.models.leave import (
    AffectedPeriod,
    AffectedStatus,
    LeaveRequest,
    LeaveStatus,
)
from app.models.substitution import Substitution
from app.services import leaves, school_rules

# 字段名 date/start_time 会遮蔽同名类型,故以别名标注类型
_Date = date
_Time = time

# 历史查询的保护性上限(M6-5):一整年不筛选地查会是数千条。取最新 N 条,
# 要看更早的请缩小日期区间;完整分页 UI 留 v1.2。
MAX_ROWS = 1000


@dataclass(frozen=True, slots=True)
class LogEntry:
    """生成一条调课与代课记录，包含受影响节次及其处理方式（如已处理）。"""

    affected_period_id: int
    date: _Date
    weekday: int
    period_no: int
    period_name: str
    start_time: _Time | None
    end_time: _Time | None
    class_names: str
    subject_name: str
    room_name: str
    absent_teacher_id: int
    absent_teacher_name: str
    leave_type: str
    leave_type_label: str
    status: str
    status_label: str
    disposed: bool  # 是否已有处理方式(代课/调课/合班/自习/不处理)
    sub_type: str | None
    sub_type_label: str | None
    handler_teacher_id: int | None
    handler_name: str | None
    counts_toward_hours: bool | None
    swap_date: _Date | None
    swap_period_name: str
    swap_class_names: str
    swap_subject_name: str
    note: str


def school_today() -> date:
    """学校所在时区的今天（Asia/Shanghai）。"""
    return clock.school_today()


def _subs_map(db: Session, affected_ids: list[int]) -> dict[int, Substitution]:
    """一次查询这些受影响节次的处理方式,避免逐条查询。"""
    if not affected_ids:
        return {}
    rows = db.scalars(select(Substitution).where(Substitution.affected_period_id.in_(affected_ids)))
    return {s.affected_period_id: s for s in rows}


def _build(ap: AffectedPeriod, sub: Substitution | None) -> LogEntry:
    leave = ap.leave_request
    status = leaves.effective_status(ap.status, ap.date, ap.end_time)
    handler_id = sub.handler_teacher_id if sub else ap.handler_teacher_id
    handler_name = None
    if sub is not None and sub.handler is not None:
        handler_name = sub.handler.name
    elif ap.handler is not None:
        handler_name = ap.handler.name
    return LogEntry(
        affected_period_id=ap.id,
        date=ap.date,
        weekday=ap.weekday,
        period_no=ap.period_no,
        period_name=ap.period_name,
        start_time=ap.start_time,
        end_time=ap.end_time,
        class_names=ap.class_names,
        subject_name=ap.subject_name,
        room_name=ap.room_name,
        absent_teacher_id=leave.teacher_id,
        absent_teacher_name=leave.teacher.name if leave.teacher else "(已移除)",
        leave_type=leave.leave_type,
        leave_type_label=school_rules.leave_type_label(leave.leave_type),
        status=status,
        status_label=school_rules.affected_status_label(status),
        disposed=sub is not None,
        sub_type=sub.type if sub else None,
        sub_type_label=school_rules.substitution_type_label(sub.type) if sub else None,
        handler_teacher_id=handler_id,
        handler_name=handler_name,
        counts_toward_hours=sub.counts_toward_hours if sub else None,
        swap_date=sub.swap_date if sub else None,
        swap_period_name=sub.swap_period_name if sub else "",
        swap_class_names=sub.swap_class_names if sub else "",
        swap_subject_name=sub.swap_subject_name if sub else "",
        note=ap.note or (sub.note if sub else ""),
    )


def daily_board(db: Session, semester_id: int, on: date) -> list[LogEntry]:
    """某一天全校的调课与代课变更,依节次、班级排序。

    只看仍有效(未销假)的假单;已因销假取消的节次不列(那天没有变更)。
    包含尚未设置处理方式(待处理)的节次,便于排课管理员查看还有多少节课程待处理。
    """
    rows = (
        db.scalars(
            select(AffectedPeriod)
            .join(LeaveRequest, AffectedPeriod.leave_request_id == LeaveRequest.id)
            .where(
                AffectedPeriod.semester_id == semester_id,
                AffectedPeriod.date == on,
                LeaveRequest.status == LeaveStatus.registered.value,
                AffectedPeriod.status != AffectedStatus.cancelled.value,
            )
            .order_by(AffectedPeriod.period_no, AffectedPeriod.class_names)
        )
        .unique()
        .all()
    )
    subs = _subs_map(db, [r.id for r in rows])
    return [_build(r, subs.get(r.id)) for r in rows]


def query(
    db: Session,
    semester_id: int,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    teacher_id: int | None = None,
    leave_type: str | None = None,
    limit: int = MAX_ROWS,
) -> list[LogEntry]:
    """历史查询:依日期区间、教师、请假类型筛选,最新在前。

    `teacher_id` 同时比对「请假的当事人」与「接手代课的教师」——查一位教师时,
    他缺的课与他代的课都算与他相关。

    `limit` 是保护性上限(M6-5):不筛选地查一整年,会把数千条一次拉进内存再序列化。
    取最新的 N 条(调用方可缩小日期区间看更早的);完整分页 UI 留 v1.2。
    """
    stmt = (
        select(AffectedPeriod)
        .join(LeaveRequest, AffectedPeriod.leave_request_id == LeaveRequest.id)
        .where(AffectedPeriod.semester_id == semester_id)
    )
    if date_from is not None:
        stmt = stmt.where(AffectedPeriod.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(AffectedPeriod.date <= date_to)
    if leave_type is not None:
        stmt = stmt.where(LeaveRequest.leave_type == leave_type)
    if teacher_id is not None:
        stmt = stmt.where(
            or_(
                LeaveRequest.teacher_id == teacher_id,
                AffectedPeriod.handler_teacher_id == teacher_id,
            )
        )
    rows = (
        db.scalars(stmt.order_by(AffectedPeriod.date.desc(), AffectedPeriod.period_no).limit(limit))
        .unique()
        .all()
    )
    subs = _subs_map(db, [r.id for r in rows])
    return [_build(r, subs.get(r.id)) for r in rows]
