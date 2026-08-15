"""设置向导与数据摘要测试。对应 M1-4 验收标准。"""

import pytest

from app.models.user import Role
from tests.conftest import make_user

PW = "password123"


@pytest.fixture
def scheduler(env):
    client, db = env
    make_user(db, "s", PW, roles=[Role.scheduler])
    client.post("/api/auth/login", json={"username": "s", "password": PW})
    return client


def test_initial_state_is_step0_incomplete(scheduler):
    """全新系统:向导在第 0 步、未完成、无学期。"""
    r = scheduler.get("/api/wizard/state")
    assert r.status_code == 200
    body = r.json()
    assert body["current_step"] == 0
    assert body["completed"] is False
    assert body["has_semesters"] is False
    assert body["total_steps"] == 5
    assert body["route"] is None


def test_management_user_can_select_and_resume_formal_route(scheduler):
    """路线选择属于单校引导状态，刷新/重新登录后仍能恢复原步骤。"""
    route = scheduler.put("/api/onboarding/route", json={"route": "formal"})
    assert route.status_code == 200, route.text
    assert route.json()["route"] == "formal"

    scheduler.patch("/api/wizard/state", json={"current_step": 2})
    scheduler.post("/api/auth/logout")
    scheduler.post("/api/auth/login", json={"username": "s", "password": PW})

    state = scheduler.get("/api/wizard/state").json()
    route = scheduler.get("/api/onboarding/route").json()
    assert state["current_step"] == 2
    assert state["route"] == "formal"
    assert route["resume_step"] == 2
    assert route["can_reselect"] is True


def test_demo_route_requires_an_explicit_choice_and_stays_isolated(scheduler):
    """示例路线只能在明确选择后加载，且正式路线切换不会覆盖示例上下文。"""
    denied = scheduler.post("/api/demo-data")
    assert denied.status_code == 403

    selected = scheduler.put("/api/onboarding/route", json={"route": "demo"})
    assert selected.status_code == 200, selected.text
    loaded = scheduler.post("/api/demo-data")
    assert loaded.status_code == 201, loaded.text
    demo_id = loaded.json()["semester_id"]

    status = scheduler.get("/api/onboarding/route").json()
    assert status["route"] == "demo"
    assert status["has_demo_semester"] is True
    assert status["has_formal_semester"] is False

    switched = scheduler.put("/api/onboarding/route", json={"route": "formal"})
    assert switched.status_code == 200, switched.text
    state = scheduler.get("/api/wizard/state").json()
    assert state["route"] == "formal"
    assert state["completed"] is False
    assert state["current_step"] == 0

    formal = scheduler.post(
        "/api/semesters",
        json={
            "academic_year": 2098,
            "term": 1,
            "start_date": "2098-09-01",
            "end_date": "2099-01-31",
        },
    )
    assert formal.status_code == 201, formal.text
    context = scheduler.get("/api/semester-context").json()
    assert context["current_semester"]["id"] == formal.json()["id"]
    assert context["current_semester"]["is_demo"] is False
    assert scheduler.get(f"/api/semesters/{demo_id}").json()["is_demo"] is True


def test_route_cannot_switch_from_formal_data_to_demo(scheduler):
    formal = scheduler.post(
        "/api/semesters",
        json={"academic_year": 2097, "term": 1},
    )
    assert formal.status_code == 201, formal.text
    selected = scheduler.put("/api/onboarding/route", json={"route": "formal"})
    assert selected.status_code == 200, selected.text

    blocked = scheduler.put("/api/onboarding/route", json={"route": "demo"})
    assert blocked.status_code == 409
    assert "正式" in blocked.json()["detail"]


def test_progress_persists(scheduler):
    """验收②:更新步骤后再读,状态保留(模拟关浏览器后续作)。"""
    sem = scheduler.post("/api/semesters", json={"academic_year": 2026, "term": 1}).json()
    scheduler.patch("/api/wizard/state", json={"current_step": 3, "semester_id": sem["id"]})
    body = scheduler.get("/api/wizard/state").json()
    assert body["current_step"] == 3
    assert body["semester_id"] == sem["id"]
    assert body["has_semesters"] is True


def test_complete_and_reset(scheduler):
    scheduler.patch("/api/wizard/state", json={"completed": True, "current_step": 4})
    assert scheduler.get("/api/wizard/state").json()["completed"] is True
    # 重新启动向导
    r = scheduler.post("/api/wizard/reset")
    body = r.json()
    assert body["completed"] is False
    assert body["current_step"] == 0
    assert body["semester_id"] is None


def test_step_clamped_to_valid_range(scheduler):
    scheduler.patch("/api/wizard/state", json={"current_step": 99})
    assert scheduler.get("/api/wizard/state").json()["current_step"] == 4  # TOTAL_STEPS-1


def test_semester_summary_counts(scheduler):
    """验收①:摘要显示教师/班级等数量。"""
    # 用空白学期(不带模板)使计数可预期
    sem = scheduler.post("/api/semesters", json={"academic_year": 2026, "term": 1}).json()
    sid = sem["id"]
    scheduler.post(f"/api/subjects?semester_id={sid}", json={"name": "数学"})
    scheduler.post(f"/api/teachers?semester_id={sid}", json={"name": "王老师"})
    scheduler.post(f"/api/teachers?semester_id={sid}", json={"name": "李老师"})
    scheduler.post(
        f"/api/class-units?semester_id={sid}",
        json={"grade": 1, "name": "甲", "track": "junior_high"},
    )
    summary = scheduler.get(f"/api/semesters/{sid}/summary").json()
    assert summary == {"subjects": 1, "teachers": 2, "classes": 1, "rooms": 0}


def test_teacher_cannot_write_wizard(env):
    client, db = env
    make_user(db, "t", PW, roles=[Role.teacher])
    client.post("/api/auth/login", json={"username": "t", "password": PW})
    assert client.patch("/api/wizard/state", json={"current_step": 2}).status_code == 403
