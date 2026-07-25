"""校历、特殊日期与排课准备数据结构。"""

from __future__ import annotations

from datetime import date as _Date
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.calendar import CalendarExceptionKind
from app.models.semester import SemesterReadiness


class CalendarExceptionCreate(BaseModel):
    date: _Date
    kind: CalendarExceptionKind
    makeup_weekday: int | None = Field(default=None, ge=1, le=6)
    note: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def validate_makeup_weekday(self) -> CalendarExceptionCreate:
        if self.kind == CalendarExceptionKind.makeup_instruction and self.makeup_weekday is None:
            raise ValueError("补课日必须指定使用周一至周六中的课表")
        if self.kind == CalendarExceptionKind.no_instruction and self.makeup_weekday is not None:
            raise ValueError("停课日不能指定补课课表星期")
        return self


class CalendarExceptionUpdate(BaseModel):
    date: _Date | None = None
    kind: CalendarExceptionKind | None = None
    makeup_weekday: int | None = Field(default=None, ge=1, le=6)
    note: str | None = Field(default=None, max_length=200)


class CalendarExceptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    semester_id: int
    date: _Date
    kind: CalendarExceptionKind
    makeup_weekday: int | None
    note: str
    created_by_name: str
    created_at: datetime | None = None


class SemesterReadinessOut(BaseModel):
    semester_id: int
    readiness: SemesterReadiness
    ready: bool
    issues: list[dict[str, str]] = []
    calendar_exception_count: int = 0
