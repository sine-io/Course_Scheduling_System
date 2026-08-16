"""数据库备份与恢复(M5-2)。

以 PostgreSQL 原生工具 pg_dump / pg_restore(custom 格式,可 --clean 恢复)。这些工具
只装在 worker 镜像,故实际 dump/restore 在 worker 执行;api 端负责列表、下载、上传与分派任务。

- 文件名:`backup_YYYYMMDD_HHMMSS_<reason>.dump`,存放于共挂的 volume(config.backup_dir)。
- 保留 config.backup_keep 份,超出者由旧而新轮替删除。
- 恢复前先验证文件头(custom 格式以 `PGDMP` 开头),非法文件直接拒绝、不动数据库(验收②)。
"""

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import unquote, urlsplit

from app.core.config import settings

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^backup_(\d{8}_\d{6})_([a-z]+)\.dump$")

# pg_restore 进较旧服务器时,新版 pg_dump 写入的跨版本 GUC(如 v17 的 transaction_timeout)
# 会让该条 SET 失败但数据不受影响。这类「无法识别设置参数」是唯一允许忽略的错误;
# 其余任何 `pg_restore: error` 都可能代表数据真的没恢复完整,统一视为失败。
_IGNORABLE_RESTORE = re.compile(r"unrecognized configuration parameter", re.IGNORECASE)


class BackupError(Exception):
    """备份/恢复失败(调用方转为 4xx/5xx)。"""


@dataclass(frozen=True, slots=True)
class BackupInfo:
    name: str
    size_bytes: int
    created_at: datetime
    reason: str


def _dir() -> str:
    os.makedirs(settings.backup_dir, exist_ok=True)
    return settings.backup_dir


def _db_params() -> dict[str, str]:
    u = urlsplit(settings.database_url)
    return {
        "host": u.hostname or "localhost",
        "port": str(u.port or 5432),
        "user": unquote(u.username or ""),
        "password": unquote(u.password or ""),
        "dbname": u.path.lstrip("/") or "postgres",
    }


def _env(params: dict[str, str]) -> dict[str, str]:
    e = os.environ.copy()
    e["PGPASSWORD"] = params["password"]
    return e


def _path(name: str) -> str:
    # 防止路径穿越:只接受单纯文件名
    if os.path.basename(name) != name or not name.endswith(".dump"):
        raise BackupError("非法的备份文件名")
    return os.path.join(_dir(), name)


# ── 列表 / 轮替(任何镜像可用)──────────────────────────────
def _info(name: str) -> BackupInfo | None:
    m = _NAME_RE.match(name)
    if m is None:
        return None
    full = os.path.join(_dir(), name)
    try:
        st = os.stat(full)
    except OSError:
        return None
    return BackupInfo(
        name=name, size_bytes=st.st_size,
        created_at=datetime.strptime(m.group(1), "%Y%m%d_%H%M%S"),
        reason=m.group(2),
    )


def list_backups() -> list[BackupInfo]:
    """最新在前。"""
    out = [i for f in os.listdir(_dir()) if (i := _info(f)) is not None]
    return sorted(out, key=lambda i: i.name, reverse=True)


def prune(keep: int | None = None) -> list[str]:
    """保留最新 keep 份,删除其余。返回被删文件名。"""
    keep = settings.backup_keep if keep is None else keep
    backups = list_backups()
    removed = []
    for info in backups[keep:]:
        try:
            os.remove(os.path.join(_dir(), info.name))
            removed.append(info.name)
        except OSError:
            pass
    return removed


def is_valid_dump(path: str) -> bool:
    """custom 格式的 pg_dump 档以魔数 `PGDMP` 开头。"""
    try:
        with open(path, "rb") as f:
            return f.read(5) == b"PGDMP"
    except OSError:
        return False


