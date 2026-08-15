"""课表(timetable / schedule_entry)与冲突检查 schema。"""

from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field


class TimetableCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class ScheduleEntryOut(BaseModel):
    id: int
    course_assignment_id: int
    weekday: int
    period_no: int
    span: int
    locked: bool
    subject: str
    teachers: list[str] = []
    classes: list[str] = []
    unit_type: str
    unit_name: str
    room: str | None = None
    # id 供前端三视角精确筛选(姓名/班名可能重复,不可当键)
    teacher_ids: list[int] = []
    class_ids: list[int] = []
    room_id: int | None = None


class TimetableBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    semester_id: int
    name: str
    status: str
    publication_state: str = "draft"
    entry_count: int = 0


class TimetableOut(BaseModel):
    id: int
    semester_id: int
    name: str
    status: str
    entries: list[ScheduleEntryOut] = []
    # 发布后回填:今日之后、依旧课表展开的受影响节次数(>0 提醒排课管理员重新查看调课与代课)
    stale_affected: int = 0


class ConflictOut(BaseModel):
    code: str
    message: str


class CheckRequest(BaseModel):
    course_assignment_id: int
    weekday: int = Field(ge=1, le=7)
    period_no: int = Field(ge=1)
    span: int = Field(default=1, ge=1, le=8)
    ignore_entry_id: int | None = None  # 移动现有单元格时,忽略自身
    room_id: int | None = None  # 本单元格使用的教室/场地(空=沿用教学任务教室/场地)


class CheckResponse(BaseModel):
    ok: bool
    conflicts: list[ConflictOut] = []


class PlaceRequest(BaseModel):
    course_assignment_id: int
    weekday: int = Field(ge=1, le=7)
    period_no: int = Field(ge=1)
    span: int = Field(default=1, ge=1, le=8)
    room_id: int | None = None  # 本单元格使用的教室/场地(空=沿用教学任务教室/场地)


class MoveRequest(BaseModel):
    weekday: int = Field(ge=1, le=7)
    period_no: int = Field(ge=1)


# ── 版本管理与发布 ────────────────────
class TimetableRename(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class UnplacedItem(BaseModel):
    course_assignment_id: int
    subject: str
    classes: list[str] = []
    teachers: list[str] = []
    required: int
    placed: int
    remaining: int
    # 自动排课当时 solver 说的「为什么排不下」(手动未排完则为空,M6-3)
    reason: str = ""


class CompletenessOut(BaseModel):
    required: int
    placed: int
    remaining: int
    complete: bool
    unplaced: list[UnplacedItem] = []


class PublicationTargetOut(BaseModel):
    id: int
    name: str


class PublicationSemesterOut(BaseModel):
    id: int
    label: str


class PublicationCheckOut(BaseModel):
    semester: PublicationSemesterOut
    version: PublicationTargetOut
    passed: bool
    requires_force: bool
    completeness: CompletenessOut
    issues: list[dict[str, str]] = []
    fingerprint: str
    checked_at: datetime


class PublicationConfirmation(BaseModel):
    fingerprint: str = Field(default="", max_length=64)
    force: bool = False


# ── 全员只读课表查询 ──────────────────
class PublicSemester(BaseModel):
    id: int
    label: str


class NamedBrief(BaseModel):
    id: int
    name: str


class PublicClass(BaseModel):
    id: int
    name: str
    grade: int
    period_table_id: int | None = None


class PublicPeriod(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    weekday: int
    period_no: int
    name: str
    start_time: time | None = None
    end_time: time | None = None
    type: str


class PublicPeriodTable(BaseModel):
    id: int
    name: str
    num_weekdays: int
    is_default: bool
    periods: list[PublicPeriod] = []


class PublishedTimetableOut(BaseModel):
    """已发布课表 + 查询页所需的全部选项,一次返回(教师端只打这一支)。"""

    id: int
    semester_id: int
    semester_label: str
    name: str
    status: str
    entries: list[ScheduleEntryOut] = []
    classes: list[PublicClass] = []
    teachers: list[NamedBrief] = []
    rooms: list[NamedBrief] = []
    period_tables: list[PublicPeriodTable] = []
