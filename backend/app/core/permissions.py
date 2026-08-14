"""固定角色的核心排课权限策略。

核心业务 API 只从这里取得角色边界，避免不同模块各自复制一组近似但不一致的
``require_roles`` 参数。``require_roles`` 本身仍负责 admin 超级用户和多角色并集。
"""

from collections.abc import Callable

from app.core.auth import require_roles
from app.models.user import Role, User

CORE_VIEW_ROLES: tuple[Role, ...] = (Role.scheduler, Role.director)
CORE_EDIT_ROLES: tuple[Role, ...] = (Role.scheduler,)
BATCH_EXPORT_ROLES: tuple[Role, ...] = (Role.scheduler,)

CoreDependency = Callable[..., User]

core_viewer: CoreDependency = require_roles(*CORE_VIEW_ROLES)
core_editor: CoreDependency = require_roles(*CORE_EDIT_ROLES)
batch_exporter: CoreDependency = require_roles(*BATCH_EXPORT_ROLES)
