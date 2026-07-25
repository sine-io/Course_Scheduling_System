"""应用程序设置。所有可部署设置均由环境变量提供。"""

import logging
import secrets
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# 已知不安全的 SECRET_KEY 值（程序默认值和 .env.example 示例）。
_INSECURE_SECRETS = {
    "dev-insecure-change-me",
    "please-change-this-to-a-random-secret",
    "",
}


def _is_real_domain(site_address: str) -> bool:
    """判断 SITE_ADDRESS 是否为真实域名，而不是内网 HTTP 的默认值。"""
    s = site_address.strip()
    return bool(s) and s != ":80" and not s.startswith(":")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 基本
    app_name: str = "学校排课、调课与代课管理系统"
    school_name: str = "示范学校"
    debug: bool = False
    # 调度器心跳间隔（秒）；每日备份等周期任务共用此调度器。
    scheduler_heartbeat_seconds: int = 3600
    # 备份目录、保留份数和每日自动备份时间；API 与 worker 挂载同一数据卷。
    backup_dir: str = "/backups"
    backup_keep: int = 30
    backup_hour: int = 2  # 每日自动备份的小时(学校时区)

    # 数据库与队列
    database_url: str = "postgresql+psycopg://scheduler:scheduler@postgres:5432/scheduler"
    redis_url: str = "redis://redis:6379/0"

    # 首次启动创建的管理员
    admin_username: str = "admin"
    admin_password: str = "changeme"

    # 认证与 session
    # 用于签署 session cookie;正式部署务必于 .env 设置随机值
    secret_key: str = "dev-insecure-change-me"
    session_max_age_seconds: int = 60 * 60 * 8  # 登录有效时间,默认 8 小时
    # 站点地址(与 Caddy 共用同一 .env 变量):设为域名即代表走 HTTPS
    site_address: str = ""
    # cookie Secure 标记。默认 False(内网 HTTP);SITE_ADDRESS 为域名时自动 True(见 _harden)
    cookie_secure: bool = False
    # 登录失败锁定
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    # 新密码最短长度
    min_password_length: int = 8
    # 导入教师并创建账号时的默认密码(首次登录强制更改)
    default_import_password: str = "changeme"

    # CORS(开发模式前端 dev server 来源)
    cors_origins: list[str] = ["http://localhost", "http://localhost:5173"]

    # 交互式 API 文档（/api/docs 与 openapi.json）默认关闭。接口本身受权限保护，
    # 但正式部署通常没有必要公开完整的内部接口目录；开发环境会显式打开。
    api_docs_enabled: bool = False

    @model_validator(mode="after")
    def _harden(self) -> "Settings":
        # SECRET_KEY 仍为默认或示例值时改用随机密钥，避免使用公开值签署会话。
        if self.secret_key in _INSECURE_SECRETS:
            self.secret_key = secrets.token_hex(32)
            logger.warning(
                "未设置 SECRET_KEY，已改用随机密钥（重启会使所有登录失效）；"
                "请在 .env 中设置固定的 SECRET_KEY（例如 openssl rand -hex 32 的输出）。"
            )
        # 配置 HTTPS 域名且未显式指定 COOKIE_SECURE 时，自动启用 Secure 标记。
        if "cookie_secure" not in self.model_fields_set and _is_real_domain(self.site_address):
            self.cookie_secure = True
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
