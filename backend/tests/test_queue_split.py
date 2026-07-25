"""M6-2:后台任务队列拆分(default = 排课 / ops = 导出、备份、恢复、发送邮件、定时)。

验的是「分派任务去了正确的队列」与「升级不会让每日备份静默断裂」——真正的隔离效果
(排课进行中导出仍立即响应)必须在 docker 全栈实测,单元测试证不了。
"""

import pytest
from rq.registry import ScheduledJobRegistry

from app.workers import queue as q
from app.workers import scheduler as sched
from app.workers import worker as worker_mod


class _FakeQueue:
    """记下 enqueue 到哪条队列、派了什么函数。"""

    def __init__(self, name):
        self.name = name
        self.calls: list[str] = []

    def _record(self, func):
        self.calls.append(getattr(func, "__name__", str(func)))
        return _FakeJob()

    def enqueue(self, func, *a, **k):
        return self._record(func)

    def enqueue_in(self, _delta, func, **k):
        return self._record(func)

    def enqueue_at(self, _when, func, **k):
        return self._record(func)


class _FakeJob:
    def latest_result(self):
        return None

    def cancel(self):
        pass


def _fake_worker(count):
    """假的 rq.Worker,只提供 count()——ops 队列上有几个 worker 在守。"""

    class _W:
        @classmethod
        def count(cls, connection=None, queue=None):
            if callable(count):
                return count()
            return count

    return _W


@pytest.fixture
def queues(monkeypatch):
    default, ops = _FakeQueue("default"), _FakeQueue("ops")
    for mod in (q, sched):
        monkeypatch.setattr(mod, "default_queue", default, raising=False)
        monkeypatch.setattr(mod, "ops_queue", ops, raising=False)
    monkeypatch.setattr(q, "Worker", _fake_worker(1))  # 默认:worker-ops 正常在跑
    return default, ops


# ── 分派任务路由 ─────────────────────────────────────────────────
def test_auto_schedule_goes_to_default(queues):
    default, ops = queues
    q.enqueue_solve("job-1", 1, 60.0, 1, None, "u")
    assert default.calls == ["run_auto_schedule"]
    assert ops.calls == [], "排课绝不能进 ops:它一跑数分钟,会把导出/备份全堵住"


def test_email_goes_to_ops(queues):
    default, ops = queues
    q.enqueue_email("a@b.c", "主旨", "内文")
    assert (ops.calls, default.calls) == (["send_notification_email"], [])


@pytest.mark.parametrize(("call", "error", "expected"), [
    (lambda: q.render_export("<html></html>", "png", timeout=1), q.RenderError,
     "render_timetable_png"),
    (lambda: q.run_backup("manual", timeout=1), q.BackupJobError, "create_backup_job"),
    (lambda: q.run_restore("x.dump", timeout=1), q.BackupJobError, "restore_job"),
])
def test_blocking_ops_work_goes_to_ops_queue(queues, call, error, expected):
    """导出/备份/恢复统一走 ops——正是排课那几分钟里排课管理员会按的东西。

    这些是阻塞式分派任务,假队列不会回结果,必然以超时作收;此处只在意「派去哪条队列」。
    """
    default, ops = queues
    with pytest.raises(error):
        call()
    assert (ops.calls, default.calls) == ([expected], [])


def test_scheduled_jobs_go_to_ops(queues):
    """定时任务(每日备份、心跳)是运维工作,排进 ops;排课 worker 不跑调度器。"""
    _default, ops = queues
    sched.schedule_daily_backup()
    sched._schedule_next()
    assert ops.calls == ["daily_backup_job", "heartbeat"]


# ── worker 进入点 ────────────────────────────────────────────
def test_worker_defaults_to_the_solve_queue_without_scheduler(monkeypatch):
    started: dict = {}

    class _W:
        def __init__(self, queues, connection):
            started["queues"] = [x.name for x in queues]

        def work(self, with_scheduler):
            started["scheduler"] = with_scheduler

    monkeypatch.setattr(worker_mod, "Worker", _W)
    monkeypatch.setattr(worker_mod, "ensure_scheduled", lambda: started.setdefault("ensured", True))

    worker_mod.main([])
    assert started["queues"] == ["default"]
    # 排课 worker 一忙就是好几分钟,不该负责「准时」的事
    assert started["scheduler"] is False
    assert "ensured" not in started


