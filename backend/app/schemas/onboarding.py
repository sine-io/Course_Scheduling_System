"""首次成功引导与 P0 待办读模型。"""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.semester import SemesterListItem

StageStatus = Literal["complete", "blocked", "pending"]


class OnboardingAction(BaseModel):
    stage: str
    label: str
    href: str
    blocking_reason: str = ""


class P0Stage(BaseModel):
    key: str
    label: str
    complete: bool
    status: StageStatus
    blocking_reason: str = ""
    next_action: OnboardingAction | None = None
    details: dict[str, object] = Field(default_factory=dict)


class OnboardingStatusOut(BaseModel):
    """由当前业务数据实时推导的首次成功状态。"""

    first_success: bool
    wizard_completed: bool
    current_semester: SemesterListItem | None = None
    stages: list[P0Stage] = Field(default_factory=list)
    p0_todos: list[P0Stage] = Field(default_factory=list)
    next_action: OnboardingAction | None = None
