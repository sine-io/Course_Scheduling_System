"""创建 E2E 验收所需的前置状态(仅供开发机与 CI 使用,正式站不要执行)。

- 排课管理员账号 e2e_scheduler / e2etest1234(见 frontend/e2e/helpers.ts)
- 教师账号 e2e_teacher / e2eteacher1234(供测试绑定「陈老师」)
- 系统管理员账号 e2e_admin / e2eadmin1234(系统管理页的备份/SMTP 卡片只有 admin 看得到)
- **首次登录账号** e2e_newuser / e2enewuser1234(`must_change_password=True`)
- 将设置向导标记为已完成(否则路由守卫会把排课管理员导回 /wizard,
  wizard.spec 会自行 reset 再走完整流程,不受影响)

幂等:已存在的账号不重建、不改密码。**唯一例外是 e2e_newuser**——见下方说明。
用法(容器内):
    sudo docker compose exec -T api python -m app.scripts.seed_e2e
"""

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import Role, User
from app.models.wizard import SINGLETON_ID, WizardState
from app.services.users import create_user

_ACCOUNTS: list[tuple[str, str, Role, str]] = [
    ("e2e_scheduler", "e2etest1234", Role.scheduler, "E2E 排课管理员"),
    ("e2e_teacher", "e2eteacher1234", Role.teacher, "E2E 教师"),
    ("e2e_admin", "e2eadmin1234", Role.admin, "E2E 系统管理员"),
]

NEW_USER = ("e2e_newuser", "e2enewuser1234", Role.scheduler, "E2E 首次登录用户")


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


def seed() -> None:
    with SessionLocal() as db:
        for username, password, role, display in _ACCOUNTS:
            if db.scalar(select(User).where(User.username == username)):
                print(f"账号已存在,跳过:{username}")
                continue
            create_user(
                db, username, password, [role],
                display_name=display, must_change_password=False,
            )
            print(f"已创建账号:{username}({role.value})")

        _reset_first_login_account(db)

        state = db.get(WizardState, SINGLETON_ID)
        if state is None:
            state = WizardState(id=SINGLETON_ID, current_step=0, completed=True)
            db.add(state)
        else:
            state.completed = True
        db.commit()
        print("设置向导已标记完成")


if __name__ == "__main__":
    seed()
