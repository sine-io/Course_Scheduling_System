"""学期 model。

同校可并存多学期(准备中/进行中/已归档),所有数据以 semester_id 为范围(见 D3/D5)。
"""

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.services.school_rules import format_semester_label

if TYPE_CHECKING:
    from app.models.period import PeriodTable


class SemesterStatus(enum.StrEnum):
    preparing = "preparing"  # 准备中(构建数据、排课)
    active = "active"        # 进行中(课表已发布、日常调课与代课)
    archived = "archived"    # 已归档(历史保存)


class SemesterReadiness(enum.StrEnum):
    draft = "draft"  # 排课准备尚未确认
    ready = "ready"  # 排课准备已确认，可进入排课与发布流程


class Semester(Base):
    __tablename__ = "semesters"
    __table_args__ = (
        # 示例学期是隔离的体验上下文，可以与正式学期使用同一学年/学期。
        # 正式学期之间仍保持业务上的唯一性。
        Index(
            "uq_semesters_formal_academic_year",
            "academic_year",
            "term",
            unique=True,
            postgresql_where=text("is_demo = false"),
            sqlite_where=text("is_demo = 0"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year: Mapped[int] = mapped_column(Integer)  # 学年起始年，如 2026
    term: Mapped[int] = mapped_column(Integer)           # 学期,1 或 2
    # 业务日期，不带时区（见 architecture.md D6）
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=SemesterStatus.preparing.value)
    readiness: Mapped[str] = mapped_column(
        String(20), default=SemesterReadiness.draft.value,
        server_default=SemesterReadiness.draft.value,
    )
    # 示例数据是独立的体验路径，不能满足正式学期的首次成功条件。
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # 当前学期不是 Semester 的生命周期状态，而是单校工作上下文。
    # 通过反向关系投影，避免在每张学期记录上复制一份可竞争的上下文状态。
    current_context: Mapped["SemesterContext | None"] = relationship(
        back_populates="current_semester", uselist=False, lazy="selectin"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    period_tables: Mapped[list["PeriodTable"]] = relationship(
        back_populates="semester", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def label(self) -> str:
        return format_semester_label(self.academic_year, self.term)

    @property
    def is_current(self) -> bool:
        """该学期是否是学校唯一的当前工作上下文。"""
        return self.current_context is not None


class SemesterContext(Base):
    """单校唯一的当前学期指针。

    只允许 id=1 的一行记录。切换时锁定这行，普通学期写入持共享锁，
    使切换和写入在数据库事务边界上有明确顺序。
    """

    __tablename__ = "semester_context"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        UniqueConstraint(
            "current_semester_id", name="uq_semester_context_current_semester"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    current_semester_id: Mapped[int | None] = mapped_column(
        ForeignKey("semesters.id", ondelete="SET NULL"), nullable=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    current_semester: Mapped[Semester | None] = relationship(
        back_populates="current_context", lazy="joined"
    )
