"""学期与作息时间表相关 schema。"""

from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.period import PeriodType
from app.models.semester import SemesterReadiness, SemesterStatus


# ── 节次 ──────────────────────────────
class PeriodIn(BaseModel):
    weekday: int = Field(ge=1, le=6)
    period_no: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=32)
    start_time: time | None = None
    end_time: time | None = None
    type: PeriodType = PeriodType.regular


class PeriodOut(PeriodIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AvailableSlot(BaseModel):
    """可排课时段(type=regular 的单元格)。"""

    weekday: int
    period_no: int
    name: str
    start_time: time | None = None
    end_time: time | None = None


# ── 作息时间表 ────────────────────────────
class PeriodTableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    semester_id: int
    name: str
    num_weekdays: int
    is_default: bool
    periods: list[PeriodOut] = []


class PeriodTableCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    num_weekdays: int = Field(default=5, ge=5, le=6)
    is_default: bool = False


class PeriodTableUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    is_default: bool | None = None


# ── 学期 ──────────────────────────────
class SemesterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    academic_year: int = Field(ge=1900, le=2100)
    term: int = Field(ge=1, le=2)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def _dates_in_order(self) -> "SemesterCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("学期结束日不可早于开始日")
        return self


class SemesterUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    status: SemesterStatus | None = None
    readiness: SemesterReadiness | None = None


class SemesterCopyRequest(BaseModel):
    academic_year: int = Field(ge=1900, le=2100)
    term: int = Field(ge=1, le=2)
    # 新学期的起止日:不能沿用来源学期(那是上学期的日期)。少了它,请假展开、今日看板、
    # 代课的「已上过」判定全部失准,而且页面上看不出哪里不对(M6-4)。
    start_date: date | None = None
    end_date: date | None = None
    period_tables: bool = True
    subjects: bool = True
    teachers: bool = True
    rooms: bool = True
    classes: bool = True
    grade_promotion: bool = True
    constraint_config: bool = True  # 软约束权重(不带则新学期悄悄回到默认值)

    @model_validator(mode="after")
    def _dates_in_order(self) -> "SemesterCopyRequest":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("学期结束日不可早于开始日")
        return self


class SemesterListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    academic_year: int
    term: int
    label: str
    status: SemesterStatus
    readiness: SemesterReadiness
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False


class SemesterOut(SemesterListItem):
    period_tables: list[PeriodTableOut] = []


class SemesterContextOut(BaseModel):
    """全局工作上下文，供所有登录角色读取。"""

    current_semester: SemesterListItem | None = None
    revision: int
    can_switch: bool


class SemesterContextSwitch(BaseModel):
    semester_id: int = Field(gt=0)
    expected_revision: int = Field(ge=0)
