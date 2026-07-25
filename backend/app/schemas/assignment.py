"""教学任务(scheduling_unit / course_assignment)schema。"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.basedata import RoomType
from app.schemas.basedata import SubjectBrief


# ── 排课单位(走班群组)──────────────────
class ClassBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    grade: int


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    class_ids: list[int] = Field(min_length=2)  # 群组至少含 2 班


class SchedulingUnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    semester_id: int
    unit_type: str
    name: str
    classes: list[ClassBrief] = []


# ── 教学任务教师 / 连堂 ───────────────────
class AssignmentTeacherIn(BaseModel):
    teacher_id: int
    is_lead: bool = True


class AssignmentTeacherOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    teacher_id: int
    is_lead: bool
    name: str


class BlockRuleIn(BaseModel):
    block_size: int = Field(ge=2, le=4)
    count_per_week: int = Field(ge=1)


class BlockRuleOut(BlockRuleIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ── 教学任务 ──────────────────────────────
class AssignmentIn(BaseModel):
    # 单班教学任务给 class_id;走班群组教学任务给 scheduling_unit_id(择一)
    class_id: int | None = None
    scheduling_unit_id: int | None = None
    subject_id: int
    periods_per_week: int = Field(ge=1, le=40)
    teachers: list[AssignmentTeacherIn] = Field(min_length=1)
    block_rules: list[BlockRuleIn] = []
    required_room_type: RoomType | None = None
    room_id: int | None = None
    lock_room: bool = False

    @model_validator(mode="after")
    def _check(self) -> "AssignmentIn":
        if (self.class_id is None) == (self.scheduling_unit_id is None):
            raise ValueError("请择一提供 class_id(单班)或 scheduling_unit_id(走班群组)")
        # 连堂总节数不可超过每周节数
        block_total = sum(b.block_size * b.count_per_week for b in self.block_rules)
        if block_total > self.periods_per_week:
            raise ValueError("连堂总节数超过每周节数")
        # 教师至多一位主讲
        if sum(1 for t in self.teachers if t.is_lead) > 1:
            raise ValueError("至多一位主讲教师")
        # 教师不可重复
        ids = [t.teacher_id for t in self.teachers]
        if len(ids) != len(set(ids)):
            raise ValueError("教师列表重复")
        return self


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    semester_id: int
    scheduling_unit: SchedulingUnitOut
    subject: SubjectBrief
    periods_per_week: int
    required_room_type: str | None
    room_id: int | None
    lock_room: bool
    teachers: list[AssignmentTeacherOut] = []
    block_rules: list[BlockRuleOut] = []


# ── 课时/负载统计 ─────────────────────
class TeacherLoad(BaseModel):
    teacher_id: int
    name: str
    base_periods: int
    admin_reduction: int
    target: int          # 应授节数 = base_periods - admin_reduction(不小于 0)
    assigned: int        # 已教学任务节数
    delta: int           # assigned - target(正=超课时,负=不足)


class ClassLoad(BaseModel):
    class_id: int
    name: str
    grade: int
    assigned: int        # 该班每周教学任务总节数
    capacity: int        # 可排节次数(regular slots)
    over_capacity: bool  # assigned > capacity
