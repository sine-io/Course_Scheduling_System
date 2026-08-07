#!/usr/bin/env bash
# 后端容器进入点。第一个参数决定角色:api(默认)或 worker。
#
#   worker        → 守 default 队列(自动排课)
#   worker ops    → 守 ops 队列(导出/备份/恢复/发送邮件 + 定时任务)
# 两者同一个镜像,只差在守哪条队列(M6-2)。
set -e

ROLE="${1:-api}"

if [ "$ROLE" = "api" ]; then
    echo "[entrypoint] 执行数据库迁移 alembic upgrade head ..."
    alembic upgrade head
    echo "[entrypoint] 启动 API (uvicorn) ..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
elif [ "$ROLE" = "worker" ]; then
    shift
    echo "[entrypoint] 启动 RQ worker(队列:${*:-default})..."
    exec python -m app.workers.worker "$@"
else
    echo "[entrypoint] 未知角色: $ROLE(可用:api、worker [队列])" >&2
    exit 1
fi
