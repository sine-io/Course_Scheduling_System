"""定时任务调度骨架(M5-0;M6-2 起改挂 ops 队列)。

RQ worker 以 `with_scheduler=True` 启动,内置调度器会在到期时把排定的任务丢回队列。
周期任务用「执行时把下一次排进去」的自我续期模式表达——不必额外的 rq-scheduler 组件或
独立容器。定时任务(每日备份、心跳)都是运维任务,故统一排进 **ops** 队列,由 ops worker
兼任调度器;排课队列被占用数分钟时,备份仍可正常执行。

心跳任务只证明调度器存活(写一行 log 并排下一次)。以固定 job_id 续期,重启不会堆叠。
"""

import logging
from datetime import datetime, timedelta

from rq.registry import ScheduledJobRegistry

from app.core import clock
from app.core.config import settings
from app.workers.queue import default_queue, ops_queue

logger = logging.getLogger(__name__)

HEARTBEAT_JOB_ID = "scheduler-heartbeat"
DAILY_BACKUP_JOB_ID = "daily-backup"


def _interval() -> timedelta:
    return timedelta(seconds=settings.scheduler_heartbeat_seconds)


def _schedule_next() -> None:
    # 固定 job_id:同时只会有一个待执行的心跳,重复排入会覆盖而非堆叠
    ops_queue.enqueue_in(_interval(), heartbeat, job_id=HEARTBEAT_JOB_ID)


def heartbeat() -> None:
    """调度器存活心跳;执行时把下一次排进去(自我续期)。

    顺带自愈每日备份链:若 daily-backup 因某次失败而未再排入(见 backup_job),
    这里补排回去——备份系统最忌讳的是静默断裂,心跳每小时兜底一次。
    """
    try:
        logger.info("调度器心跳 OK,下次 %s 后", _interval())
        _ensure_daily_backup_scheduled()
    finally:
        _schedule_next()  # 无论本次是否出错,下一次心跳一定排入


def _ensure_daily_backup_scheduled() -> None:
    try:
        registry = ScheduledJobRegistry(queue=ops_queue)
        if DAILY_BACKUP_JOB_ID not in set(registry.get_job_ids()):
            schedule_daily_backup()
            logger.warning("检测到每日备份未排入,已补排,下次 %s", _next_backup_time())
    except Exception:  # noqa: BLE001 - 自愈失败不该让心跳挂掉
        logger.warning("检查/补排每日备份失败(Redis 不可用?)")


def _drop_legacy_default_schedules() -> None:
    """清掉旧版排在 **default** 队列上的定时任务(M6-2 之前的版本)。

    升级后调度器改看 ops 队列。若不清,旧的 daily-backup / heartbeat 会永远留在
    default 的 ScheduledJobRegistry 里——排课 worker 不运行调度器,这些任务不会被取出,
    每日备份就此静默断裂(备份系统最不能忍的失败模式)。以固定 job_id 精准移除。
    """
    try:
        registry = ScheduledJobRegistry(queue=default_queue)
        for job_id in (HEARTBEAT_JOB_ID, DAILY_BACKUP_JOB_ID):
            if job_id in set(registry.get_job_ids()):
                registry.remove(job_id, delete_job=True)
                logger.info("已移除旧版排在 default 队列的定时任务:%s", job_id)
    except Exception:  # noqa: BLE001 - 清理失败不该让 worker 起不来
        logger.warning("清理旧版 default 队列定时任务失败(Redis 不可用?)")


def _next_backup_time() -> datetime:
    """学校时区的下一个 backup_hour 时刻(unaware,供 enqueue_at)。"""
    now = clock.school_now().replace(tzinfo=None)
    target = now.replace(hour=settings.backup_hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def schedule_daily_backup() -> None:
    from app.workers.backup_job import daily_backup_job
    ops_queue.enqueue_at(_next_backup_time(), daily_backup_job, job_id=DAILY_BACKUP_JOB_ID)


def ensure_scheduled() -> None:
    """ops worker 启动时调用:确保心跳与每日备份已排入(已存在则跳过,重启不重复)。"""
    _drop_legacy_default_schedules()
    try:
        registry = ScheduledJobRegistry(queue=ops_queue)
        pending = set(registry.get_job_ids())
        if HEARTBEAT_JOB_ID not in pending:
            _schedule_next()
            logger.info("已排入调度器心跳,间隔 %s", _interval())
        if DAILY_BACKUP_JOB_ID not in pending:
            schedule_daily_backup()
            logger.info("已排入每日自动备份,下次 %s", _next_backup_time())
    except Exception:  # noqa: BLE001 - Redis 不可用不该让 worker 起不来
        logger.warning("排入定时任务失败(Redis 不可用?);后台任务仍可运行")
