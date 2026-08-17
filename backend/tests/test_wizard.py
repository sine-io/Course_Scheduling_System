"""设置向导与数据摘要测试。对应 M1-4 验收标准。"""

import pytest

from app.models.basedata import Subject
from app.models.semester import Semester
from app.models.user import Role
from tests.conftest import make_user

PW = "password123"


@pytest.fixture
def scheduler(env):
    client, db = env
    make_user(db, "s", PW, roles=[Role.scheduler])
    client.post("/api/auth/login", json={"username": "s", "password": PW})
    return client


def create_semester(client, *, with_dates: bool = True) -> dict:
    body = {"academic_year": 2026, "term": 1}
    if with_dates:
        body.update({"start_date": "2026-09-01", "end_date": "2027-01-20"})
    response = client.post("/api/semesters", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def add_minimum_setup(client, semester_id: int) -> None:
    assert client.post(
        f"/api/subjects?semester_id={semester_id}", json={"name": "数学"}
    ).status_code == 201
    assert client.post(
        f"/api/teachers?semester_id={semester_id}", json={"name": "王老师"}
    ).status_code == 201
    assert client.post(
        f"/api/class-units?semester_id={semester_id}",
        json={"grade": 7, "name": "七年级1班", "track": "junior_high"},
    ).status_code == 201
    draft = client.get(f"/api/semesters/{semester_id}/period-setup").json()
    response = client.put(
        f"/api/semesters/{semester_id}/period-setup",
        json={"fingerprint": draft["fingerprint"], "groups": draft["groups"]},
    )
    assert response.status_code == 200, response.text


def test_initial_state_is_step0_incomplete(scheduler):
    """全新系统:向导在第 0 步、未完成、无学期。"""
    r = scheduler.get("/api/wizard/state")
    assert r.status_code == 200
    body = r.json()
    assert body["current_step"] == 0
    assert body["resume_step"] == 0
    assert body["completed"] is False
    assert body["paused"] is False
    assert body["has_semesters"] is False
    assert body["total_steps"] == 4
    assert "route" not in body


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/demo-data"),
        ("post", "/api/demo-data"),
        ("get", "/api/onboarding/status"),
        ("get", "/api/onboarding/route"),
        ("put", "/api/onboarding/route"),
        ("post", "/api/wizard/reset"),
    ],
)
def test_removed_onboarding_endpoints_are_not_exposed(scheduler, method, path):
    assert getattr(scheduler, method)(path).status_code == 404


def test_progress_persists(scheduler):
    """验收②:更新步骤后再读,状态保留(模拟关浏览器后续作)。"""
    sem = create_semester(scheduler, with_dates=False)
    scheduler.patch(
        "/api/wizard/state",
        json={"current_step": 2, "semester_id": sem["id"], "paused": True},
    )
    scheduler.post("/api/auth/logout")
    scheduler.post("/api/auth/login", json={"username": "s", "password": PW})
    body = scheduler.get("/api/wizard/state").json()
    assert body["current_step"] == 2
    assert body["resume_step"] == 0
    assert body["semester_id"] == sem["id"]
    assert body["paused"] is True
    assert body["has_semesters"] is True


def test_setup_check_is_derived_from_real_data(scheduler):
    semester = create_semester(scheduler, with_dates=False)
    semester_id = semester["id"]

    response = scheduler.get(f"/api/semesters/{semester_id}/setup-check")

    assert response.status_code == 200
    check = response.json()
    assert check["can_complete"] is False
    assert check["first_incomplete_step"] == 0
    assert {item["code"] for item in check["blockers"]} >= {
        "semester_dates_missing",
        "subjects_missing",
        "teachers_missing",
        "classes_missing",
        "regular_period_missing",
        "period_default_missing",
    }
    assert check["summary"] == {"subjects": 0, "teachers": 0, "classes": 0, "rooms": 0}


