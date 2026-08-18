"""工作空间首页总览的只读响应模型。"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

OverviewTone = Literal["critical", "warning", "info"]


class WorkspaceTimetableOut(BaseModel):
    id: int | None = None
    name: str = ""
    status: str = ""
    updated_at: datetime | None = None
    required_periods: int = 0
    placed_periods: int = 0
    remaining_periods: int = 0
    completion_rate: int | None = None


class WorkspacePreflightOut(BaseModel):
    available: bool = True
    error_count: int = 0
    warning_count: int = 0
    unavailable_message: str = ""


class WorkspaceMetricsOut(BaseModel):
    active_teacher_count: int
    class_count: int
    weekly_affected_periods: int
    week_start: date
    week_end: date


class WorkspaceActionItemOut(BaseModel):
    code: str
    title: str
    description: str
    tone: OverviewTone
    target: str
    count: int | None = None


class WorkspaceOverviewOut(BaseModel):
    semester_id: int
    semester_label: str
    generated_at: datetime
    metrics: WorkspaceMetricsOut
    timetable: WorkspaceTimetableOut
    preflight: WorkspacePreflightOut
    today_pending_periods: int
    unacknowledged_notifications: int
    focus_items: list[WorkspaceActionItemOut] = Field(default_factory=list)
    recommendations: list[WorkspaceActionItemOut] = Field(default_factory=list)