def test_ops_worker_runs_the_scheduler(monkeypatch):
    started: dict = {}

    class _W:
        def __init__(self, queues, connection):
            started["queues"] = [x.name for x in queues]

        def work(self, with_scheduler):
            started["scheduler"] = with_scheduler

    monkeypatch.setattr(worker_mod, "Worker", _W)
    monkeypatch.setattr(worker_mod, "ensure_scheduled", lambda: started.setdefault("ensured", True))

    worker_mod.main(["ops"])
    assert started["queues"] == ["ops"]
    assert started["scheduler"] is True
    assert started["ensured"] is True


def test_worker_rejects_an_unknown_queue_name(monkeypatch):
    monkeypatch.setattr(worker_mod, "Worker", lambda *a, **k: pytest.fail("不该走到这"))
    with pytest.raises(SystemExit, match="未知的队列名称"):
        worker_mod.main(["solver"])


# ── 升级路径:旧版排在 default 的定时任务要清掉 ───────────────
def test_legacy_default_schedules_are_dropped_on_upgrade(monkeypatch):
    """M6-2 之前每日备份排在 default;调度器改为监听 ops 后,旧任务不会再被取出——
    不清掉的话备份链就静默断了(而备份最怕的正是静默断裂)。"""
    removed: list[str] = []

    class _Registry:
        def __init__(self, queue):
            self.queue = queue

        def get_job_ids(self):
            if self.queue.name == "default":
                return [sched.HEARTBEAT_JOB_ID, sched.DAILY_BACKUP_JOB_ID, "some-other-job"]
            return []

        def remove(self, job_id, delete_job=False):
            removed.append(job_id)

    default, ops = _FakeQueue("default"), _FakeQueue("ops")
    monkeypatch.setattr(sched, "default_queue", default)
    monkeypatch.setattr(sched, "ops_queue", ops)
    monkeypatch.setattr(sched, "ScheduledJobRegistry", _Registry)

    sched.ensure_scheduled()

    assert removed == [sched.HEARTBEAT_JOB_ID, sched.DAILY_BACKUP_JOB_ID]
    assert "some-other-job" not in removed, "只动自己的固定 job_id,别人的调度不碰"
    # 清完之后,两个定时任务在 ops 上重新排好
    assert ops.calls == ["heartbeat", "daily_backup_job"]


def test_registry_helper_is_wired_to_the_real_rq_registry():
    """避免上面的假 Registry 把真实接线测没了。"""
    assert sched.ScheduledJobRegistry is ScheduledJobRegistry


# ── 升级路径:ops 队列没有 worker 时要立刻说清楚 ───────────────
def test_ops_worker_availability_reads_the_queue(monkeypatch):
    monkeypatch.setattr(q, "Worker", _fake_worker(1))
    assert q.ops_worker_available() is True
    monkeypatch.setattr(q, "Worker", _fake_worker(0))
    assert q.ops_worker_available() is False


def test_ops_worker_availability_is_permissive_when_it_cannot_tell(monkeypatch):
    """Redis 抖动时误判成「没有 worker」,会挡掉本来会成功的导出与备份——宁可放行。"""
    def _boom():
        raise ConnectionError("redis 挂了")

    monkeypatch.setattr(q, "Worker", _fake_worker(_boom))
    assert q.ops_worker_available() is True


@pytest.mark.parametrize(("call", "error"), [
    (lambda: q.render_export("<html></html>", "png", timeout=1), q.RenderError),
    (lambda: q.run_backup("manual", timeout=1), q.BackupJobError),
    (lambda: q.run_restore("x.dump", timeout=1), q.BackupJobError),
])
def test_ops_work_fails_fast_when_no_ops_worker(queues, monkeypatch, call, error):
    """沿用旧 compose 升级时,ops 上没有任何 worker。原本要等 90~180 秒才超时,
    而且错误信息说不出原因;现在立刻回一句讲得出处理方式的话。"""
    _default, ops = queues
    monkeypatch.setattr(q, "Worker", _fake_worker(0))

    with pytest.raises(error, match="worker-ops"):
        call()
    # 既然任务不会被取出,就不应放入该队列——恢复尤其危险:延迟执行会在无预警情况下覆盖数据库
    assert ops.calls == []


def test_email_never_raises_when_no_ops_worker(queues, monkeypatch, caplog):
    """发送邮件的调用点在事务 commit 之后:站内通知已送达、操作已成功,不能为了一封邮件报错。
    信照排(worker-ops 一起来就补寄),但要在 log 留下看得懂的原因。"""
    _default, ops = queues
    monkeypatch.setattr(q, "Worker", _fake_worker(0))

    with caplog.at_level("ERROR"):
        q.enqueue_email("a@b.c", "主旨", "内文")

    assert ops.calls == ["send_notification_email"]
    assert "worker-ops" in caplog.text
