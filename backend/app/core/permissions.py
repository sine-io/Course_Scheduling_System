"""固定角色的业务权限策略。

业务 API 只从这里获取角色边界，避免不同模块各自复制一组近似但不一致的
``require_roles`` 参数。``require_roles`` 本身仍负责 admin 超级用户和多角色并集；
这里的策略只描述业务动作，不替代后端对对象范围和当前学期的校验。
"""

from collections.abc import Callable

from app.core.auth import require_roles
from app.models.user import Role, User

CORE_VIEW_ROLES: tuple[Role, ...] = (Role.scheduler, Role.director)
CORE_EDIT_ROLES: tuple[Role, ...] = (Role.scheduler,)
BATCH_EXPORT_ROLES: tuple[Role, ...] = (Role.scheduler,)
TIMETABLE_PUBLISH_ROLE_NAMES = frozenset({Role.admin.value, Role.scheduler.value})

# 日常运行由排课管理员和教务主任共同负责。admin 由 ``require_roles`` 的
# 超级用户规则统一放行，不重复写进每一组业务角色，避免角色矩阵漂移。
DAILY_OPERATOR_ROLES: tuple[Role, ...] = (Role.scheduler, Role.director)

# 请假、通知确认和个人统计允许四种固定角色中的任一种；实际能看到的
# 数据仍由 current_teacher/对象归属校验限定到本人。
DAILY_USER_ROLES: tuple[Role, ...] = (
    Role.admin,
    Role.scheduler,
    Role.director,
    Role.teacher,
)

DAILY_OPERATOR_ROLE_NAMES = frozenset(
    {Role.admin.value, *(role.value for role in DAILY_OPERATOR_ROLES)}
)

PermissionDependency = Callable[..., User]
CoreDependency = PermissionDependency

core_viewer: CoreDependency = require_roles(*CORE_VIEW_ROLES)
core_editor: CoreDependency = require_roles(*CORE_EDIT_ROLES)
batch_exporter: CoreDependency = require_roles(*BATCH_EXPORT_ROLES)
daily_operator: PermissionDependency = require_roles(*DAILY_OPERATOR_ROLES)
daily_user: PermissionDependency = require_roles(*DAILY_USER_ROLES)


def is_daily_operator(user: User) -> bool:
    """Return whether ``user`` may operate on school-wide daily data."""
    return bool(user.role_names & DAILY_OPERATOR_ROLE_NAMES)


def can_publish_timetable(user: User) -> bool:
    """Return whether the user's fixed-role union includes direct publication."""
    return bool(user.role_names & TIMETABLE_PUBLISH_ROLE_NAMES)
