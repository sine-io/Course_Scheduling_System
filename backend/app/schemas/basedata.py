"""基础数据(教师/科目/教室/场地/班级)schema。"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validators import is_valid_email
from app.models.basedata import ClassTrack, RoomType, TeacherRuleType


def _normalize_optional_email(value: str | None) -> str | None:
    """空字符串转 None;非空则验证 Email 格式。"""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not is_valid_email(value):
        raise ValueError("Email 格式不正确")
    return value


# ── 科目 ──────────────────────────────
class SubjectBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class SubjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    domain: str | None = Field(default=None, max_length=64)
    required_room_type: RoomType | None = None
    default_block_size: int = Field(default=1, ge=1, le=8)
    is_major: bool = False  # 主科(排课引擎 S5:尽量排上午)


class SubjectOut(SubjectIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    semester_id: int


# ── 教师 ──────────────────────────────
class TeacherIn(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    id_last4: str | None = Field(default=None, max_length=4)
    base_periods: int = Field(default=0, ge=0)
    admin_title: str | None = Field(default=None, max_length=32)
    admin_reduction: int = Field(default=0, ge=0)
    is_external: bool = False
    is_active: bool = True
    subject_ids: list[int] = []
    email: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    line_id: str | None = Field(default=None, max_length=64)
    user_id: int | None = None  # 绑定的登录账号(空=不绑定)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str | None) -> str | None:
        return _normalize_optional_email(v)


class TeacherOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    semester_id: int
    name: str
    id_last4: str | None
    base_periods: int
    admin_title: str | None
    admin_reduction: int
    is_external: bool
    is_active: bool
    subjects: list[SubjectBrief] = []
    email: str | None = None
    phone: str | None = None
    line_id: str | None = None
    user_id: int | None = None


class BindableAccount(BaseModel):
    """可供教师绑定的账号(teacher 角色、于本学期尚未被绑定者)。"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    display_name: str


class TeacherTimeRuleIn(BaseModel):
    weekday: int = Field(ge=1, le=6)
    period_no: int = Field(ge=1)
    rule_type: TeacherRuleType


class TeacherTimeRuleOut(TeacherTimeRuleIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ── 教室/场地 ──────────────────────────────
class RoomIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    room_type: RoomType = RoomType.normal
    capacity: int | None = Field(default=None, ge=0)
    subject_ids: list[int] = []


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    semester_id: int
    name: str
    room_type: RoomType
    capacity: int | None
    subjects: list[SubjectBrief] = []


# ── 班级 ──────────────────────────────
class ClassUnitIn(BaseModel):
    grade: int = Field(ge=1, le=12)
    name: str = Field(min_length=1, max_length=32)
    track: ClassTrack
    department: str | None = Field(default=None, max_length=32)
    student_count: int | None = Field(default=None, ge=0)
    homeroom_teacher_id: int | None = None
    period_table_id: int | None = None  # 空=用学期默认作息时间表


class ClassUnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    semester_id: int
    grade: int
    name: str
    track: ClassTrack
    department: str | None
    student_count: int | None
    homeroom_teacher_id: int | None
    homeroom_teacher: SubjectBrief | None = None  # 借用 {id,name} 结构显示班主任
    period_table_id: int | None = None
