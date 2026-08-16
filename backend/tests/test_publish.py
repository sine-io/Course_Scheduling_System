"""版本管理与发布(M2-5)测试。对应验收标准①②③。"""

from datetime import UTC, datetime

import pytest

from app.models.basedata import Teacher
from app.models.user import Role
from tests.api_helpers import publish_checked_timetable
from tests.conftest import make_user
from tests.dates import SEM_END, SEM_START
from tests.test_timetables import (
    MAIN_SLOTS,
    _assign,
    _class,
    _entries,
    _periods,
    _place,
    _subject,
    _teacher,
)

PW = "password123"


@pytest.fixture
def env3(env):
    """排课管理员 + 学期 + 主作息时间表 + 一份草稿A。返回 (client, sid, ttA_id, db)。"""
    client, db = env
    make_user(db, "s", PW, roles=[Role.scheduler])
    client.post("/api/auth/login", json={"username": "s", "password": PW})
    sid = client.post(
        "/api/semesters",
        json={
            "academic_year": 2026,
            "term": 1,
            "start_date": SEM_START.isoformat(),
            "end_date": SEM_END.isoformat(),
        },
    ).json()["id"]
    pt = client.post(
        f"/api/semesters/{sid}/period-tables", json={"name": "主表", "is_default": True}
    ).json()
    client.put(f"/api/period-tables/{pt['id']}/periods", json=_periods(MAIN_SLOTS))
    ready = client.post(f"/api/semesters/{sid}/readiness")
    assert ready.status_code == 200, ready.text
    tt = client.post(f"/api/timetables?semester_id={sid}", json={"name": "草稿A"}).json()
    return client, sid, tt["id"], db


def _one_period_course(client, sid, cname="301", sname="语文", tname="王师"):
    """创建一项「每周 1 节」的教学任务,方便排满。"""
    c = _class(client, sid, 3, cname)
    s = _subject(client, sid, sname)
    t = _teacher(client, sid, tname)
    return _assign(client, sid, class_id=c["id"], subject_id=s["id"],
                   teacher_ids=[t["id"]], periods=1)


# ── 完整性检查 ────────────────────────
def test_completeness_reports_unplaced(env3):
    client, sid, tid, _ = env3
    a = _one_period_course(client, sid)  # 需 1 节
    # 再加一项需 3 节的教学任务,完全未排
    c2 = _class(client, sid, 3, "302")
    s2 = _subject(client, sid, "数学")
    t2 = _teacher(client, sid, "李师")
    _assign(client, sid, class_id=c2["id"], subject_id=s2["id"],
            teacher_ids=[t2["id"]], periods=3)

    r = client.get(f"/api/timetables/{tid}/completeness").json()
    assert r["complete"] is False
    assert r["required"] == 4 and r["placed"] == 0 and r["remaining"] == 4
    assert len(r["unplaced"]) == 2

    _place(client, tid, a["id"], 1, 1)
    r = client.get(f"/api/timetables/{tid}/completeness").json()
    assert r["placed"] == 1
    assert [u["subject"] for u in r["unplaced"]] == ["数学"]
    assert r["unplaced"][0]["remaining"] == 3


def test_completeness_complete_when_all_placed(env3):
    client, sid, tid, _ = env3
    a = _one_period_course(client, sid)
    _place(client, tid, a["id"], 1, 1)
    r = client.get(f"/api/timetables/{tid}/completeness").json()
    assert r["complete"] is True and r["remaining"] == 0 and r["unplaced"] == []


