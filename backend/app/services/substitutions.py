"""调课与代课处理方式(M4-2,architecture.md §5.3)。

指派即生效：创建或更新处理方式后，受影响节次转为“已处理”并记录处理教师，随后发送通知。
没有邀请/婉拒;通知只是正式告知 +「确认收到」。

各处理方式的课时:代课计、合班/自习/不处理不计(§5.4 月结)。
调课(swap)要验两位教师交换后都无冲突,拒绝时说出是谁在哪一节撞课。
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.models.assignment import AssignmentTeacher, CourseAssignment
from app.models.basedata import Subject, Teacher
from app.models.leave import AffectedPeriod, AffectedStatus, LeaveStatus
from app.models.notification import NotificationType
from app.models.substitution import (
    TYPES_WITH_HANDLER,
    Substitution,
    SubstitutionType,
)
from app.models.timetable import ScheduleEntry
from app.services import calendar as calendar_service
from app.services import notifications, school_rules
from app.services.availability import Availability, Interval


class SubstitutionError(Exception):
    """处理方式不合法(调用方转为 400/409)。"""


def _wd(weekday: int) -> str:
    return school_rules.weekday_name(weekday)


def _counts_default(sub_type: str) -> bool:
    return sub_type == SubstitutionType.substitute.value


def assign(
    db: Session,
    affected: AffectedPeriod,
    *,
    sub_type: str,
    handler_teacher_id: int | None,
    counts_toward_hours: bool | None,
    funding_source: str,
    swap_entry_id: int | None,
    swap_date: date | None,
    created_by_user_id: int | None,
    created_by_name: str,
    availability: Availability | None = None,
) -> Substitution:
    """对一个受影响节次做处理方式。调用方负责 commit。"""
    if affected.status == AffectedStatus.cancelled.value:
        raise SubstitutionError("此节次已因销假取消,无法再设置处理方式")
    if affected.status == AffectedStatus.completed.value or clock.is_past_slot(
        affected.date, affected.end_time
    ):
        raise SubstitutionError("此节次已结束,无法变更处理方式")
    if sub_type not in set(SubstitutionType):
        raise SubstitutionError(f"未知的处理方式：{sub_type}")

    av = availability or Availability(db, affected.semester_id)
    handler = _resolve_handler(db, affected, sub_type, handler_teacher_id, av)

    swap_fields: dict = {}
    if sub_type == SubstitutionType.swap.value:
        swap_fields = _validate_swap(db, affected, handler, swap_entry_id, swap_date, av)

    counts = _counts_default(sub_type) if counts_toward_hours is None else counts_toward_hours

    sub = db.scalar(select(Substitution).where(Substitution.affected_period_id == affected.id))
    if sub is None:
        sub = Substitution(semester_id=affected.semester_id, affected_period_id=affected.id)
        db.add(sub)
    sub.type = sub_type
    sub.handler_teacher_id = handler.id if handler else None
    sub.counts_toward_hours = counts
    sub.funding_source = funding_source
    sub.created_by_user_id = created_by_user_id
    sub.created_by_name = created_by_name
    for k, v in swap_fields.items():
        setattr(sub, k, v)
    if sub_type != SubstitutionType.swap.value:
        _clear_swap(sub)

    affected.status = AffectedStatus.resolved.value
    affected.handler_teacher_id = handler.id if handler else None
    db.flush()

    if handler is not None:
        _notify_handler(db, affected, sub, handler)
    return sub


def _resolve_handler(
    db: Session,
    affected: AffectedPeriod,
    sub_type: str,
    handler_teacher_id: int | None,
    av: Availability,
) -> Teacher | None:
    if sub_type not in TYPES_WITH_HANDLER:
        return None  # 自习/不处理没有处理教师
    if handler_teacher_id is None:
        label = school_rules.substitution_type_label(sub_type)
        raise SubstitutionError(f"“{label}”需要指定教师")

    teacher = db.scalar(
        select(Teacher).where(
            Teacher.id == handler_teacher_id, Teacher.semester_id == affected.semester_id
        )
    )
    if teacher is None:
        raise SubstitutionError("找不到指定的教师")
    if teacher.id == affected.leave_request.teacher_id:
        raise SubstitutionError("不能指派请假教师代自己的课")

    # 代课/合班:接手者在该时段必须是空的(调课的冲突另由 _validate_swap 检查)
    if sub_type != SubstitutionType.swap.value:
        conflict = av.conflict_for(teacher.id, affected.date, av.slot_of(affected))
        if conflict is not None:
            raise SubstitutionError(
                f"{teacher.name} {affected.date} {affected.period_name} {conflict.detail},无法指派"
            )
    return teacher


def _validate_swap(
    db: Session,
    affected: AffectedPeriod,
    handler: Teacher | None,
    swap_entry_id: int | None,
    swap_date: date | None,
    av: Availability,
) -> dict:
    """调课:乙(handler)代甲请假那节;甲(请假教师)于 swap_date 补乙原本的 swap_entry。

    验四件事,任一撞课即拒绝并指名道姓:
      ① 乙 在甲请假那节无自己的课    ② swap_entry 确实是乙的课
      ③ 甲 在 swap_date 那节无课、也没请假   ④ swap_date 是乙该节课真的会上的日子
    """
    if handler is None:
        raise SubstitutionError("调课需要指定对调教师")
    if swap_entry_id is None or swap_date is None:
        raise SubstitutionError("调课需要指定对调的节次与补课日期")

    entry = db.get(ScheduleEntry, swap_entry_id)
    if entry is None:
        raise SubstitutionError("找不到要对调的节次")
    teaches = db.scalar(
        select(AssignmentTeacher).where(
            AssignmentTeacher.course_assignment_id == entry.course_assignment_id,
            AssignmentTeacher.teacher_id == handler.id,
        )
    )
    if teaches is None:
        raise SubstitutionError(f"要对调的节次不是 {handler.name} 的课")
    effective_swap_weekday = calendar_service.effective_weekday(db, affected.semester_id, swap_date)
    if effective_swap_weekday != entry.weekday:
        actual_weekday = effective_swap_weekday or swap_date.isoweekday()
        raise SubstitutionError(
            f"{swap_date} 使用 {_wd(actual_weekday)}课表，"
            f"但调课课程在 {_wd(entry.weekday)}，补课日期与该节课星期不符"
        )

    # ① 乙 在甲请假那节不能有自己的课(代课要来上)
    clash = av.teaching_at(handler.id, av.slot_of(affected))
    if clash is not None:
        raise SubstitutionError(
            f"{handler.name} {affected.date} {affected.period_name} 有自己的课,无法对调"
        )

    swap_assignment = db.get(CourseAssignment, entry.course_assignment_id)
    if swap_assignment is None:
        raise SubstitutionError("要对调的节次已无对应教学任务")

    # ③ 甲 在 swap_date 的 swap 节次不能有课、也不能请假
    absent = affected.leave_request.teacher
    swap_slot = Interval(entry.weekday, entry.period_no, None, None)
    conflict = av.conflict_for(absent.id, swap_date, swap_slot)
    if conflict is not None:
        subj = db.get(Subject, swap_assignment.subject_id)
        pname = _entry_period_name(db, entry)
        raise SubstitutionError(
            f"{absent.name} 无法在 {swap_date} {pname} 补课:{conflict.detail}"
            + (f"(对调的是{subj.name})" if subj else "")
        )

    subject = db.get(Subject, swap_assignment.subject_id)
    classes = "、".join(m.class_unit.name for m in swap_assignment.scheduling_unit.members)
    return {
        "swap_date": swap_date,
        "swap_period_no": entry.period_no,
        "swap_period_name": _entry_period_name(db, entry),
        "swap_class_names": classes,
        "swap_subject_name": subject.name if subject else "",
        "swap_entry_id": entry.id,
    }


def _entry_period_name(db: Session, entry: ScheduleEntry) -> str:
    from app.models.period import Period

    a = db.get(CourseAssignment, entry.course_assignment_id)
    if a and a.scheduling_unit.members:
        from app.services import period_tables as pt_service

        table = pt_service.resolve_period_table(db, a.scheduling_unit.members[0].class_unit)
        if table:
            p = db.scalar(
                select(Period).where(
                    Period.period_table_id == table.id,
                    Period.weekday == entry.weekday,
                    Period.period_no == entry.period_no,
                )
            )
            if p:
                return p.name
    return f"第 {entry.period_no} 格"


def _clear_swap(sub: Substitution) -> None:
    sub.swap_date = None
    sub.swap_period_no = None
    sub.swap_period_name = ""
    sub.swap_class_names = ""
    sub.swap_subject_name = ""
    sub.swap_entry_id = None


def _notify_handler(
    db: Session, affected: AffectedPeriod, sub: Substitution, handler: Teacher
) -> None:
    absent = affected.leave_request.teacher
    type_cn = school_rules.substitution_type_label(sub.type)
    where = f"{affected.date} {affected.period_name}({affected.class_names}{affected.subject_name})"
    if sub.type == SubstitutionType.swap.value:
        body = (
            f"请于 {where} 代 {absent.name} 一节；"
            f"{absent.name} 将于 {sub.swap_date} {sub.swap_period_name} 补您的"
            f"{sub.swap_class_names}{sub.swap_subject_name}"
        )
    else:
        body = f"请于 {where} {type_cn} {absent.name} 的课"
    notifications.notify(
        db,
        semester_id=affected.semester_id,
        teacher_id=handler.id,
        type=NotificationType.substitution_assigned,
        title=f"{type_cn}通知：{affected.date} {affected.period_name}",
        body=body,
    )


def clear(db: Session, affected: AffectedPeriod, *, actor_name: str) -> None:
    """撤回处理方式:受影响节次退回『待处理』,已指派的教师收到取消通知。调用方负责 commit。"""
    if affected.leave_request.status == LeaveStatus.cancelled.value:
        raise SubstitutionError("此假单已销假")
    if clock.is_past_slot(affected.date, affected.end_time):
        raise SubstitutionError("此节次已结束,无法撤回处理方式")
    sub = db.scalar(select(Substitution).where(Substitution.affected_period_id == affected.id))
    if sub is None:
        return
    if sub.handler_teacher_id is not None:
        notifications.notify(
            db,
            semester_id=affected.semester_id,
            teacher_id=sub.handler_teacher_id,
            type=NotificationType.substitution_cancelled,
            title=f"原定{school_rules.substitution_type_label(sub.type)}已取消",
            body=f"{actor_name} 取消了 {affected.date} {affected.period_name} 的处理",
        )
    db.delete(sub)
    affected.status = AffectedStatus.pending.value
    affected.handler_teacher_id = None
    db.flush()
