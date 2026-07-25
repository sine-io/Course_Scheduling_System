"""RQ worker 进入点。

两个 worker 进程,各守一条队列(M6-2):

    python -m app.workers.worker           # default:自动排课(可占住数分钟)
    python -m app.workers.worker ops       # ops:导出 / 备份 / 恢复 / 发送邮件 + 定时任务

分开的理由是快慢任务不该互相堵住:合在一条队列时,排课一开跑,排课管理员按导出就排在后面
等到超时失败。**排课永远只走 default**,ops worker 因此不会加载求解引擎,内存预算低得多。

调度器(`with_scheduler=True`)只挂在 ops worker:定时任务(每日备份、心跳)都排进 ops,
由它自己取出执行。排课 worker 不运行调度器——一次求解可能持续数分钟,不适合负责准时任务。
"""

import sys

from rq import Worker

from app.workers.queue import QUEUES, ops_queue, redis_conn
from app.workers.scheduler import ensure_scheduled


def main(argv: list[str] | None = None) -> None:
    names = list(argv if argv is not None else sys.argv[1:]) or ["default"]
    unknown = [n for n in names if n not in QUEUES]
    if unknown:
        raise SystemExit(f"未知的队列名称:{', '.join(unknown)}(可用:{', '.join(QUEUES)})")

    queues = [QUEUES[n] for n in names]
    runs_scheduler = ops_queue.name in names
    if runs_scheduler:
        ensure_scheduled()
    Worker(queues, connection=redis_conn).work(with_scheduler=runs_scheduler)


if __name__ == "__main__":
    main()
