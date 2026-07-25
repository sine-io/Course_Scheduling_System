"""请假与受影响节次 model(architecture.md §5.3 状态机)。

**这里是「周循环格」与「特定日期」的交界。** M0–M3 的一切都创建在
`(weekday, period_no)` 的周循环抽象上;请假却是「王师 11/12 上午请假」这种特定日期的事实。
`affected_period` 就是把前者依日历展开成后者的产物,M4 之后的代课推荐、今日看板、
课时统计全部长在它上面。

**它是快照,不是 join。** 展开的当下把教学任务、教师、班级、教室/场地、节次名称与起止时间一并写死。
理由与 D4(已发布课表是不可变快照)一致:课表可以重新发布,但「王师 11/12 第三节
原本要上 301 班的语文」是一件已经发生的历史事实,不该随着课表改版而变化——
更不该让一项已经指派出去的代课,隔天指向另一门课。
"""

import enum
from datetime import date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.basedata import Teacher


class LeaveType(enum.StrEnum):
    official = "official"        # 公假
    personal = "personal"        # 事假
    sick = "sick"                # 病假
    marriage = "marriage"        # 婚假
    bereavement = "bereavement"  # 丧假
    maternity = "maternity"      # 产假
    training = "training"        # 培训


class LeaveStatus(enum.StrEnum):
    registered = "registered"  # 已登记(受影响节次已展开)
    cancelled = "cancelled"    # 已销假(所有处理方式级联取消)


class AffectedStatus(enum.StrEnum):
    """待处理 → 已处理 → 已完成；任一阶段均可因销假转为已取消。"""

    pending = "pending"      # 待处理
    resolved = "resolved"    # 已处理（已设置代课、调课、合班、自习或不处理）
    completed = "completed"  # 已完成(上课日结束)
    cancelled = "cancelled"  # 已取消(销假)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), index=True
    )
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), index=True
    )
    leave_type: Mapped[str] = mapped_column(String(20))
    # 领域日期/时间,无时区(architecture.md D6)。时间为空 = 该端点全天。
    start_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    reason: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default=LeaveStatus.registered.value)

    # 登记人(教师自登或排课管理员代登);账号删除后仍保留姓名快照
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_name: Mapped[str] = mapped_column(String(64), default="")
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    teacher: Mapped[Teacher] = relationship(lazy="selectin")
    affected_periods: Mapped[list["AffectedPeriod"]] = relationship(
        back_populates="leave_request", cascade="all, delete-orphan", lazy="selectin",
    )

    @property
    def is_half_day(self) -> bool:
        return self.start_time is not None or self.end_time is not None


class AffectedPeriod(Base):
    __tablename__ = "affected_periods"
    __table_args__ = (
        # 同一张假单、同一天、同一节课只会出现一次
        UniqueConstraint(
            "leave_request_id", "date", "period_no", "class_names",
            name="uq_affected_periods_slot",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    leave_request_id: Mapped[int] = mapped_column(
        ForeignKey("leave_requests.id", ondelete="CASCADE"), index=True
    )
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), index=True
    )

    date: Mapped[date] = mapped_column(Date, index=True)  # 实际上课日
    weekday: Mapped[int] = mapped_column(Integer)
    period_no: Mapped[int] = mapped_column(Integer)

    # ── 快照字段(展开当下的事实,不随课表改版而变)──
    period_name: Mapped[str] = mapped_column(String(32), default="")  # 「第三节」,不用 period_no
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    subject_name: Mapped[str] = mapped_column(String(64), default="")
    class_names: Mapped[str] = mapped_column(String(128), default="")  # 走班群组可能多班
    room_name: Mapped[str] = mapped_column(String(64), default="")

    # 溯源用;课表被删除或重新发布时设为 NULL,快照字段仍在
    schedule_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedule_entries.id", ondelete="SET NULL"), nullable=True
    )
    course_assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_assignments.id", ondelete="SET NULL"), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(20), default=AffectedStatus.pending.value)
    # 已指派的处理教师。实际处理方式以 `substitution` 记录为准。
    # (代课/调课/合班/自习/不处理、是否计课时、经费来源);这里刻意冗余一个指标,
    # 供销假级联通知、今日看板与月结统计直接查询,不必每次回头 join。
    handler_teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    leave_request: Mapped[LeaveRequest] = relationship(back_populates="affected_periods")
    handler: Mapped[Teacher | None] = relationship(lazy="selectin")
