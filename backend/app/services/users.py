"""用户相关服务:创建账号、首次启动创建管理员。"""

import logging
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import Role, User, UserRole

logger = logging.getLogger("app.users")


def create_user(
    db: Session,
    username: str,
    password: str,
    roles: Iterable[Role],
    display_name: str = "",
    must_change_password: bool = True,
    is_builtin: bool | None = None,
) -> User:
    """创建账号并指派角色。调用方负责 commit。

    ``admin`` 只属于首次初始化的内置账号;业务 API 也会在高风险审计边界
    再次校验,这里作为领域服务的最后一道保护。
    """
    role_list = list(roles)
    if is_builtin is None:
        is_builtin = Role.admin in role_list
    if Role.admin in role_list and not is_builtin:
        raise ValueError("admin 角色只能授予内置系统管理员账号")
    if is_builtin and set(role_list) != {Role.admin}:
        raise ValueError("内置系统管理员必须且只能拥有 admin 角色")
    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name or username,
        must_change_password=must_change_password,
        is_builtin=is_builtin,
        roles=[UserRole(role=r.value) for r in role_list],
    )
    db.add(user)
    db.flush()
    return user


def ensure_admin() -> None:
    """系统首次启动(尚无任何用户)时,依 .env 创建管理员账号。

    以「是否已有任何用户」判断,避免重复创建;默认要求首次登录改密码。
    """
    with SessionLocal() as db:
        user_count = db.scalar(select(func.count()).select_from(User))
        if user_count and user_count > 0:
            return
        create_user(
            db,
            username=settings.admin_username,
            password=settings.admin_password,
            roles=[Role.admin],
            display_name="系统管理员",
            must_change_password=True,
            is_builtin=True,
        )
        db.commit()
        logger.info("已创建初始管理员账号:%s(首次登录需改密码)", settings.admin_username)
