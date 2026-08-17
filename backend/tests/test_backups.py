"""M5-2:备份/恢复的纯逻辑与 RBAC。实际 pg_dump/pg_restore(需 PostgreSQL 与
pg 工具)由 docker 整合测试涵盖;这里测文件头验证、轮替、列表、权限、非法上传拒绝。
"""

import pytest

from app.core.config import settings
from app.models.user import Role
from app.services import backup as bk
from tests.conftest import make_user

PW = "password123"
PGDMP = b"PGDMP" + b"\x00" * 100  # 假的 custom 格式文件头


def _confirmation(operation_id: str, target: str) -> dict[str, object]:
    return {
        "operation_id": operation_id,
        "confirmed": True,
        "target": target,
    }


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))
    return tmp_path


def _touch(dir_, name: str, content: bytes = PGDMP):
    (dir_ / name).write_bytes(content)


# ── 文件头验证(验收②)───────────────────────────────────────
def test_is_valid_dump(backup_dir):
    _touch(backup_dir, "good.dump", PGDMP)
    _touch(backup_dir, "bad.dump", b"not a dump")
    assert bk.is_valid_dump(str(backup_dir / "good.dump")) is True
    assert bk.is_valid_dump(str(backup_dir / "bad.dump")) is False


def test_save_uploaded_rejects_non_dump(backup_dir):
    with pytest.raises(bk.BackupError):
        bk.save_uploaded("x.dump", b"garbage bytes")
    # 拒绝的文件不落地
    assert list(backup_dir.iterdir()) == []


def test_save_uploaded_accepts_valid(backup_dir):
    name = bk.save_uploaded("x.dump", PGDMP)
    assert name.endswith("_upload.dump")
    assert (backup_dir / name).exists()


# ── 列表 / 轮替(验收③)───────────────────────────────────
def test_list_backups_newest_first(backup_dir):
    _touch(backup_dir, "backup_20260101_010101_manual.dump")
    _touch(backup_dir, "backup_20260301_010101_auto.dump")
    _touch(backup_dir, "notabackup.txt")
    names = [b.name for b in bk.list_backups()]
    assert names == [
        "backup_20260301_010101_auto.dump",
        "backup_20260101_010101_manual.dump",
    ]  # 非备份文件被忽略


def test_prune_keeps_newest(backup_dir):
    for i in range(1, 6):
        _touch(backup_dir, f"backup_2026010{i}_010101_auto.dump")
    removed = bk.prune(keep=2)
    remaining = sorted(b.name for b in bk.list_backups())
    assert len(remaining) == 2
    assert remaining == [
        "backup_20260104_010101_auto.dump",
        "backup_20260105_010101_auto.dump",
    ]
    assert len(removed) == 3


def test_path_traversal_rejected(backup_dir):
    with pytest.raises(bk.BackupError):
        bk.restore_backup("../../etc/passwd")


