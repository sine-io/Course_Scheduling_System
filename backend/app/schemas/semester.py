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


class PeriodSetupPatternIn(BaseModel):
    """向导中一行节次的定义；同一行可覆盖一个或多个工作日。"""

    model_config = ConfigDict(extra="forbid")

    period_no: int = Field(ge=1)
    weekdays: list[int] = Field(min_length=1, max_length=6)
    name: str = Field(min_length=1, max_length=32)
    start_time: time | None = None
    end_time: time | None = None
    type: PeriodType = PeriodType.regular

    @model_validator(mode="after")
    def _validate_weekdays_and_times(self) -> "PeriodSetupPatternIn":
        if len(set(self.weekdays)) != len(self.weekdays) or any(
            weekday < 1 or weekday > 6 for weekday in self.weekdays
        ):
            raise ValueError("工作日必须是 1~6 且不可重复")
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("开始时间和结束时间需要成对填写")
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("结束时间必须晚于开始时间")
        return self


class PeriodSetupGroupIn(BaseModel):
    """作息分组及其班级分配。"""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=64)
    table_id: int | None = Field(default=None, gt=0)
    name: str = Field(min_length=1, max_length=64)
    num_weekdays: int = Field(default=5, ge=5, le=6)
    is_default: bool = False
    class_ids: list[int] = []
    periods: list[PeriodSetupPatternIn] = []

    @model_validator(mode="after")
    def _validate_cells(self) -> "PeriodSetupGroupIn":
        cells: set[tuple[int, int]] = set()
        for pattern in self.periods:
            if any(weekday > self.num_weekdays for weekday in pattern.weekdays):
                raise ValueError("节次工作日不可超过本分组的工作日数量")
            for weekday in pattern.weekdays:
                cell = (weekday, pattern.period_no)
                if cell in cells:
                    raise ValueError("同一工作日和节次不可重复配置")
                cells.add(cell)
        if len(set(self.class_ids)) != len(self.class_ids):
            raise ValueError("同一班级不可在同一分组中重复")
        return self


class PeriodSetupApply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = Field(min_length=1, max_length=128)
    groups: list[PeriodSetupGroupIn] = Field(min_length=1, max_length=32)


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
