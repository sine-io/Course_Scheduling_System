"""按账号保存的导航偏好。"""

from typing import Annotated

from pydantic import BaseModel, Field, field_validator

NavigationKey = Annotated[str, Field(min_length=1, max_length=64)]


class NavigationPreference(BaseModel):
    fixed: list[NavigationKey] = Field(default_factory=list, max_length=5)
    recent: list[NavigationKey] = Field(default_factory=list, max_length=20)

    @field_validator("fixed", "recent")
    @classmethod
    def remove_duplicates(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))
