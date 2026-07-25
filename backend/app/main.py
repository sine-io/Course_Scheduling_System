"""FastAPI 应用程序入口。"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    app_config,
    assignments,
    audit,
    auth,
    backups,
    basedata,
    calendar,
    exports,
    health,
    imports,
    leaves,
    notifications,
    semesters,
    solver,
    substitution_log,
    substitution_stats,
    substitutions,
    timetables,
    wizard,
)
from app.api import (
    settings as settings_api,
)
from app.core.config import settings
from app.services.users import ensure_admin

logger = logging.getLogger(__name__)


# 启动时 worker-ops 可能仍在启动(compose 会并行启动容器),因此会等待一段时间再判定。
OPS_CHECK_RETRIES = 6
OPS_CHECK_INTERVAL = 2.0


async def _warn_if_no_ops_worker() -> None:
    """背景检查 ops 队列有没有 worker 在守,没有就在启动 log 讲清楚。

    升级只换镜像、没更新 docker-compose.yml 的话,worker-ops 根本不存在;此时导出/备份
    会失败(那还算吵),而每日自动备份是**静默**停摆的——没人会发现,直到需要那份备份的
    那一天。不阻塞启动，也不在冷启动的最初几秒误报。
    """
    try:
        from app.workers.queue import OPS_WORKER_MISSING, ops_worker_available

        for _ in range(OPS_CHECK_RETRIES):
            await asyncio.sleep(OPS_CHECK_INTERVAL)
            if await asyncio.to_thread(ops_worker_available):
                return
        logger.warning(OPS_WORKER_MISSING)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 - Redis 暂不可用不应影响 API 启动
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动时：若系统尚无任何用户，按 .env 创建初始管理员。
    ensure_admin()
    check = asyncio.create_task(_warn_if_no_ops_worker())
    yield
    check.cancel()


app = FastAPI(
    title=settings.app_name,
    description="开源免费的学校排课、调课与代课管理系统 API",
    version="0.1.0",
    # 正式部署默认关闭(见 settings.api_docs_enabled);None = 该路由不存在,回 404
    docs_url="/api/docs" if settings.api_docs_enabled else None,
    openapi_url="/api/openapi.json" if settings.api_docs_enabled else None,
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 所有 API 挂在 /api 前缀之下(Caddy 依此前缀分流)
app.include_router(health.router, prefix="/api")
app.include_router(app_config.router, prefix="/api")
app.include_router(calendar.router, prefix="/api")
app.include_router(auth.router, prefix="/api/auth")
app.include_router(semesters.router, prefix="/api")
app.include_router(basedata.router, prefix="/api")
app.include_router(assignments.router, prefix="/api")
app.include_router(timetables.router, prefix="/api")
app.include_router(solver.router, prefix="/api")
app.include_router(exports.router, prefix="/api")
app.include_router(leaves.router, prefix="/api")
app.include_router(substitutions.router, prefix="/api")
app.include_router(substitution_log.router, prefix="/api")
app.include_router(substitution_stats.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
app.include_router(backups.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(wizard.router, prefix="/api")
