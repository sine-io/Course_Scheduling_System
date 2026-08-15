"""当前学期上下文的 HTTP 行为测试。"""

from app.api import solver as solver_api
from app.models.semester import SemesterStatus
from app.models.user import Role
from app.workers.progress import ControlAction, InMemoryProgressStore, JobState, JobStatus
from tests.api_helpers import create_api_semester
from tests.conftest import make_user

PW = "password123"


def login(client, db, roles=(Role.scheduler,), username="context-user"):
    make_user(db, username, PW, roles=list(roles))
    response = client.post("/api/auth/login", json={"username": username, "password": PW})
    assert response.status_code == 200


def context(client):
    response = client.get("/api/semester-context")
    assert response.status_code == 200
    return response.json()


def test_first_semester_becomes_current_and_context_is_visible_to_every_role(env):
    client, db = env
    login(client, db, username="scheduler")

    first = create_api_semester(client, academic_year=2026)
    second = create_api_semester(client, academic_year=2027, with_periods=False)

    assert first["is_current"] is True
    assert second["is_current"] is False
    listed = client.get("/api/semesters").json()
    assert {item["id"] for item in listed if item["is_current"]} == {first["id"]}
    assert context(client)["current_semester"]["id"] == first["id"]

    client.post("/api/auth/logout")
    login(client, db, roles=(Role.director,), username="director")
    director_context = context(client)
    assert director_context["current_semester"]["id"] == first["id"]
    assert director_context["can_switch"] is False

    client.post("/api/auth/logout")
    login(client, db, roles=(Role.teacher,), username="teacher")
    teacher_context = context(client)
    assert teacher_context["current_semester"]["id"] == first["id"]
    assert teacher_context["can_switch"] is False


