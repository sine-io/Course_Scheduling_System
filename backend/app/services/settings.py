"""全局系统设置的读写(M4-3)。"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting

# 学校名称。显示在界面、导出的课表和调课与代课通知中。
SCHOOL_NAME = "school_name"

# 超课时上限：教师每周教学任务最多可超过应授课时的数量；0 表示不限制。
MAX_OVERTIME = "max_overtime_periods"
DEFAULT_MAX_OVERTIME = 8

# SMTP 设置的 key
SMTP_HOST = "smtp_host"
SMTP_PORT = "smtp_port"
SMTP_USER = "smtp_user"
SMTP_PASSWORD = "smtp_password"
SMTP_FROM = "smtp_from"
SMTP_TLS = "smtp_tls"


@dataclass(frozen=True, slots=True)
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str
    use_tls: bool

    @property
    def configured(self) -> bool:
        """只要有主机与发件人即视为已设置;账号和密码可空(内网转发常见)。"""
        return bool(self.host and self.sender)


def get(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppSetting, key)
    return row.value if row else default


def set_value(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value


def all_settings(db: Session) -> dict[str, str]:
    return {row.key: row.value for row in db.scalars(select(AppSetting))}


def school_name(db: Session) -> str:
    """优先读取系统设置，未设置时沿用安装时 .env 的学校名称。"""
    from app.core.config import settings as env_settings

    return get(db, SCHOOL_NAME).strip() or env_settings.school_name


def save_school_name(db: Session, value: str) -> None:
    set_value(db, SCHOOL_NAME, value.strip())


def max_overtime(db: Session) -> int:
    """读取超课时上限；配置损坏时回退到默认值，避免阻塞教学任务维护。"""
    raw = get(db, MAX_OVERTIME)
    if not raw:
        return DEFAULT_MAX_OVERTIME
    try:
        return max(int(raw), 0)
    except ValueError:
        return DEFAULT_MAX_OVERTIME


def save_max_overtime(db: Session, value: int) -> None:
    set_value(db, MAX_OVERTIME, str(max(value, 0)))


def smtp_config(db: Session) -> SmtpConfig:
    values = all_settings(db)
    return SmtpConfig(
        host=values.get(SMTP_HOST, ""),
        port=int(values.get(SMTP_PORT) or 25),
        user=values.get(SMTP_USER, ""),
        password=values.get(SMTP_PASSWORD, ""),
        sender=values.get(SMTP_FROM, ""),
        use_tls=values.get(SMTP_TLS, "") == "1",
    )


def save_smtp(
    db: Session, *, host: str, port: int, user: str, password: str, sender: str, use_tls: bool
) -> None:
    set_value(db, SMTP_HOST, host.strip())
    set_value(db, SMTP_PORT, str(port))
    set_value(db, SMTP_USER, user.strip())
    # 空密码视为「不变更」,避免每次存设置都要重打密码
    if password:
        set_value(db, SMTP_PASSWORD, password)
    set_value(db, SMTP_FROM, sender.strip())
    set_value(db, SMTP_TLS, "1" if use_tls else "0")
