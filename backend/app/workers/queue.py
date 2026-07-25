"""RQ 队列与连接设置。排课、邮件、备份等后台任务均通过此队列分派。"""

import logging
import time

from redis import Redis
from rq import Queue, Worker

from app.core.config import settings

logger = logging.getLogger(__name__)

redis_conn = Redis.from_url(settings.redis_url)

# 两条队列,两个 worker 进程(M6-2)。分开的理由是「快慢任务不该互相堵住」:
#   default → 自动排课。60 班可跑数分钟,期间这个 worker 完全占住。
#   ops     → 导出 / 备份 / 恢复 / 发送邮件。都是秒级,但正是排课那几分钟里排课管理员最常按的。
# 合在一条队列时,排课一开跑,导出就排在后面等到超时失败(M5 复审 A)。
default_queue = Queue("default", connection=redis_conn)
ops_queue = Queue("ops", connection=redis_conn)

QUEUES = {q.name: q for q in (default_queue, ops_queue)}

# 求解超时后仍需时间写回结果,无解时还要跑冲突定位;RQ 的看门狗要比 solver 的 timeout 宽松。
# 被 RQ 砍掉的话,用户等了十分钟却连「为什么排不出来」都拿不到。
JOB_TIMEOUT_MARGIN = 240


def enqueue_solve(
    job_id: str,
    timetable_id: int,
    max_seconds: float,
    seed: int,
    user_id: int | None,
    username: str,
    allow_partial: bool = False,
    relax: list[str] | None = None,
) -> None:
    """把自动排课任务丢进队列(API 层调用;测试以假队列取代)。"""
    from app.workers.solve_job import run_auto_schedule

    default_queue.enqueue(
        run_auto_schedule,
        job_id, timetable_id, max_seconds, seed, user_id, username,
        allow_partial, relax or [],
        job_id=job_id,
        job_timeout=int(max_seconds) + JOB_TIMEOUT_MARGIN,
    )


# 升级时只换镜像、沿用旧 docker-compose.yml 的话,ops 队列上不会有任何 worker
# (旧 compose 只起一个 `worker`,在新镜像下只守 default)。后果不只是导出/备份超时,
# 调度器也不存在——**每日备份会静默停摆**。故所有派往 ops 的路径先确认有人在守,
# 把「90 秒后的谜样超时」换成一句说得出原因、讲得出处理方式的错误(Fable 5 M6 复审 A)。
OPS_WORKER_MISSING = (
    "运维背景服务(worker-ops)没有在执行。v1.1 起导出、备份、恢复、发送邮件与每日自动备份"
    "由独立的 worker-ops 容器负责;若你刚升级,请一并更新 docker-compose.yml 再执行"
    "`sudo docker compose up -d`（见升级指南），并执行 "
    "`sudo docker compose ps` 确认 worker-ops 已启动"
)


def ops_worker_available() -> bool:
    """ops 队列上是否有 worker 在守。

    判断不了时(Redis 抖动、RQ 版本差异)统一回 True:误判成「没有 worker」会挡掉
    本来会成功的导出与备份,比让它照原路超时更糟。这道检查是为了把常见的升级失误
    讲清楚,不是把自己变成新的故障点。
    """
    try:
        return Worker.count(connection=redis_conn, queue=ops_queue) > 0
    except Exception:  # noqa: BLE001 - 无法判断时保守放行
        return True


def enqueue_email(to: str, subject: str, body: str) -> None:
    """把通知邮件放入队列(通知服务在事务 commit 后调用)。

    这里**不抛出异常**:调用点在 SQLAlchemy 的 after_commit,事务已经提交,站内通知也已送达,
    不能为了一封信让已完成的操作看起来像失败(M4-3 的语义)。信照样排进队列——worker-ops
    一起来就会补寄;但要在 log 留下一句看得懂的话,否则信就无声消失了。
    """
    from app.workers.email_job import send_notification_email

    if not ops_worker_available():
        logger.error("通知 Email 无人处理(收件:%s):%s", to, OPS_WORKER_MISSING)
    ops_queue.enqueue(send_notification_email, to, subject, body, job_timeout=60)


class RenderError(RuntimeError):
    """PDF/PNG 渲染失败或超时(调用方转为 5xx)。"""


RESULT_POLL_INTERVAL = 0.5