def test_publication_check_marks_complete_current_draft_as_checked(env3):
    client, sid, tid, _ = env3
    assignment = _one_period_course(client, sid)
    _place(client, tid, assignment["id"], 1, 1)

    response = client.post(f"/api/timetables/{tid}/publication-check")

    assert response.status_code == 200, response.text
    check = response.json()
    assert check["semester"] == {"id": sid, "label": "2026-2027学年第一学期"}
    assert check["version"] == {"id": tid, "name": "草稿A"}
    assert check["passed"] is True
    assert check["requires_force"] is False
    assert datetime.fromisoformat(check["checked_at"]).utcoffset() == UTC.utcoffset(None)
    assert check["completeness"] == {
        "required": 1,
        "placed": 1,
        "remaining": 0,
        "complete": True,
        "unplaced": [],
    }
    assert check["fingerprint"]
    versions = client.get(f"/api/timetables?semester_id={sid}").json()
    assert versions[0]["status"] == "draft"
    assert versions[0]["publication_state"] == "checked"


def test_director_can_read_completeness_but_cannot_record_publication_check(env3):
    client, sid, tid, db = env3
    make_user(db, "director-check", PW, roles=[Role.director])
    client.post("/api/auth/logout")
    client.post(
        "/api/auth/login",
        json={"username": "director-check", "password": PW},
    )

    assert client.get(f"/api/timetables/{tid}/completeness").status_code == 200
    assert client.post(f"/api/timetables/{tid}/publication-check").status_code == 403
    versions = client.get(f"/api/timetables?semester_id={sid}").json()
    assert versions[0]["publication_state"] == "draft"


def test_publish_requires_confirmation_from_a_fresh_check(env3):
    client, sid, tid, _ = env3
    assignment = _one_period_course(client, sid)
    _place(client, tid, assignment["id"], 1, 1)

    unconfirmed = client.post(f"/api/timetables/{tid}/publish", json={})

    assert unconfirmed.status_code == 409
    assert unconfirmed.json()["detail"]["code"] == "publication_confirmation_required"
    assert client.get(f"/api/timetables/{tid}").json()["status"] == "draft"

    check = client.post(f"/api/timetables/{tid}/publication-check").json()
    confirmed = client.post(
        f"/api/timetables/{tid}/publish",
        json={"fingerprint": check["fingerprint"]},
    )

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "published"


def test_rejected_publish_attempts_have_structured_audit_records(env3):
    client, sid, tid, db = env3
    assignment = _one_period_course(client, sid)
    _place(client, tid, assignment["id"], 1, 1)

    assert client.post(f"/api/timetables/{tid}/publish", json={}).status_code == 409

    for username, role in (("director1", Role.director), ("teacher1", Role.teacher)):
        make_user(db, username, PW, roles=[role])
        client.post("/api/auth/logout")
        client.post("/api/auth/login", json={"username": username, "password": PW})
        assert client.post(
            f"/api/timetables/{tid}/publish",
            json={"fingerprint": "not-a-valid-check"},
        ).status_code == 403

    make_user(db, "admin1", PW, roles=[Role.admin])
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "admin1", "password": PW})
    logs = client.get("/api/audit-logs?action=publish_timetable").json()

    assert len(logs) == 3
    by_user = {log["username"]: log for log in logs}
    assert by_user["s"]["actor_roles"] == ["scheduler"]
    assert by_user["s"]["reason"] == "publication_confirmation_required"
    for username, role in (("director1", "director"), ("teacher1", "teacher")):
        assert by_user[username]["actor_roles"] == [role]
        assert by_user[username]["reason"] == "publication_permission_denied"
    for log in logs:
        assert log["semester_id"] == sid
        assert log["target_version"] == f"草稿A (#{tid})"
        assert log["result"] == "rejected"
        assert log["created_at"]


