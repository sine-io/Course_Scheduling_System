"""调课与代课处理方式与代课推荐 schema(M4-2)。"""

from datetime import date

from pydantic import BaseModel, Field


class CandidateOut(BaseModel):
    teacher_id: int
    teacher_name: str
    same_subject: bool
    at_school_that_day: bool
    sub_periods_this_month: int
    reasons: list[str] = []


class RecommendationOut(BaseModel):
    affected_period_id: int
    candidates: list[CandidateOut] = []
    no_candidate_hint: str = ""


class AssignRequest(BaseModel):
    """指派处理方式。type=substitute/swap/merge 需 handler_teacher_id;swap 另需 swap_*。"""

    type: str  # substitute / swap / merge / self_study / cancel
    handler_teacher_id: int | None = None
    counts_toward_hours: bool | None = None  # 空=依处理方式默认(代课计、其余不计)
    funding_source: str = Field(default="", max_length=32)
    # 调课:乙的某节课(schedule_entry)与甲补课的日期
    swap_entry_id: int | None = None
    swap_date: date | None = None


class SubstitutionOut(BaseModel):
    id: int
    affected_period_id: int
    type: str
    type_label: str
    handler_teacher_id: int | None = None
    handler_name: str | None = None
    counts_toward_hours: bool
    funding_source: str
    swap_date: date | None = None
    swap_period_name: str = ""
    swap_class_names: str = ""
    swap_subject_name: str = ""
    created_by_name: str