def _wait_result(job, timeout: int):
    """轮询等待 job 的最新结果;超时回 None。

    不用 RQ 的 `latest_result(timeout=...)`:它以 XREAD 阻塞读等结果,redis-py 8
    (RESP3 成为默认)之后结果写入不会唤醒阻塞中的读端,最后以 socket 超时收场
    (2026-07-13 CI 首跑抓到:worker 6 秒完成 PNG 渲染,api 却等到超时回 500;
    本机镜像因 pip layer 缓存仍是旧版 redis-py 而测不到)。改为每 0.5s 以
    XREVRANGE 轮询,对任何 client 版本/协定都成立,延迟对导出/备份无感。
    """
    deadline = time.monotonic() + timeout
    while True:
        result = job.latest_result()  # 非阻塞:XREVRANGE count=1
        if result is not None:
            return result
        if time.monotonic() >= deadline:
            return None
        time.sleep(RESULT_POLL_INTERVAL)


def _cancel_quietly(job) -> None:
    """超时后把仍在队列中的 job 取消,避免 worker 空下来后才「补跑」一个没人等的任务
    (对恢复尤其危险:api 已回失败,几分钟后数据库却被无预警覆盖)。"""
    try:
        job.cancel()
    except Exception:  # noqa: BLE001 - 取消失败不影响对调用方的错误报告
        pass


def render_export(html: str, fmt: str, *, timeout: int = 90) -> bytes:
    """在 worker 渲染 PDF/PNG,阻塞等待结果并返回 bytes(api 导出端点调用)。

    api 镜像无 WeasyPrint 依赖,故统一派到 worker;结果经 RQ result 取回。
    """
    from app.workers.export_job import render_timetable_pdf, render_timetable_png

    if not ops_worker_available():
        raise RenderError(OPS_WORKER_MISSING)
    func = render_timetable_pdf if fmt == "pdf" else render_timetable_png
    job = ops_queue.enqueue(func, html, job_timeout=timeout + 30, result_ttl=120)
    result = _wait_result(job, timeout)
    if result is None or result.type != result.Type.SUCCESSFUL:
        if result is None:
            _cancel_quietly(job)
        detail = getattr(result, "exc_string", None) or "背景忙碌或超时,请稍后再试"
        raise RenderError(f"课表{fmt.upper()}渲染失败:{detail}")
    data = result.return_value
    if not isinstance(data, bytes):
        raise RenderError(f"课表{fmt.upper()}渲染返回非预期类型")
    return data


def solver_busy() -> bool:
    """是否有自动排课任务正在执行或排队中(供恢复前置检查)。

    分队列后(M6-2)恢复不再排在排课后面等,但这道关口仍然必要——**这是数据安全,不是排队**:
    恢复会 pg_restore --clean 覆盖整个数据库,而排课中的 worker 正要把结果写回同一个库。
    两者同时进行,写回的草稿会落进一个刚被抹掉的世界。故排课进行中统一拒绝恢复(409)。
    只看 default 队列即可:排课永远只走这条。
    """
    from rq.registry import StartedJobRegistry

    def _is_solve(job) -> bool:
        return bool(job and job.func_name and "run_auto_schedule" in job.func_name)

    try:
        started = StartedJobRegistry(queue=default_queue)
        for jid in started.get_job_ids():
            if _is_solve(default_queue.fetch_job(jid)):
                return True
        return any(_is_solve(job) for job in default_queue.jobs)
    except Exception:  # noqa: BLE001 - 无法判断时保守放行(不因 Redis 抖动阻止恢复)
        return False


class BackupJobError(RuntimeError):
    """备份/恢复任务失败或超时(调用方转为 5xx)。"""


def _run_blocking(func, *args, timeout: int):
    if not ops_worker_available():
        raise BackupJobError(OPS_WORKER_MISSING)
    job = ops_queue.enqueue(func, *args, job_timeout=timeout + 30, result_ttl=300)
    result = _wait_result(job, timeout)
    if result is None or result.type != result.Type.SUCCESSFUL:
        if result is None:
            _cancel_quietly(job)  # 超时的任务不留在队列里等待晚点才跑
        detail = getattr(result, "exc_string", None) or "背景忙碌或超时"
        raise BackupJobError(detail)
    return result.return_value


def run_backup(reason: str = "manual", *, timeout: int = 120) -> dict:
    """在 worker 跑 pg_dump,阻塞等待并返回备份信息(api 调用)。"""
    from app.workers.backup_job import create_backup_job
    return _run_blocking(create_backup_job, reason, timeout=timeout)


def run_restore(name: str, *, timeout: int = 180) -> list[str]:
    """在 worker 跑 pg_restore,阻塞等待完成(api 调用)。返回可忽略的警告摘要。"""
    from app.workers.backup_job import restore_job
    return _run_blocking(restore_job, name, timeout=timeout)