def test_stale_and_repeated_confirmations_are_atomic_and_audited(env3):
    client, sid, tid, db = env3
    assignment = _one_period_course(client, sid)
    _place(client, tid, assignment["id"], 1, 1)
    stale_check = client.post(f"/api/timetables/{tid}/publication-check").json()

    entry = _entries(client, tid)[0]
    moved = client.patch(
        f"/api/timetables/{tid}/entries/{entry['id']}",
        json={"weekday": 2, "period_no": 2},
    )
    assert moved.status_code == 200, moved.text
    stale = client.post(
        f"/api/timetables/{tid}/publish",
        json={"fingerprint": stale_check["fingerprint"]},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "publication_check_stale"
    versions = client.get(f"/api/timetables?semester_id={sid}").json()
    assert versions[0]["status"] == "draft"
    assert versions[0]["publication_state"] == "draft"

    fresh_check = client.post(f"/api/timetables/{tid}/publication-check").json()
    confirmation = {"fingerprint": fresh_check["fingerprint"]}
    assert client.post(
        f"/api/timetables/{tid}/publish", json=confirmation
    ).status_code == 200
    repeated = client.post(f"/api/timetables/{tid}/publish", json=confirmation)
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["code"] == "publication_already_submitted"
    versions = client.get(f"/api/timetables?semester_id={sid}").json()
    assert [version["status"] for version in versions] == ["published"]

    make_user(db, "audit-admin", PW, roles=[Role.admin])
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "audit-admin", "password": PW})
    logs = client.get("/api/audit-logs?action=publish_timetable").json()
    assert [(log["result"], log["reason"]) for log in reversed(logs)] == [
        ("rejected", "publication_check_stale"),
        ("success", ""),
        ("rejected", "publication_already_submitted"),
    ]
    assert client.patch(f"/api/audit-logs/{logs[0]['id']}", json={}).status_code == 404
    assert client.delete(f"/api/audit-logs/{logs[0]['id']}").status_code == 404


