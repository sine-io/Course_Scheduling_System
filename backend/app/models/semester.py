"""学期 model。

同校可并存多学期(准备中/进行中/已归档),所有数据以 semester_id 为范围(见 D3/D5)。
"""

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint, func
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
        UniqueConstraint("academic_year", "term", name="uq_semesters_academic_year"),
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