def test_complete_requires_warning_acknowledgement_and_keeps_readiness_draft(scheduler):
    semester = create_semester(scheduler)
    semester_id = semester["id"]
    add_minimum_setup(scheduler, semester_id)
    check = scheduler.get(f"/api/semesters/{semester_id}/setup-check").json()
    assert check["can_complete"] is True
    assert check["first_incomplete_step"] == 3
    assert {item["code"] for item in check["warnings"]} == {
        "rooms_missing",
        "teacher_accounts_missing",
        "special_dates_missing",
        "bell_times_missing",
    }

    unacknowledged = scheduler.post(
        "/api/wizard/complete",
        json={"semester_id": semester_id, "acknowledge_warnings": False},
    )
    assert unacknowledged.status_code == 409
    assert unacknowledged.json()["detail"]["code"] == "wizard_warnings_unacknowledged"

    completed = scheduler.post(
        "/api/wizard/complete",
        json={"semester_id": semester_id, "acknowledge_warnings": True},
    )
    assert completed.status_code == 200
    assert completed.json()["completed"] is True
    assert completed.json()["semester_id"] == semester_id
    assert scheduler.get(f"/api/semesters/{semester_id}").json()["readiness"] == "draft"


def test_completion_cannot_bypass_the_check(scheduler):
    semester = create_semester(scheduler, with_dates=False)
    bypass = scheduler.patch("/api/wizard/state", json={"completed": True})
    assert bypass.status_code == 409
    assert bypass.json()["detail"]["code"] == "wizard_completion_requires_check"

    blocked = scheduler.post(
        "/api/wizard/complete",
        json={"semester_id": semester["id"], "acknowledge_warnings": True},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "wizard_setup_blocked"
    assert blocked.json()["detail"]["check"]["blockers"]


def test_completed_state_stays_historical_until_current_semester_is_reopened(scheduler, env):
    _, db = env
    semester = create_semester(scheduler)
    semester_id = semester["id"]
    add_minimum_setup(scheduler, semester_id)
    completed = scheduler.post(
        "/api/wizard/complete",
        json={"semester_id": semester_id, "acknowledge_warnings": True},
    )
    assert completed.status_code == 200

    subject = db.query(Subject).filter(Subject.semester_id == semester_id).one()
    db.delete(subject)
    db.commit()
    state = scheduler.get("/api/wizard/state").json()
    assert state["completed"] is True
    assert state["resume_step"] == 1

    semester_count = db.query(Semester).count()
    reopened = scheduler.post("/api/wizard/reopen")
    assert reopened.status_code == 200
    state = reopened.json()
    assert {key: state[key] for key in (
        "current_step", "resume_step", "completed", "paused", "semester_id"
    )} == {
        "current_step": 1,
        "resume_step": 1,
        "completed": False,
        "paused": False,
        "semester_id": semester_id,
    }
    assert db.query(Semester).count() == semester_count


def test_step_clamped_to_valid_range(scheduler):
    scheduler.patch("/api/wizard/state", json={"current_step": 99})
    assert scheduler.get("/api/wizard/state").json()["current_step"] == 3  # TOTAL_STEPS-1


def test_semester_summary_counts(scheduler):
    """验收①:摘要显示教师/班级等数量。"""
    # 用空白学期(不带模板)使计数可预期
    sem = create_semester(scheduler, with_dates=False)
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


def test_director_can_view_check_but_cannot_complete_or_reopen(env):
    client, db = env
    make_user(db, "s", PW, roles=[Role.scheduler])
    make_user(db, "d", PW, roles=[Role.director])
    client.post("/api/auth/login", json={"username": "s", "password": PW})
    semester = create_semester(client)
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "d", "password": PW})

    assert client.get(f"/api/semesters/{semester['id']}/setup-check").status_code == 200
    assert client.post(
        "/api/wizard/complete",
        json={"semester_id": semester["id"], "acknowledge_warnings": True},
    ).status_code == 403
    assert client.post("/api/wizard/reopen").status_code == 403