def test_scheduler_switches_current_semester_and_stale_switch_is_rejected(env):
    client, db = env
    login(client, db)
    first = create_api_semester(client, academic_year=2026)
    second = create_api_semester(client, academic_year=2027, with_periods=False)
    revision = context(client)["revision"]

    switched = client.put(
        "/api/semester-context",
        json={"semester_id": second["id"], "expected_revision": revision},
    )
    assert switched.status_code == 200
    assert switched.json()["current_semester"]["id"] == second["id"]
    assert switched.json()["revision"] == revision + 1
    assert context(client)["current_semester"]["id"] == second["id"]

    stale = client.put(
        "/api/semester-context",
        json={"semester_id": first["id"], "expected_revision": revision},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "semester_context_changed"
    assert context(client)["current_semester"]["id"] == second["id"]


def test_formal_semester_locks_demo_context_switch(env):
    client, db = env
    login(client, db)
    assert client.put("/api/onboarding/route", json={"route": "demo"}).status_code == 200
    demo = client.post("/api/demo-data")
    assert demo.status_code == 201, demo.text
    formal = create_api_semester(client, academic_year=2090, with_periods=False)

    revision = context(client)["revision"]
    blocked = client.put(
        "/api/semester-context",
        json={"semester_id": demo.json()["semester_id"], "expected_revision": revision},
    )

    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "demo_context_locked"
    assert context(client)["current_semester"]["id"] == formal["id"]


def test_admin_can_switch_but_teacher_cannot(env):
    client, db = env
    login(client, db, username="scheduler")
    first = create_api_semester(client, academic_year=2026)
    second = create_api_semester(client, academic_year=2027, with_periods=False)
    revision = context(client)["revision"]

    client.post("/api/auth/logout")
    login(client, db, roles=(Role.teacher,), username="teacher")
    denied = client.put(
        "/api/semester-context",
        json={"semester_id": second["id"], "expected_revision": revision},
    )
    assert denied.status_code == 403
    assert context(client)["current_semester"]["id"] == first["id"]

    client.post("/api/auth/logout")
    login(client, db, roles=(Role.admin,), username="admin")
    switched = client.put(
        "/api/semester-context",
        json={"semester_id": second["id"], "expected_revision": revision},
    )
    assert switched.status_code == 200
    assert switched.json()["current_semester"]["id"] == second["id"]


def test_director_cannot_switch_and_archived_semester_is_read_only(env):
    client, db = env
    login(client, db, roles=(Role.scheduler,), username="scheduler")
    first = create_api_semester(client, academic_year=2026)
    second = create_api_semester(client, academic_year=2027, with_periods=False)
    revision = context(client)["revision"]
    assert client.patch(
        f"/api/semesters/{first['id']}", json={"status": SemesterStatus.archived.value}
    ).status_code == 200
    revision = context(client)["revision"]
    assert client.put(
        "/api/semester-context",
        json={"semester_id": second["id"], "expected_revision": revision},
    ).status_code == 200

    client.post("/api/auth/logout")
    login(client, db, roles=(Role.director,), username="director")
    denied = client.put(
        "/api/semester-context",
        json={"semester_id": second["id"], "expected_revision": revision + 1},
    )
    assert denied.status_code == 403

    client.post("/api/auth/logout")
    login(client, db, username="scheduler-again")
    response = client.post(f"/api/subjects?semester_id={first['id']}", json={"name": "历史科目"})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "semester_read_only"


def test_non_current_semester_writes_are_rejected_but_current_writes_work(env):
    client, db = env
    login(client, db)
    first = create_api_semester(client, academic_year=2026)
    second = create_api_semester(client, academic_year=2027, with_periods=False)
    revision = context(client)["revision"]
    assert client.put(
        "/api/semester-context",
        json={"semester_id": second["id"], "expected_revision": revision},
    ).status_code == 200

    current_write = client.post(
        f"/api/subjects?semester_id={second['id']}", json={"name": "当前科目"}
    )
    assert current_write.status_code == 201

    historical_write = client.post(
        f"/api/subjects?semester_id={first['id']}", json={"name": "旧链接科目"}
    )
    assert historical_write.status_code == 409
    assert historical_write.json()["detail"]["code"] == "semester_not_current"

    timetable_write = client.post(
        f"/api/timetables?semester_id={first['id']}", json={"name": "旧链接草稿"}
    )
    assert timetable_write.status_code == 409


def test_historical_calendar_import_solver_and_timetable_delete_are_read_only(env):
    client, db = env
    login(client, db)
    first = create_api_semester(client, academic_year=2026)
    first_timetable = client.post(
        f"/api/timetables?semester_id={first['id']}", json={"name": "历史草稿"}
    ).json()
    second = create_api_semester(client, academic_year=2027, with_periods=False)
    revision = context(client)["revision"]
    switched = client.put(
        "/api/semester-context",
        json={"semester_id": second["id"], "expected_revision": revision},
    )
    assert switched.status_code == 200, switched.text

    calendar = client.post(
        f"/api/semesters/{first['id']}/calendar-exceptions",
        json={"date": "2026-10-01", "kind": "no_instruction", "note": "历史校历"},
    )
    assert calendar.status_code == 409
    assert calendar.json()["detail"]["code"] == "semester_not_current"

    imported = client.post(
        f"/api/import/subjects?semester_id={first['id']}",
        files={"file": ("subjects.xlsx", b"not-an-xlsx", "application/octet-stream")},
    )
    assert imported.status_code == 409
    assert imported.json()["detail"]["code"] == "semester_not_current"

    solver = client.put(f"/api/solver/config?semester_id={first['id']}", json={})
    assert solver.status_code == 409
    assert solver.json()["detail"]["code"] == "semester_not_current"

    deleted = client.delete(f"/api/timetables/{first_timetable['id']}")
    assert deleted.status_code == 409
    assert deleted.json()["detail"]["code"] == "semester_not_current"


def test_historical_solver_stop_is_read_only_but_cancel_remains_available(env):
    client, db = env
    login(client, db)
    first = create_api_semester(client, academic_year=2026)
    timetable = client.post(
        f"/api/timetables?semester_id={first['id']}", json={"name": "历史排课草稿"}
    ).json()
    second = create_api_semester(client, academic_year=2027, with_periods=False)
    revision = context(client)["revision"]
    assert client.put(
        "/api/semester-context",
        json={"semester_id": second["id"], "expected_revision": revision},
    ).status_code == 200

    store = InMemoryProgressStore()
    client.app.dependency_overrides[solver_api.get_progress_store] = lambda: store
    store.create(JobState(
        job_id="historical-job",
        status=JobStatus.running.value,
        semester_id=first["id"],
        source_timetable_id=timetable["id"],
        source_name=timetable["name"],
        max_seconds=60,
    ))

    stopped = client.post("/api/solver/jobs/historical-job/stop")
    assert stopped.status_code == 409
    assert stopped.json()["detail"]["code"] == "semester_not_current"

    cancelled = client.post("/api/solver/jobs/historical-job/cancel")
    assert cancelled.status_code == 200
    assert store.requested("historical-job") == ControlAction.cancel


def test_historical_assignment_and_publish_mutations_are_read_only(env):
    client, db = env
    login(client, db)
    first = create_api_semester(client, academic_year=2026)
    subject = client.post(
        f"/api/subjects?semester_id={first['id']}", json={"name": "语文"}
    ).json()
    teacher = client.post(
        f"/api/teachers?semester_id={first['id']}",
        json={"name": "王老师", "base_periods": 5},
    ).json()
    class_unit = client.post(
        f"/api/class-units?semester_id={first['id']}",
        json={"grade": 1, "name": "一班", "track": "junior_high"},
    ).json()
    assignment_body = {
        "class_id": class_unit["id"],
        "subject_id": subject["id"],
        "periods_per_week": 5,
        "teachers": [{"teacher_id": teacher["id"]}],
    }
    assignment = client.post(
        f"/api/assignments?semester_id={first['id']}", json=assignment_body
    ).json()
    timetable = client.post(
        f"/api/timetables?semester_id={first['id']}", json={"name": "历史草稿"}
    ).json()

    second = create_api_semester(client, academic_year=2027, with_periods=False)
    revision = context(client)["revision"]
    assert client.put(
        "/api/semester-context",
        json={"semester_id": second["id"], "expected_revision": revision},
    ).status_code == 200

    responses = [
        client.patch(f"/api/assignments/{assignment['id']}", json=assignment_body),
        client.delete(f"/api/assignments/{assignment['id']}"),
        client.post(f"/api/timetables/{timetable['id']}/publish"),
    ]
    assert {response.status_code for response in responses} == {409}
    assert {
        response.json()["detail"]["code"] for response in responses
    } == {"semester_not_current"}


def test_historical_and_archived_semesters_can_be_copied_without_becoming_current(env):
    client, db = env
    login(client, db)
    first = create_api_semester(client, academic_year=2026)
    assert client.post(
        f"/api/subjects?semester_id={first['id']}", json={"name": "历史科目"}
    ).status_code == 201
    second = create_api_semester(client, academic_year=2027, with_periods=False)
    revision = context(client)["revision"]
    assert client.put(
        "/api/semester-context",
        json={"semester_id": second["id"], "expected_revision": revision},
    ).status_code == 200

    historical_copy = client.post(
        f"/api/semesters/{first['id']}/copy",
        json={"academic_year": 2028, "term": 1},
    )
    assert historical_copy.status_code == 201, historical_copy.text
    assert context(client)["current_semester"]["id"] == second["id"]
    copied_id = historical_copy.json()["id"]
    assert client.get(f"/api/subjects?semester_id={copied_id}").json()[0]["name"] == "历史科目"
    assert client.post(
        f"/api/subjects?semester_id={copied_id}", json={"name": "不可直接修改"}
    ).status_code == 409

    revision = context(client)["revision"]
    assert client.put(
        "/api/semester-context",
        json={"semester_id": first["id"], "expected_revision": revision},
    ).status_code == 200
    assert client.patch(
        f"/api/semesters/{first['id']}", json={"status": SemesterStatus.archived.value}
    ).status_code == 200
    revision = context(client)["revision"]
    assert client.put(
        "/api/semester-context",
        json={"semester_id": second["id"], "expected_revision": revision},
    ).status_code == 200

    archived_copy = client.post(
        f"/api/semesters/{first['id']}/copy",
        json={"academic_year": 2029, "term": 1},
    )
    assert archived_copy.status_code == 201, archived_copy.text
    assert context(client)["current_semester"]["id"] == second["id"]
