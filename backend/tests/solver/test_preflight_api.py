"""M3-1:pre-flight 检查报告 API(GET /api/solver/preflight)。"""

from app.models.user import Role
from tests.api_helpers import create_api_semester
from tests.conftest import make_user

PW = "password123"


def _login(client, db, username="s", roles=(Role.scheduler,)):
    make_user(db, username, PW, roles=list(roles))
    client.post("/api/auth/login", json={"username": username, "password": PW})


def _setup(client, sid, *, periods, base_periods=20):
    c = client.post(
        f"/api/class-units?semester_id={sid}",
        json={"grade": 3, "name": "301", "track": "junior_high"},
    ).json()
    s = client.post(f"/api/subjects?semester_id={sid}", json={"name": "语文"}).json()
    t = client.post(
        f"/api/teachers?semester_id={sid}", json={"name": "王师", "base_periods": base_periods}
    ).json()
    client.post(f"/api/assignments?semester_id={sid}", json={
        "class_id": c["id"], "subject_id": s["id"], "periods_per_week": periods,
        "teachers": [{"teacher_id": t["id"]}], "block_rules": [],
    })
    return c, s, t


def test_preflight_ok(env):
    client, db = env
    _login(client, db)
    sid = create_api_semester(client)["id"]
    _setup(client, sid, periods=20)

    r = client.get(f"/api/solver/preflight?semester_id={sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["error_count"] == 0
    assert body["class_count"] == 1 and body["teacher_count"] == 1
    assert body["assignment_count"] == 1 and body["total_periods"] == 20
    assert body["semester_label"] == "2026-2027学年第一学期"


def test_preflight_reports_class_overload(env):
    client, db = env
    _login(client, db)
    sid = create_api_semester(client)["id"]
    # base_periods=0 表示学校尚未维护基准课时，避免超课时上限在建教学任务时提前拦截。
    _setup(client, sid, periods=40, base_periods=0)  # 40 > 35 可排节次

    body = client.get(f"/api/solver/preflight?semester_id={sid}").json()
    assert body["ok"] is False
    codes = {i["code"] for i in body["issues"]}
    assert "class_overload" in codes
    assert "teacher_overload" in codes  # 40 节 > 35 格
    assert "teacher_over_hours" in codes
    # error 排在 warning 之前
    assert body["issues"][0]["level"] == "error"
    assert body["warning_count"] >= 1

    overload = next(i for i in body["issues"] if i["code"] == "teacher_overload")
    assert overload["detail"] == {"assigned": 40, "available": 35, "unavailable": 0}


def test_preflight_unknown_semester_404(env):
    client, db = env
    _login(client, db)
    assert client.get("/api/solver/preflight?semester_id=9999").status_code == 404


def test_preflight_requires_scheduler(env):
    client, db = env
    _login(client, db, username="t", roles=(Role.teacher,))
    sid = client.post(
        "/api/semesters", json={"academic_year": 2026, "term": 1}
    ).status_code
    assert sid == 403  # teacher 连建学期都不行
    assert client.get("/api/solver/preflight?semester_id=1").status_code == 403
