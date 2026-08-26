"""通过部署命令恢复唯一内置系统管理员的登录凭据。

密码只从交互式终端读取,不会出现在命令行参数、日志或审计详情中。恢复会改变
密码哈希,因此已有 session 会自动失效;下一次登录仍必须修改密码。
"""

from getpass import getpass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.user import User

_RECOVERY_ACTOR = "deployment-recovery"
_RECOVERY_ACTION = "recover_builtin_admin"
_MAX_PASSWORD_LENGTH = 128


def recover_builtin_admin(db: Session, new_password: str) -> User:
    """重置内置管理员密码并写入一次成功审计记录。"""
    if len(new_password) < settings.min_password_length:
        raise ValueError(f"新密码至少需 {settings.min_password_length} 个字符")
    if len(new_password) > _MAX_PASSWORD_LENGTH:
        raise ValueError(f"新密码不能超过 {_MAX_PASSWORD_LENGTH} 个字符")

    admin = db.scalar(select(User).where(User.is_builtin.is_(True)))
    if admin is None:
        raise RuntimeError("找不到内置系统管理员,请先完成系统初始化")

    admin.password_hash = hash_password(new_password)
    admin.failed_login_attempts = 0
    admin.locked_until = None
    admin.is_active = True
    admin.must_change_password = True
    db.add(
        AuditLog(
            user_id=None,
            username=_RECOVERY_ACTOR,
            actor_roles=[],
            action=_RECOVERY_ACTION,
            target_type="account",
            target_id=admin.id,
            target_version=admin.username,
            result="success",
            reason="",
            detail="已重置内置管理员凭据、解除登录锁定并撤销已有会话;下次登录需修改密码",
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(admin)
    return admin


def main() -> None:
    print("恢复内置系统管理员。密码不会显示,也不会写入命令历史或审计详情。")
    try:
        new_password = getpass("输入新密码: ")
        confirmation = getpass("再次输入新密码: ")
    except (EOFError, KeyboardInterrupt) as exc:
        raise SystemExit("操作已取消") from exc
    if new_password != confirmation:
        raise SystemExit("两次输入的密码不一致")

    with SessionLocal() as db:
        try:
            admin = recover_builtin_admin(db, new_password)
        except (RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
    print(f"已恢复内置管理员 {admin.username};旧会话已失效,下次登录需修改密码。")


if __name__ == "__main__":
    main()
