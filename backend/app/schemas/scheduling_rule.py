"""排课规则目录、草稿编辑、校验与激活 schema。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

RuleStrength = Literal["hard", "soft", "informational"]
RulePriority = Literal["high", "medium", "low"]


class RuleTarget(BaseModel):
    entity_type: str = Field(min_length=1, max_length=32)
    ids: list[int] = Field(default_factory=list)

    @field_validator("ids")
    @classmethod
    def unique_ids(cls, value: list[int]) -> list[int]:
        if any(item < 1 for item in value):
            raise ValueError("规则对象 ID 必须为正整数")
        return list(dict.fromkeys(value))


class RuleTiming(BaseModel):
    weekdays: list[int] = Field(default_factory=list)
    period_nos: list[int] = Field(default_factory=list)
    period_table_ids: list[int] = Field(default_factory=list)
    week_pattern: str | None = None

    @field_validator("weekdays")
    @classmethod
    def valid_weekdays(cls, value: list[int]) -> list[int]:
        if any(day < 1 or day > 7 for day in value):
            raise ValueError("星期必须在 1 至 7 之间")
        return list(dict.fromkeys(value))

    @field_validator("period_nos", "period_table_ids")
    @classmethod
    def positive_numbers(cls, value: list[int]) -> list[int]:
        if any(item < 1 for item in value):
            raise ValueError("节次和作息表 ID 必须为正整数")
        return list(dict.fromkeys(value))


class SchedulingRuleUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    template: str = Field(min_length=1, max_length=40)
    target: RuleTarget
    timing: RuleTiming
    operator: str = Field(min_length=1, max_length=24)
    strength: RuleStrength
    priority: RulePriority = "medium"
    source_text: str = Field(default="", max_length=500)
    enabled: bool = True


class RuleTemplateOut(BaseModel):
    key: str
    label: str
    description: str
    supported: bool
    target_types: list[str]
    operators: list[str]
    strengths: list[RuleStrength]
    operator_strengths: dict[str, list[RuleStrength]]
    unavailable_reason: str | None = None


class RuleRevisionOut(BaseModel):
    id: int
    revision_no: int
    status: str
    note: str
    created_by_name: str
    created_at: datetime
    activated_at: datetime | None


class SchedulingRuleOut(BaseModel):
    id: int
    rule_key: str
    revision_id: int
    name: str
    template: str
    template_label: str
    target: RuleTarget
    timing: RuleTiming
    operator: str
    strength: RuleStrength
    priority: RulePriority
    source_kind: str
    source_text: str
    enabled: bool
    status: str
    compiler_version: str
    compiler_status: str
    summary: str


class BuiltinRuleOut(BaseModel):
    rule_key: str
    name: str
    summary: str
    strength: Literal["hard", "soft"]
    source_kind: Literal["builtin"] = "builtin"
    status: Literal["active"] = "active"


class SchedulingRuleWorkspaceOut(BaseModel):
    semester_id: int
    active_revision: RuleRevisionOut | None
    draft_revision: RuleRevisionOut | None
    rules: list[SchedulingRuleOut]
    builtin_rules: list[BuiltinRuleOut]
    options: dict


class RuleDiagnosticOut(BaseModel):
    level: Literal["error", "warning"]
    code: str
    message: str
    rule_key: str


class RuleValidationOut(BaseModel):
    revision_id: int | None
    valid: bool
    diagnostics: list[RuleDiagnosticOut]
    matched_assignment_count: int
    excluded_candidate_count: int


class ActivateRulesRequest(BaseModel):
    note: str = Field(default="", max_length=240)
