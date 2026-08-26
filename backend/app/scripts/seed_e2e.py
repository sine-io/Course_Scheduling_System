"""创建 E2E 验收所需的前置状态(仅供开发机与 CI 使用,正式站不要执行)。

- 教务主任账号 e2e_director / e2edirector1234(见 frontend/e2e/helpers.ts)
- 教师账号 e2e_teacher / e2eteacher1234(供测试绑定「陈老师」)
- 唯一内置系统管理员账号 e2e_admin / e2eadmin1234(系统管理页的备份/SMTP 卡片只有 admin 看得到)
- **首次登录账号** e2e_newuser / e2enewuser1234(`must_change_password=True`)
- 清理 Issue #33 浏览器测试创建的归档学期夹具
- 不再需要独立的首次设置状态；首次登录测试直接从普通工作页面开始。

幂等:普通账号已存在时跳过;唯一内置管理员和 **e2e_newuser** 会按下方说明重置,
以保证每次 E2E 从可预测的凭据与状态开始。
用法(容器内):
    sudo docker compose exec -T api python -m app.scripts.seed_e2e
"""

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.basedata import Subject
from app.models.semester import Semester
from app.models.user import Role, User, UserRole
from app.services.users import create_user

_ACCOUNTS: list[tuple[str, str, tuple[Role, ...], str]] = [
    ("e2e_director", "e2edirector1234", (Role.director,), "E2E 教务主任"),
    ("e2e_teacher", "e2eteacher1234", (Role.teacher,), "E2E 教师"),
]

NEW_USER = ("e2e_newuser", "e2enewuser1234", Role.director, "E2E 首次登录用户")
ISSUE_33_ARCHIVED_YEAR = 2068
ISSUE_33_ARCHIVED_SUBJECT = "归档学期保留科目"


def _cleanup_issue_33_archived_fixture(db) -> None:
    """只删除带专用标记科目的 E2E 归档夹具，避免触碰同年份真实数据。"""
    semesters = db.scalars(
        select(Semester).where(Semester.academic_year == ISSUE_33_ARCHIVED_YEAR)
    ).all()
    removed = 0
    for semester in semesters:
        marker = db.scalar(
            select(Subject.id).where(
                Subject.semester_id == semester.id,
                Subject.name == ISSUE_33_ARCHIVED_SUBJECT,
            )
        )
        if marker is not None:
            db.delete(semester)
            removed += 1
    if removed:
        print(f"已清理 Issue #33 归档学期夹具:{removed}")


def _reset_first_login_account(db) -> None:
    """每次 seed 都把首次登录测试账号恢复为强制改密状态。"""
    username, password, role, display = NEW_USER
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        create_user(
            db, username, password, [role],
            display_name=display, must_change_password=True,
        )
        print(f"已创建账号:{username}(首次登录状态)")
        return
    user.password_hash = hash_password(password)
    user.must_change_password = True
    print(f"已重置为首次登录状态:{username}")


def _reset_builtin_admin(db) -> None:
    """把现有唯一内置管理员准备成 E2E 管理员,避免创建第二个 admin。"""
    username = "e2e_admin"
    password = "e2eadmin1234"
    display = "E2E 系统管理员"
    admin = db.scalar(select(User).where(User.is_builtin.is_(True)))
    if admin is None:
        admin = db.scalar(select(User).where(User.username == username))
        if admin is None:
            admin = create_user(
                db,
                username,
                password,
                [Role.admin],
                display_name=display,
                must_change_password=False,
                is_builtin=True,
            )
        elif admin.role_names != {Role.admin.value}:
            raise RuntimeError(f"账号 {username} 已存在但不是系统管理员,无法准备 E2E 环境")
        else:
            admin.is_builtin = True

    admin.username = username
    admin.display_name = display
    admin.password_hash = hash_password(password)
    admin.is_active = True
    admin.must_change_password = False
    admin.failed_login_attempts = 0
    admin.locked_until = None
    existing_admin_role = next(
        (role for role in admin.roles if role.role == Role.admin.value),
        None,
    )
    admin.roles = [existing_admin_role or UserRole(role=Role.admin.value)]
    db.flush()
    print(f"已准备唯一内置管理员:{username}")


def seed() -> None:
    with SessionLocal() as db:
        _cleanup_issue_33_archived_fixture(db)
        _reset_builtin_admin(db)
        for username, password, roles, display in _ACCOUNTS:
            if db.scalar(select(User).where(User.username == username)):
                print(f"账号已存在,跳过:{username}")
                continue
            create_user(
                db, username, password, list(roles),
                display_name=display, must_change_password=False,
            )
            print(f"已创建账号:{username}({','.join(role.value for role in roles)})")

        _reset_first_login_account(db)

        db.commit()
        print("E2E 账号与基础环境已准备")


if __name__ == "__main__":
    seed()