# ── dump / restore(需 pg_dump/pg_restore,worker 镜像)──────
def create_backup(reason: str = "manual") -> BackupInfo:
    """跑 pg_dump 生成一份备份并轮替。返回新备份信息。"""
    reason = reason if reason.isalpha() else "manual"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"backup_{ts}_{reason}.dump"
    path = os.path.join(_dir(), name)
    p = _db_params()
    try:
        subprocess.run(
            ["pg_dump", "-Fc", "-h", p["host"], "-p", p["port"],
             "-U", p["user"], "-d", p["dbname"], "-f", path],
            check=True, env=_env(p), capture_output=True, text=True,
        )
    except FileNotFoundError as e:
        raise BackupError("找不到 pg_dump(需在 worker 镜像执行)") from e
    except subprocess.CalledProcessError as e:
        raise BackupError(f"备份失败:{e.stderr or e}") from e
    prune()
    info = _info(name)
    if info is None:
        raise BackupError("备份文件生成后无法读取")
    return info


def _terminate_other_connections(p: dict[str, str]) -> None:
    """恢复前踢掉其他连接,避免 pg_restore 的 DROP 被锁住(尽力而为)。"""
    try:
        import psycopg
        with psycopg.connect(
            host=p["host"], port=int(p["port"]), user=p["user"],
            password=p["password"], dbname=p["dbname"], connect_timeout=5,
        ) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (p["dbname"],),
            )
            conn.commit()
    except Exception:  # noqa: BLE001 - 尽力而为,失败不阻止恢复
        pass


def _classify_restore_stderr(stderr: str) -> list[str]:
    """查看 pg_restore 的 stderr,返回可忽略的警告摘要。

    只有「无法识别设置参数」(跨版本 GUC 噪声)允许忽略;出现任何其他 `pg_restore: error`
    就抛出 BackupError——只凭 returncode==1 无法区分「跨版本噪声」与「某张表 COPY 失败」,
    后者若被当成成功,会把数据缺漏报成恢复成功。
    """
    warnings: list[str] = []
    for raw in stderr.splitlines():
        s = raw.strip()
        if not s:
            continue
        low = s.lower()
        if "pg_restore: error" in low or "; error while" in low:
            if _IGNORABLE_RESTORE.search(s):
                warnings.append(s)
                continue
            raise BackupError(f"恢复时出现非预期错误:{s}")
        if "warning" in low or "errors ignored on restore" in low:
            warnings.append(s)
    return warnings


def restore_backup(name: str) -> list[str]:
    """从指定备份恢复(先验证文件头)。返回可忽略的警告摘要;调用方负责事后强制重新登录。"""
    path = _path(name)
    if not os.path.exists(path):
        raise BackupError("找不到备份文件")
    if not is_valid_dump(path):
        raise BackupError("这不是有效的备份文件(格式不符),已拒绝恢复")
    p = _db_params()
    _terminate_other_connections(p)
    try:
        proc = subprocess.run(
            ["pg_restore", "--single-transaction", "--exit-on-error", "--clean", "--if-exists",
             "--no-owner", "--no-privileges",
             "-h", p["host"], "-p", p["port"], "-U", p["user"], "-d", p["dbname"], path],
            check=False, env=_env(p), capture_output=True, text=True,
        )
    except FileNotFoundError as e:
        raise BackupError("找不到 pg_restore(需在 worker 镜像执行)") from e
    # 单事务恢复下任何 SQL 错误都会回滚整次恢复；不能再把跨版本 SET 错误当作已完成。
    if proc.returncode != 0:
        raise BackupError(f"恢复失败，全部变更已回滚:{proc.stderr or proc.returncode}")
    warnings = _classify_restore_stderr(proc.stderr)
    if warnings:
        logger.warning("pg_restore 完成但有可忽略的警告:%s", " | ".join(warnings))
    return warnings


def save_uploaded(name_hint: str, data: bytes) -> str:
    """把上传的备份文件写入备份目录,先验证格式;返回实际文件名。非法则拒绝不落地。"""
    if data[:5] != b"PGDMP":
        raise BackupError("这不是有效的备份文件(格式不符)")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"backup_{ts}_upload.dump"
    with open(os.path.join(_dir(), name), "wb") as f:
        f.write(data)
    return name


def discard(name: str) -> None:
    """删除未能完成恢复的上传文件；只接受备份目录中的合法文件名。"""
    try:
        os.remove(_path(name))
    except OSError:
        pass
