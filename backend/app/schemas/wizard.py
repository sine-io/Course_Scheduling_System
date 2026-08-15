"""设置向导 schema。"""

from typing import Literal

from pydantic import BaseModel

WizardRoute = Literal["demo", "formal"]


class WizardStateOut(BaseModel):
    current_step: int
    completed: bool
    semester_id: int | None
    total_steps: int
    has_semesters: bool  # 系统是否已有任何学期(辅助前端判断是否需引导)
    route: WizardRoute | None


class WizardStateUpdate(BaseModel):
    current_step: int | None = None
    completed: bool | None = None
    semester_id: int | None = None
    route: WizardRoute | None = None


class OnboardingRouteRequest(BaseModel):
    route: WizardRoute


class OnboardingRouteOut(BaseModel):
    """首次路线的持久化状态和安全重选能力。"""

    route: WizardRoute | None
    demo_available: bool
    demo_school_name: str
    has_demo_semester: bool
    has_formal_semester: bool
    can_reselect: bool
    resume_step: int
    resume_semester_id: int | None


class SemesterSummary(BaseModel):
    subjects: int
    teachers: int
    classes: int
    rooms: int