def test_assignment_teacher_change_invalidates_publication_confirmation(env3):
    client, sid, tid, _ = env3
    assignment = _one_period_course(client, sid)
    _place(client, tid, assignment["id"], 1, 1)
    checked = client.post(f"/api/timetables/{tid}/publication-check").json()
    replacement = _teacher(client, sid, "李师")

    updated = client.patch(
        f"/api/assignments/{assignment['id']}",
        json={
            "class_id": assignment["scheduling_unit"]["classes"][0]["id"],
            "subject_id": assignment["subject"]["id"],
            "periods_per_week": assignment["periods_per_week"],
            "teachers": [{"teacher_id": replacement["id"], "is_lead": True}],
            "block_rules": [],
        },
    )
    assert updated.status_code == 200, updated.text

    stale = client.post(
        f"/api/timetables/{tid}/publish",
        json={"fingerprint": checked["fingerprint"]},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "publication_check_stale"


# ── 验收②:未排完 → 警告;强制可发布 ──
def test_publish_blocked_when_incomplete_then_forced(env3):
    client, sid, tid, _ = env3
    c = _class(client, sid, 3, "301")
    s = _subject(client, sid, "语文")
    t = _teacher(client, sid, "王师")
    a = _assign(client, sid, class_id=c["id"], subject_id=s["id"],
                teacher_ids=[t["id"]], periods=5)
    for wd in (1, 2):
        _place(client, tid, a["id"], wd, 1)  # 只排 2 节,尚缺 3 节

    check = client.post(f"/api/timetables/{tid}/publication-check")
    assert check.status_code == 200, check.text
    assert check.json()["passed"] is False
    assert check.json()["requires_force"] is True
    r = client.post(
        f"/api/timetables/{tid}/publish",
        json={"fingerprint": check.json()["fingerprint"]},
    )
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["completeness"]["remaining"] == 3
    assert detail["completeness"]["unplaced"][0]["remaining"] == 3

    # 确认后强制发布
    r = client.post(
        f"/api/timetables/{tid}/publish",
        json={"fingerprint": check.json()["fingerprint"], "force": True},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "published"


def test_publish_complete_without_force(env3):
    client, sid, tid, _ = env3
    a = _one_period_course(client, sid)
    _place(client, tid, a["id"], 1, 1)
    r = publish_checked_timetable(client, tid)
    assert r.status_code == 200 and r.json()["status"] == "published"


def test_admin_can_check_and_confirm_publication(env3):
    client, sid, tid, db = env3
    assignment = _one_period_course(client, sid)
    _place(client, tid, assignment["id"], 1, 1)
    make_user(db, "publishing-admin", PW, roles=[Role.admin])
    client.post("/api/auth/logout")
    client.post(
        "/api/auth/login",
        json={"username": "publishing-admin", "password": PW},
    )

    response = publish_checked_timetable(client, tid)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "published"


# ── 验收①:双草稿并存 / 发布 B 后 A 仍可编辑 ──
def test_duplicate_creates_independent_draft(env3):
    client, sid, tidA, _ = env3
    a = _one_period_course(client, sid)
    _place(client, tidA, a["id"], 1, 1)

    tidB = client.post(f"/api/timetables/{tidA}/duplicate", json={"name": "草稿B"}).json()["id"]
    assert tidB != tidA
    assert len(_entries(client, tidB)) == 1  # 单元格一并复制

    # 改 B 不影响 A
    eB = _entries(client, tidB)[0]
    client.patch(f"/api/timetables/{tidB}/entries/{eB['id']}", json={"weekday": 2, "period_no": 2})
    assert _entries(client, tidA)[0]["weekday"] == 1
    assert _entries(client, tidB)[0]["weekday"] == 2

    # 删 B 的单元格不影响 A
    client.delete(f"/api/timetables/{tidB}/entries/{eB['id']}")
    assert len(_entries(client, tidA)) == 1
    assert len(_entries(client, tidB)) == 0


def test_publish_b_leaves_a_editable(env3):
    """验收①:发布 B 后,查询页显示 B,A 仍为草稿可编辑。"""
    client, sid, tidA, _ = env3
    a = _one_period_course(client, sid)
    _place(client, tidA, a["id"], 1, 1)
    tidB = client.post(f"/api/timetables/{tidA}/duplicate", json={"name": "草稿B"}).json()["id"]

    assert publish_checked_timetable(client, tidB).status_code == 200

    lst = {t["id"]: t["status"] for t in client.get(f"/api/timetables?semester_id={sid}").json()}
    assert lst[tidB] == "published"
    assert lst[tidA] == "draft"

    # A 仍可编辑
    eA = _entries(client, tidA)[0]
    r = client.patch(f"/api/timetables/{tidA}/entries/{eA['id']}",
                     json={"weekday": 3, "period_no": 2})
    assert r.status_code == 200

    # 查询页显示 B
    pubtt = client.get(f"/api/published/timetable?semester_id={sid}").json()
    assert pubtt["id"] == tidB and pubtt["name"] == "草稿B"


def test_publishing_new_archives_previous(env3):
    client, sid, tidA, _ = env3
    a = _one_period_course(client, sid)
    _place(client, tidA, a["id"], 1, 1)
    tidB = client.post(f"/api/timetables/{tidA}/duplicate", json={"name": "草稿B"}).json()["id"]

    publish_checked_timetable(client, tidA)
    publish_checked_timetable(client, tidB)
    lst = {t["id"]: t["status"] for t in client.get(f"/api/timetables?semester_id={sid}").json()}
    assert lst[tidA] == "archived" and lst[tidB] == "published"
    # 同学期至多一份 published
    assert sum(1 for v in lst.values() if v == "published") == 1


# ── 已发布为快照,不可编辑 ─────────────
def test_published_timetable_is_read_only(env3):
    client, sid, tid, _ = env3
    a = _one_period_course(client, sid)
    _place(client, tid, a["id"], 1, 1)
    eid = _entries(client, tid)[0]["id"]
    publish_checked_timetable(client, tid)

    assert _place(client, tid, a["id"], 2, 1).status_code == 409
    assert client.patch(f"/api/timetables/{tid}/entries/{eid}",
                        json={"weekday": 2, "period_no": 2}).status_code == 409
    assert client.delete(f"/api/timetables/{tid}/entries/{eid}").status_code == 409
    assert client.post(f"/api/timetables/{tid}/entries/{eid}/lock?locked=true").status_code == 409
    # 再次发布也不行(已非草稿)
    assert client.post(f"/api/timetables/{tid}/publish").status_code == 409


def test_rename_timetable(env3):
    client, _sid, tid, _ = env3
    r = client.patch(f"/api/timetables/{tid}", json={"name": "重新命名"})
    assert r.status_code == 200 and r.json()["name"] == "重新命名"


# ── 全员查询 API 与教师权限(验收③后端面)──
def test_published_endpoints_readable_by_teacher(env3):
    client, sid, tid, db = env3
    a = _one_period_course(client, sid)
    _place(client, tid, a["id"], 1, 1)
    publish_checked_timetable(client, tid)

    # 绑定教师账号:王师 ↔ e2e teacher user
    teacher = client.get(f"/api/teachers?semester_id={sid}").json()[0]
    tuser = make_user(db, "t", PW, roles=[Role.teacher])
    teacher_model = db.get(Teacher, teacher["id"])
    assert teacher_model is not None
    teacher_model.user_id = tuser.id
    db.commit()

    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "t", "password": PW})

    # 教师可读已发布课表与学期
    sems = client.get("/api/published/semesters").json()
    assert [s["id"] for s in sems] == [sid]
    pubtt = client.get(f"/api/published/timetable?semester_id={sid}").json()
    assert pubtt["status"] == "published" and len(pubtt["entries"]) == 1
    assert pubtt["period_tables"] and pubtt["classes"]

    # my-teacher 解析出本人
    me = client.get(f"/api/published/my-teacher?semester_id={sid}").json()
    assert me["id"] == teacher["id"] and me["name"] == "王师"

    # 但不得动用排课管理员 API
    assert client.get(f"/api/timetables?semester_id={sid}").status_code == 403
    assert client.post(f"/api/timetables/{tid}/publish").status_code == 403


