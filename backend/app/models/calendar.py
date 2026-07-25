"""学期特殊日期。"""

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.semester import Semester
    from app.models.user import User


class CalendarExceptionKind(enum.StrEnum):
    no_instruction = "no_instruction"
    makeup_instruction = "makeup_instruction"


class SemesterCalendarException(Base):
    __tablename__ = "semester_calendar_exceptions"
    __table_args__ = (
        UniqueConstraint("semester_id", "date", name="uq_calendar_exception_semester_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    # 补课日必须指定使用哪个周一至周六的周课表。
    makeup_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="", server_default="")
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_name: Mapped[str] = mapped_column(String(64), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    semester: Mapped["Semester"] = relationship()
    created_by: Mapped["User | None"] = relationship()