def test_restore_nonzero_exit_is_reported_as_rolled_back_failure(
    backup_dir, monkeypatch
):
    """单事务下连旧版可忽略的 SET 错误也会回滚，不能报告恢复成功。"""
    import subprocess

    name = "backup_20260101_010101_manual.dump"
    _touch(backup_dir, name)
    monkeypatch.setattr(bk, "_terminate_other_connections", lambda _params: None)
    seen: dict[str, list[str]] = {}

    def fake_run(command, **_kwargs):
        seen["command"] = command
        return subprocess.CompletedProcess(
            command,
            1,
            "",
            "pg_restore: error: unrecognized configuration parameter transaction_timeout",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(bk.BackupError, match="全部变更已回滚"):
        bk.restore_backup(name)
    assert "--single-transaction" in seen["command"]
    assert "--exit-on-error" in seen["command"]


# ── RBAC:仅管理员 ─────────────────────────────────────────
def _login(client, db, username, roles):
    make_user(db, username, PW, roles=roles)
    client.post("/api/auth/login", json={"username": username, "password": PW})


def test_list_backups_admin_only(env, backup_dir):
    client, db = env
    _login(client, db, "sch", [Role.scheduler])
    assert client.get("/api/backups").status_code == 403
    client.post("/api/auth/logout")
    _login(client, db, "adm", [Role.admin])
    r = client.get("/api/backups")
    assert r.status_code == 200
    assert r.json() == []


def test_restore_upload_rejects_garbage_before_touching_db(env, backup_dir):
    client, db = env
    _login(client, db, "adm", [Role.admin])
    r = client.post(
        "/api/backups/restore-upload",
        data={
            "operation_id": "66666666-6666-4666-8666-666666666666",
            "confirmed": "true",
            "target": "upload:evil.dump",
        },
        files={"file": ("evil.dump", b"rm -rf /", "application/octet-stream")},
    )
    assert r.status_code == 400
    assert "格式不符" in r.json()["detail"]
    assert list(backup_dir.iterdir()) == []  # 系统无损:没有文件落地


def test_scheduler_cannot_restore(env, backup_dir):
    client, db = env
    _login(client, db, "sch", [Role.scheduler])
    denied = client.post(
        "/api/backups/some.dump/restore",
        json=_confirmation("11111111-1111-4111-8111-111111111111", "backup:some.dump"),
    )
    assert denied.status_code == 403

    client.post("/api/auth/logout")
    _login(client, db, "adm-audit", [Role.admin])
    attempts = client.get("/api/audit-logs?action=restore_backup").json()["items"]
    assert len(attempts) == 1
    assert attempts[0]["username"] == "sch"
    assert attempts[0]["actor_roles"] == ["scheduler"]
    assert attempts[0]["target_version"] == "some.dump"
    assert attempts[0]["result"] == "rejected"
    assert attempts[0]["reason"] == "high_risk_permission_denied"


def test_scheduler_cannot_create_backup(env, backup_dir, monkeypatch):
    from app.api import backups as backups_api

    client, db = env
    _login(client, db, "sch", [Role.scheduler])
    called = False

    def fake_backup(_reason: str):
        nonlocal called
        called = True

    monkeypatch.setattr(backups_api.job_queue, "run_backup", fake_backup)
    denied = client.post(
        "/api/backups",
        json=_confirmation(
            "12121212-1212-4212-8212-121212121212",
            "backup:create",
        ),
    )

    assert denied.status_code == 403
    assert called is False
    client.post("/api/auth/logout")
    _login(client, db, "adm-audit", [Role.admin])
    log = client.get("/api/audit-logs?action=create_backup").json()["items"][0]
    assert log["username"] == "sch"
    assert log["result"] == "rejected"
    assert log["reason"] == "high_risk_permission_denied"


def test_create_backup_requires_confirmation_and_deduplicates_operation(
    env, backup_dir, monkeypatch
):
    from app.api import backups as backups_api

    client, db = env
    _login(client, db, "adm", [Role.admin])
    calls: list[str] = []

    def fake_backup(reason: str):
        calls.append(reason)
        return {
            "name": "backup_20260101_010101_manual.dump",
            "size_bytes": len(PGDMP),
            "created_at": "2026-01-01T01:01:01",
            "reason": reason,
        }

    monkeypatch.setattr(backups_api.job_queue, "run_backup", fake_backup)

    missing = client.post("/api/backups")
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "high_risk_confirmation_required"
    assert calls == []

    confirmation = _confirmation(
        "22222222-2222-4222-8222-222222222222",
        "backup:create",
    )
    created = client.post("/api/backups", json=confirmation)
    assert created.status_code == 201, created.text
    assert calls == ["manual"]

    repeated = client.post("/api/backups", json=confirmation)
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["code"] == "high_risk_duplicate_operation"
    assert calls == ["manual"]

    attempts = client.get("/api/audit-logs?action=create_backup").json()["items"]
    assert [(item["result"], item["reason"]) for item in reversed(attempts)] == [
        ("rejected", "high_risk_confirmation_required"),
        ("success", ""),
        ("rejected", "high_risk_duplicate_operation"),
    ]
    assert attempts[1]["operation_id"] == confirmation["operation_id"]


def test_delete_backup_requires_confirmation_and_records_success(env, backup_dir):
    client, db = env
    name = "backup_20260101_010101_manual.dump"
    _touch(backup_dir, name)
    _login(client, db, "adm", [Role.admin])

    missing = client.delete(f"/api/backups/{name}")
    assert missing.status_code == 409
    assert (backup_dir / name).exists()

    deleted = client.request(
        "DELETE",
        f"/api/backups/{name}",
        json=_confirmation(
            "77777777-7777-4777-8777-777777777777",
            f"backup:{name}",
        ),
    )
    assert deleted.status_code == 200
    assert not (backup_dir / name).exists()
    log = client.get("/api/audit-logs?action=delete_backup").json()["items"][0]
    assert log["username"] == "adm"
    assert log["target_version"] == name
    assert log["result"] == "success"


def test_delete_backup_file_failure_is_not_reported_as_success(
    env, backup_dir, monkeypatch
):
    from app.api import backups as backups_api

    client, db = env
    name = "backup_20260101_010101_manual.dump"
    _touch(backup_dir, name)
    _login(client, db, "adm", [Role.admin])

    def fail_remove(_path):
        raise OSError("read only")

    monkeypatch.setattr(backups_api.os, "remove", fail_remove)
    failed = client.request(
        "DELETE",
        f"/api/backups/{name}",
        json=_confirmation(
            "88888888-8888-4888-8888-888888888888",
            f"backup:{name}",
        ),
    )

    assert failed.status_code == 500
    assert (backup_dir / name).exists()
    log = client.get("/api/audit-logs?action=delete_backup").json()["items"][0]
    assert log["result"] == "failed"
    assert log["reason"] == "backup_delete_failed"


def test_restore_requires_exact_target_and_records_worker_failure(
    env, backup_dir, monkeypatch
):
    from app.api import backups as backups_api

    client, db = env
    name = "backup_20260101_010101_manual.dump"
    _touch(backup_dir, name)
    _login(client, db, "adm", [Role.admin])
    restore_calls: list[str] = []

    monkeypatch.setattr(backups_api.job_queue, "solver_busy", lambda: False)
    monkeypatch.setattr(
        backups_api.job_queue,
        "run_backup",
        lambda reason: {"name": f"backup_20260102_010101_{reason}.dump"},
    )

    def fail_restore(target: str):
        restore_calls.append(target)
        raise backups_api.job_queue.BackupJobError("校验失败")

    monkeypatch.setattr(backups_api.job_queue, "run_restore", fail_restore)

    wrong_target = client.post(
        f"/api/backups/{name}/restore",
        json=_confirmation(
            "33333333-3333-4333-8333-333333333333",
            "backup:another.dump",
        ),
    )
    assert wrong_target.status_code == 409
    assert wrong_target.json()["detail"]["code"] == "high_risk_target_mismatch"
    assert restore_calls == []

    failed = client.post(
        f"/api/backups/{name}/restore",
        json=_confirmation(
            "44444444-4444-4444-8444-444444444444",
            f"backup:{name}",
        ),
    )
    assert failed.status_code == 502
    assert restore_calls == [name]

    attempts = client.get("/api/audit-logs?action=restore_backup").json()["items"]
    assert [(item["result"], item["reason"]) for item in reversed(attempts)] == [
        ("rejected", "high_risk_target_mismatch"),
        ("failed", "backup_job_failed"),
    ]


# ── 恢复前不得保留会被 pg_restore 中止的数据库会话(M6-6 实测发现)────────
def test_restore_closes_the_request_session_before_touching_the_database(
    env, backup_dir, monkeypatch
):
    """pg_restore --clean 会中止数据库上的所有连接,包括本请求验证身份时建立的连接。

    yield 依赖是在**响应发送后**才收尾,届时 db.close() 会通过已经失效的连接发送 ROLLBACK,
    在日志中输出 AdminShutdown traceback——响应与数据都是对的,但刚按下「恢复」的人看到
    那段红字只会以为恢复失败了。因此,分派恢复任务前必须先关闭这个数据库会话。
    """
    from app.api import backups as backups_api
    from app.core.db import get_db

    client, db = env
    _touch(backup_dir, "backup_20260101_010101_manual.dump")
    _login(client, db, "adm", [Role.admin])

    # 拦下请求用的 session,记下它是否被关闭
    original = client.app.dependency_overrides[get_db]
    closed: dict[str, bool] = {}

    def spy_get_db():
        gen = original()
        session = next(gen)
        real_close = session.close

        def close():
            closed["yes"] = True
            real_close()

        session.close = close  # type: ignore[method-assign]
        try:
            yield session
        finally:
            next(gen, None)

    client.app.dependency_overrides[get_db] = spy_get_db

    seen: dict[str, bool] = {}

    def fake_restore(name):
        # 这一刻 pg_restore 正要砍掉所有连接:请求的 session 必须已经关了
        seen["closed_before_restore"] = closed.get("yes", False)
        return []

    monkeypatch.setattr(backups_api.job_queue, "solver_busy", lambda: False)
    monkeypatch.setattr(
        backups_api.job_queue, "run_backup",
        lambda reason: {"name": f"backup_20260102_010101_{reason}.dump"},
    )
    monkeypatch.setattr(backups_api.job_queue, "run_restore", fake_restore)

    try:
        r = client.post(
            "/api/backups/backup_20260101_010101_manual.dump/restore",
            json=_confirmation(
                "55555555-5555-4555-8555-555555555555",
                "backup:backup_20260101_010101_manual.dump",
            ),
        )
    finally:
        client.app.dependency_overrides[get_db] = original

    assert r.status_code == 200
    assert r.json()["restored_from"] == "backup_20260101_010101_manual.dump"
    assert seen["closed_before_restore"] is True


def test_get_db_teardown_never_raises(monkeypatch, caplog):
    """收尾关 session 失败不该变成一段没有请求可归属的 ASGI traceback——
    用户早就拿到(正确的)响应了。真正的失败会在查询当下就报错,不会被这里盖掉。"""
    from app.core import db as db_mod

    class _DeadSession:
        def close(self):
            raise RuntimeError("terminating connection due to administrator command")

    monkeypatch.setattr(db_mod, "SessionLocal", lambda: _DeadSession())

    gen = db_mod.get_db()
    next(gen)
    with caplog.at_level("WARNING"), pytest.raises(StopIteration):
        next(gen)  # 触发 finally:不得抛出异常
    assert "恢复" in caplog.text