def test_published_timetable_none_when_no_published(env3):
    client, sid, _tid, _ = env3
    assert client.get(f"/api/published/timetable?semester_id={sid}").json() is None
    assert client.get("/api/published/semesters").json() == []


def test_my_teacher_null_when_unbound(env3):
    client, sid, _tid, _ = env3
    assert client.get(f"/api/published/my-teacher?semester_id={sid}").json() is None


# ── audit_log ─────────────────────────
def test_publish_writes_audit_log(env3):
    client, sid, tid, db = env3
    a = _one_period_course(client, sid)
    _place(client, tid, a["id"], 1, 1)
    publish_checked_timetable(client, tid)

    make_user(db, "admin1", PW, roles=[Role.admin])
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "admin1", "password": PW})

    logs = client.get("/api/audit-logs?action=publish_timetable").json()
    assert len(logs) == 1
    assert logs[0]["username"] == "s"
    assert logs[0]["actor_roles"] == ["scheduler"]
    assert logs[0]["target_id"] == tid
    assert logs[0]["semester_id"] == sid
    assert logs[0]["target_version"] == f"草稿A (#{tid})"
    assert logs[0]["result"] == "success"
    assert logs[0]["reason"] == ""
    assert "草稿A" in logs[0]["detail"]


def test_forced_publish_marked_in_audit(env3):
    client, sid, tid, db = env3
    c = _class(client, sid, 3, "301")
    s = _subject(client, sid, "语文")
    t = _teacher(client, sid, "王师")
    _assign(client, sid, class_id=c["id"], subject_id=s["id"], teacher_ids=[t["id"]], periods=5)
    publish_checked_timetable(client, tid, force=True)

    make_user(db, "admin1", PW, roles=[Role.admin])
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "admin1", "password": PW})
    logs = client.get("/api/audit-logs").json()
    assert "强制发布" in logs[0]["detail"]


def test_audit_logs_admin_only(env3):
    client, _sid, _tid, _ = env3  # 目前登录者为 scheduler
    assert client.get("/api/audit-logs").status_code == 403
