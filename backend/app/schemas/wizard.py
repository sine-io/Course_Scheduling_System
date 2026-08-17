"""设置向导 schema。"""

from pydantic import BaseModel, ConfigDict, Field


class WizardStateOut(BaseModel):
    current_step: int
    resume_step: int
    completed: bool
    paused: bool
    semester_id: int | None
    total_steps: int
    has_semesters: bool  # 系统是否已有任何学期(辅助前端判断是否需引导)


class WizardStateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_step: int | None = None
    completed: bool | None = None
    paused: bool | None = None
    semester_id: int | None = None


class SemesterSummary(BaseModel):
    subjects: int
    teachers: int
    classes: int
    rooms: int


class SetupCheckItem(BaseModel):
    code: str
    message: str
    step: int = Field(ge=0, le=2)


class SetupCheckOut(BaseModel):
    semester_id: int
    can_complete: bool
    first_incomplete_step: int = Field(ge=0, le=3)
    blockers: list[SetupCheckItem]
    warnings: list[SetupCheckItem]
    summary: SemesterSummary


class WizardCompleteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semester_id: int = Field(gt=0)
    acknowledge_warnings: bool = False
