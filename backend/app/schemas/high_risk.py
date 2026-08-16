"""高风险命令的显式确认。"""

from uuid import UUID

from pydantic import BaseModel, Field


class HighRiskConfirmation(BaseModel):
    operation_id: UUID
    confirmed: bool
    target: str = Field(min_length=1, max_length=160)
