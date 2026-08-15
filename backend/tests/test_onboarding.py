"""首次成功状态与 P0 待办的外部行为。"""

from app.models.user import Role
from tests.api_helpers import create_api_semester
from tests.conftest import make_user

PW = "password123"


def _login(client, db, username="scheduler", roles=(Role.scheduler,)):
    make_user(db, username, PW, roles=list(roles))
    response = client.post("/api/auth/login", json={"username": username, "password": PW})
    assert response.status_code == 200, response.text


def _setup_one_assignment(client, sid):
    class_unit = client.post(
        f"/api/class-units?semester_id={sid}",
        json={"grade": 7, "name": "701", "track": "junior_high"},
    ).json()
    subject = client.post(
        f"/api/subjects?semester_id={sid}", json={"name": "数学"}
    ).json()
    teacher = client.post(
        f"/api/teachers?semester_id={sid}",
        json={"name": "王老师", "base_periods": 10},
    ).json()
    assignment = client.post(
        "/api/assignments?semester_id=" + str(sid),
        json={
            "class_id": class_unit["id"],
            "subject_id": subject["id"],
            "periods_per_week": 1,
            "teachers": [{"teacher_id": teacher["id"]}],
            "block_rules": [],
        },
    ).json()
    return assignment


def test_empty_system_exposes_one_next_p0_action(env):
    client, db = env
    _login(client, db)

    response = client.get("/api/onboarding/status")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["first_success"] is False
    assert body["current_semester"] is None
    assert body["next_action"]["stage"] == "semester"
    assert body["next_action"]["href"] == "/wizard"
    assert body["p0_todos"][0]["key"] == "semester"
    assert {stage["status"] for stage in body["stages"]} <= {"complete", "blocked", "pending"}
    assert all(stage["complete"] == (stage["status"] == "complete") for stage in body["stages"])


def test_wizard_completion_does_not_end_first_success(env):
    client, db = env
    _login(client, db)
    semester = create_api_semester(
        client,
        academic_year=2061,
        with_periods=False,
        start_date="2061-09-01",
        end_date="2062-01-31",
    )
    client.patch("/api/wizard/state", json={"completed": True})

    body = client.get("/api/onboarding/status").json()

    assert body["wizard_completed"] is True
    assert body["first_success"] is False
    assert body["current_semester"]["id"] == semester["id"]
    assert body["next_action"]["stage"] == "periods"
    assert body["next_action"]["href"] == "/settings/semesters"
    periods = next(stage for stage in body["stages"] if stage["key"] == "periods")
    assert periods["complete"] is False
    assert "作息" in periods["blocking_reason"]


def test_demo_semester_is_not_formal_first_success_context(env):
    client, db = env
    _login(client, db, username="admin", roles=(Role.admin,))
    assert client.put("/api/onboarding/route", json={"route": "demo"}).status_code == 200

    demo = client.post("/api/demo-data")

    assert demo.status_code == 201, demo.text
    body = client.get("/api/onboarding/status").json()
    assert body["current_semester"]["is_demo"] is True
    assert body["first_success"] is False
    assert body["next_action"]["stage"] == "semester"
    assert "示例" in body["next_action"]["blocking_reason"]


def test_creating_formal_semester_after_demo_switches_current_context(env):
    client, db = env
    _login(client, db, username="admin", roles=(Role.admin,))
    assert client.put("/api/onboarding/route", json={"route": "demo"}).status_code == 200

    demo = client.post("/api/demo-data")
    assert demo.status_code == 201, demo.text

    formal = client.post(
        "/api/semesters",
        json={
            "academic_year": 2063,
            "term": 1,
            "start_date": "2063-09-01",
            "end_date": "2064-01-31",
        },
    )
    assert formal.status_code == 201, formal.text
    formal_body = formal.json()

    context = client.get("/api/semester-context").json()
    assert context["current_semester"]["id"] == formal_body["id"]
    onboarding = client.get("/api/onboarding/status").json()
    assert onboarding["current_semester"]["id"] == formal_body["id"]
    assert onboarding["current_semester"]["is_demo"] is False
    assert onboarding["first_success"] is False


def test_first_success_is_derived_from_published_complete_timetable(env):
    client, db = env
    _login(client, db)
    semester = create_api_semester(client, academic_year=2062, ready=True)
    sid = semester["id"]
    assignment = _setup_one_assignment(client, sid)
    timetable = client.post(
        f"/api/timetables?semester_id={sid}", json={"name": "首张草稿"}
    ).json()

    before = client.get("/api/onboarding/status").json()
    assert before["first_success"] is False
    assert before["next_action"]["stage"] == "integrity"

    placed = client.post(
        f"/api/timetables/{timetable['id']}/entries",
        json={"course_assignment_id": assignment["id"], "weekday": 1, "period_no": 2},
    )
    assert placed.status_code == 201, placed.text
    published = client.post(f"/api/timetables/{timetable['id']}/publish")
    assert published.status_code == 200, published.text

    success = client.get("/api/onboarding/status").json()
    assert success["first_success"] is True
    assert success["p0_todos"] == []
    assert success["next_action"] is None
    assert all(stage["status"] == "complete" for stage in success["stages"])

    # 归档的旧完整版本不能掩盖当前被强制发布的不完整版本。
    replacement = client.post(
        f"/api/timetables?semester_id={sid}", json={"name": "不完整替代版"}
    ).json()
    forced = client.post(f"/api/timetables/{replacement['id']}/publish?force=true")
    assert forced.status_code == 200, forced.text
    replaced = client.get("/api/onboarding/status").json()
    assert replaced["first_success"] is False
    integrity = next(stage for stage in replaced["stages"] if stage["key"] == "integrity")
    published_stage = next(stage for stage in replaced["stages"] if stage["key"] == "published")
    assert integrity["complete"] is False
    assert published_stage["complete"] is False

    # 新增真实教学任务后重新计算，不依赖向导完成标记或历史缓存。
    extra = client.post(
        f"/api/subjects?semester_id={sid}", json={"name": "语文"}
    ).json()
    teacher = client.post(
        f"/api/teachers?semester_id={sid}",
        json={"name": "李老师", "base_periods": 10},
    ).json()
    class_unit = client.post(
        f"/api/class-units?semester_id={sid}",
        json={"grade": 7, "name": "702", "track": "junior_high"},
    ).json()
    created = client.post(
        f"/api/assignments?semester_id={sid}",
        json={
            "class_id": class_unit["id"],
            "subject_id": extra["id"],
            "periods_per_week": 1,
            "teachers": [{"teacher_id": teacher["id"]}],
            "block_rules": [],
        },
    )
    assert created.status_code == 201, created.text

    changed = client.get("/api/onboarding/status").json()
    assert changed["first_success"] is False
    assert changed["next_action"]["stage"] == "integrity"
    assert changed["p0_todos"][0]["blocking_reason"]
