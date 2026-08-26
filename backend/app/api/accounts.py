"""系统管理员账号与固定角色管理。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api import high_risk_http
from app.core.auth import get_active_user, require_roles
from app.core.db import get_db
from app.core.security import hash_password
from app.models.user import Role, User, UserRole
from app.schemas.account import AccountCreateRequest, AccountOut, AccountUpdateRequest
from app.services import high_risk
from app.services.users import create_user

router = APIRouter(tags=["accounts"])

admin_only = require_roles(Role.admin)


def _role_values(roles: list[Role]) -> list[str]:
    return sorted(role.value for role in roles)


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
) -> list[AccountOut]:
    users = db.scalars(select(User).order_by(User.username, User.id)).all()
    return [AccountOut.from_model(user) for user in users]


@router.post("/accounts", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(
    body: AccountCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_active_user),
) -> AccountOut:
    roles = _role_values(body.roles)
    attempt = high_risk_http.begin(
        db,
        actor,
        body.confirmation,
        action="create_account",
        target_type="account",
        target_id=None,
        semester_id=None,
        target_version=body.username,
        expected_target=f"account:{body.username}",
        impact=f"创建账号 {body.username} 并授予角色：{'、'.join(roles)}",
    )
    if db.scalar(select(User.id).where(User.username == body.username)) is not None:
        high_risk_http.reject_code(
            db,
            attempt.id,
            code="account_username_exists",
            message="此账号已存在，请使用其他账号名",
        )
    if Role.admin.value in roles:
        high_risk_http.reject_code(
            db,
            attempt.id,
            code="system_admin_role_reserved",
            message="系统管理员是唯一的内置账号，不能通过新增账号授予",
        )
    try:
        account = create_user(
            db,
            username=body.username,
            password=body.temporary_password,
            roles=body.roles,
            display_name=body.display_name,
            must_change_password=True,
        )
        high_risk.update_target(
            db,
            attempt.id,
            target_version=body.username,
        )
        high_risk.finish(
            db,
            attempt.id,
            result="success",
            detail=f"已创建账号 {body.username}；角色：{'、'.join(roles)}",
        )
    except IntegrityError:
        high_risk_http.reject_code(
            db,
            attempt.id,
            code="account_username_exists",
            message="此账号已存在，请使用其他账号名",
        )
    db.refresh(account)
    return AccountOut.from_model(account)


@router.patch("/accounts/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int,
    body: AccountUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_active_user),
) -> AccountOut:
    attempt = high_risk_http.begin(
        db,
        actor,
        body.confirmation,
        action="update_account",
        target_type="account",
        target_id=account_id,
        semester_id=None,
        target_version=f"#{account_id}",
        expected_target=f"account:{account_id}",
        impact=f"修改账号 #{account_id} 的角色、状态或登录凭据",
    )
    account = db.get(User, account_id)
    if account is None:
        high_risk_http.reject_code(
            db,
            attempt.id,
            code="account_not_found",
            message="找不到账号",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    high_risk.update_target(db, attempt.id, target_version=account.username)

    if account.is_builtin:
        high_risk_http.reject_code(
            db,
            attempt.id,
            code="builtin_account_protected",
            message="内置系统管理员不能通过账号权限页面编辑",
        )

    requested_roles = (
        set(_role_values(body.roles)) if body.roles is not None else account.role_names
    )
    if Role.admin.value in requested_roles:
        high_risk_http.reject_code(
            db,
            attempt.id,
            code="system_admin_role_reserved",
            message="系统管理员是唯一的内置账号，不能授予普通账号",
        )

    before_roles = sorted(account.role_names)
    if body.display_name is not None:
        account.display_name = body.display_name
    if body.roles is not None:
        account.roles = [role for role in account.roles if role.role in requested_roles]
        retained = {role.role for role in account.roles}
        account.roles.extend(
            UserRole(role=role) for role in sorted(requested_roles - retained)
        )
    if body.is_active is not None:
        account.is_active = body.is_active
    if body.temporary_password is not None:
        if account.auth_provider != "local":
            high_risk_http.reject_code(
                db,
                attempt.id,
                code="external_account_password",
                message="外部认证账号不能在本系统重设密码",
            )
        account.password_hash = hash_password(body.temporary_password)
        account.must_change_password = True
    after_roles = sorted(requested_roles)
    detail = (
        f"已更新账号 {account.username}；角色 {before_roles} -> {after_roles}；"
        f"状态：{'启用' if account.is_active else '停用'}"
        + ("；已重设临时密码" if body.temporary_password is not None else "")
    )
    high_risk.finish(db, attempt.id, result="success", detail=detail)
    db.refresh(account)
    return AccountOut.from_model(account)
