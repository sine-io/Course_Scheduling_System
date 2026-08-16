"""管理员账号与固定角色管理 schema。"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.user import Role, User
from app.schemas.high_risk import HighRiskConfirmation


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    roles: list[str]
    is_active: bool
    must_change_password: bool
    auth_provider: str

    @classmethod
    def from_model(cls, user: User) -> "AccountOut":
        return cls(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            roles=sorted(user.role_names),
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            auth_provider=user.auth_provider,
        )


class AccountCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=64)
    temporary_password: str = Field(min_length=8, max_length=128)
    roles: list[Role] = Field(min_length=1)
    confirmation: HighRiskConfirmation | None = None

    @model_validator(mode="after")
    def unique_roles(self) -> "AccountCreateRequest":
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("角色不可重复")
        return self


class AccountUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    roles: list[Role] | None = Field(default=None, min_length=1)
    is_active: bool | None = None
    temporary_password: str | None = Field(default=None, min_length=8, max_length=128)
    confirmation: HighRiskConfirmation | None = None

    @model_validator(mode="after")
    def validate_change(self) -> "AccountUpdateRequest":
        if self.roles is not None and len(set(self.roles)) != len(self.roles):
            raise ValueError("角色不可重复")
        if all(
            value is None
            for value in (
                self.display_name,
                self.roles,
                self.is_active,
                self.temporary_password,
            )
        ):
            raise ValueError("请至少修改一项账号设置")
        return self
