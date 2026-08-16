"""日常运行 RBAC 与教师本人数据范围的 HTTP 回归。

这些测试刻意从 HTTP 边界验证角色、对象归属和当前学期，而不是把前端隐藏入口
当成安全边界。核心排课数据的拒绝也在这里覆盖，确保日常角色不会意外升级。
"""

import pytest

from app.models.basedata import Teacher
from app.models.semester import Semester, SemesterStatus
from app.models.user import Role
from tests.api_helpers import create_api_semester
from tests.conftest import make_user
from tests.dates import SEM_END, SEM_START, WED, WED2
from tests.test_substitutions import _World

PW = "password123"


def _login(client, username: str) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": PW})
    assert response.status_code == 200, response.text


def _switch(client, db, username: str, roles: list[Role] | None = None) -> None:
    client.post("/api/auth/logout")
    if roles is not None:
        make_user(db, username, PW, roles=roles)
    _login(client, username)


def _bind_teacher(_client, db, teacher_id: int, name: str, username: str) -> None:
    user = make_user(db, username, PW, roles=[Role.teacher])
    teacher = db.get(Teacher, teacher_id)
    assert teacher is not None and teacher.name == name
    teacher.user_id = user.id
    db.commit()


@pytest.fixture
def daily_world(env):
    """当前学期中有一条已发布课表、两位教师和一条代课通知。"""
    client, db = env
    make_user(db, "scheduler", PW, roles=[Role.scheduler])
    _login(client, "scheduler")
    sid = create_api_semester(
        client,
        ready=True,
        start_date=SEM_START.isoformat(),
        end_date=SEM_END.isoformat(),
    )["id"]

    world = _World(client, db, sid)
    wang = world.teacher("王师", ["语文"])
    chen = world.teacher("陈师", ["语文"])
    world.place("王师", "语文", "701", 0)
    world.publish()
    affected = world.leave("王师")[0]
    assigned = client.put(
        f"/api/affected-periods/{affected['id']}/substitution",
        json={"type": "substitute", "handler_teacher_id": chen},
    )
    assert assigned.status_code == 200, assigned.text

    # 第二张假单用于验证教师本人可维护、他人不可访问。
    chen_leave = client.post(
        f"/api/leaves?semester_id={sid}",
        json={
            "teacher_id": chen,
            "leave_type": "personal",
            "start_date": WED2.isoformat(),
            "end_date": WED2.isoformat(),
        },
    )
    assert chen_leave.status_code == 201, chen_leave.text

    _bind_teacher(client, db, wang, "王师", "wang")
    _bind_teacher(client, db, chen, "陈师", "chen")
    leaves = client.get(f"/api/leaves?semester_id={sid}").json()
    wang_leave = next(row for row in leaves if row["teacher_id"] == wang)
    notification = next(
        row
        for row in client.get(f"/api/notifications?semester_id={sid}").json()
        if row["teacher_id"] == chen and row["type"] == "substitution_assigned"
    )
    return {
        "client": client,
        "db": db,
        "sid": sid,
        "world": world,
        "wang": wang,
        "chen": chen,
        "wang_leave": wang_leave["id"],
        "chen_leave": chen_leave.json()["id"],
        "affected": affected["id"],
        "notification": notification["id"],
        "class_id": world.classes["701"],
    }


def test_director_can_run_daily_operations_but_not_core_or_admin_actions(daily_world):
    client, db = daily_world["client"], daily_world["db"]
    sid = daily_world["sid"]
    _switch(client, db, "director", [Role.director])

    calendar = client.post(
        f"/api/semesters/{sid}/calendar-exceptions",
        json={"date": str(WED2), "kind": "no_instruction", "note": "主任维护"},
    )
    assert calendar.status_code == 201, calendar.text
    delegated_leave = client.post(
        f"/api/leaves?semester_id={sid}",
        json={
            "teacher_id": daily_world["wang"],
            "leave_type": "official",
            "start_date": str(WED2),
            "end_date": str(WED2),
        },
    )
    assert delegated_leave.status_code == 201, delegated_leave.text
    assert client.get(
        f"/api/affected-periods/{daily_world['affected']}/recommendations"
    ).status_code == 200
    handled = client.put(
        f"/api/affected-periods/{daily_world['affected']}/substitution",
        json={"type": "self_study"},
    )
    assert handled.status_code == 200, handled.text
    assert client.get(f"/api/notifications?semester_id={sid}").status_code == 200
    assert client.get(
        f"/api/daily-board?semester_id={sid}&on={WED.isoformat()}"
    ).status_code == 200
    assert client.get(
        f"/api/substitution-log?semester_id={sid}"
    ).status_code == 200
    assert client.get(
        f"/api/substitution-stats?semester_id={sid}&year={WED.year}&month={WED.month}"
    ).status_code == 200
    reminder = client.post(f"/api/notifications/{daily_world['notification']}/remind")
    assert reminder.status_code == 200, reminder.text

    assert client.post(
        f"/api/subjects?semester_id={sid}", json={"name": "主任不应修改"}
    ).status_code == 403
    assert client.post(
        f"/api/timetables?semester_id={sid}", json={"name": "主任草稿"}
    ).status_code == 403
    assert client.post(
        f"/api/timetables/{daily_world['world'].tt}/publish"
    ).status_code == 403
    assert client.get(f"/api/export/school.xlsx?semester_id={sid}").status_code == 403
    assert client.get("/api/settings/smtp").status_code == 403


def test_teacher_is_limited_to_own_daily_data_and_published_exports(daily_world):
    client, db = daily_world["client"], daily_world["db"]
    sid = daily_world["sid"]
    _switch(client, db, "chen")

    rows = client.get(f"/api/leaves?semester_id={sid}&teacher_id={daily_world['wang']}")
    assert rows.status_code == 200
    assert {row["teacher_id"] for row in rows.json()} == {daily_world["chen"]}
    assert client.get(f"/api/leaves/{daily_world['chen_leave']}").status_code == 200
    assert client.get(f"/api/leaves/{daily_world['wang_leave']}").status_code == 403
    assert client.post(f"/api/leaves/{daily_world['wang_leave']}/cancel").status_code == 403
    own_cancel = client.post(f"/api/leaves/{daily_world['chen_leave']}/cancel")
    assert own_cancel.status_code == 200, own_cancel.text

    mine = client.get(f"/api/notifications/mine?semester_id={sid}")
    assert mine.status_code == 200
    assert daily_world["notification"] in {item["id"] for item in mine.json()["items"]}
    assert client.post(
        f"/api/notifications/{daily_world['notification']}/acknowledge"
    ).status_code == 200
    _switch(client, db, "wang")
    assert client.post(
        f"/api/notifications/{daily_world['notification']}/acknowledge"
    ).status_code == 403

    _switch(client, db, "chen")
    assert client.get(
        f"/api/substitution-stats/mine?semester_id={sid}&year={WED.year}&month={WED.month}"
    ).status_code == 200
    for path in (
        f"/api/semesters/{sid}/calendar-exceptions",
        f"/api/notifications?semester_id={sid}",
        f"/api/daily-board?semester_id={sid}",
        f"/api/substitution-log?semester_id={sid}",
        f"/api/substitution-stats?semester_id={sid}&year={WED.year}&month={WED.month}",
        f"/api/substitution-stats/export?semester_id={sid}&year={WED.year}&month={WED.month}",
        f"/api/affected-periods/{daily_world['affected']}/recommendations",
        f"/api/subjects?semester_id={sid}",
        f"/api/timetables?semester_id={sid}",
    ):
        assert client.get(path).status_code == 403, path

    assert client.get(
        f"/api/published/timetable?semester_id={sid}"
    ).status_code == 200
    assert client.get(
        f"/api/export/timetable?semester_id={sid}&view=class&target_id={daily_world['class_id']}"
    ).status_code == 200
    assert client.get(f"/api/export/school.xlsx?semester_id={sid}").status_code == 403
    assert client.get(f"/api/export/batch.zip?semester_id={sid}").status_code == 403


def test_scheduler_teacher_union_keeps_daily_personal_and_operator_actions(daily_world):
    client, db = daily_world["client"], daily_world["db"]
    sid = daily_world["sid"]
    _switch(client, db, "scheduler")
    user = make_user(db, "scheduler-teacher", PW, roles=[Role.scheduler, Role.teacher])
    third = client.post(
        f"/api/teachers?semester_id={sid}", json={"name": "兼任教师", "base_periods": 20}
    )
    assert third.status_code == 201, third.text
    teacher = db.get(Teacher, third.json()["id"])
    assert teacher is not None
    teacher.user_id = user.id
    db.commit()
    client.post("/api/auth/logout")
    _login(client, "scheduler-teacher")

    assert client.post(
        f"/api/subjects?semester_id={sid}", json={"name": "兼任科目"}
    ).status_code == 201
    own_leave = client.post(
        f"/api/leaves?semester_id={sid}",
        json={"leave_type": "sick", "start_date": str(WED2), "end_date": str(WED2)},
    )
    assert own_leave.status_code == 201, own_leave.text
    assert own_leave.json()["teacher_id"] == third.json()["id"]
    assert client.get(f"/api/notifications?semester_id={sid}").status_code == 200
    assert client.get(f"/api/export/batch.zip?semester_id={sid}").status_code == 200


def test_unassigned_role_cannot_use_personal_daily_endpoints(daily_world):
    client, db = daily_world["client"], daily_world["db"]
    sid = daily_world["sid"]
    _switch(client, db, "unassigned", roles=[])

    for path in (
        "/api/leave-types",
        f"/api/notifications/mine?semester_id={sid}",
        f"/api/substitution-stats/mine?semester_id={sid}&year={WED.year}&month={WED.month}",
    ):
        assert client.get(path).status_code == 403, path


def test_daily_writes_reject_historical_and_archived_semesters(daily_world):
    client, db = daily_world["client"], daily_world["db"]
    sid = daily_world["sid"]
    second = create_api_semester(client, academic_year=2027, with_periods=False)["id"]
    revision = client.get("/api/semester-context").json()["revision"]
    switched = client.put(
        "/api/semester-context",
        json={"semester_id": second, "expected_revision": revision},
    )
    assert switched.status_code == 200, switched.text

    checks = [
        client.post(f"/api/leaves/{daily_world['wang_leave']}/cancel"),
        client.put(
            f"/api/affected-periods/{daily_world['affected']}/substitution",
            json={"type": "self_study"},
        ),
        client.post(f"/api/notifications/{daily_world['notification']}/remind"),
        client.post(
            f"/api/semesters/{sid}/calendar-exceptions",
            json={"date": str(WED2), "kind": "no_instruction"},
        ),
    ]
    assert all(response.status_code == 409 for response in checks)
    assert all(response.json()["detail"]["code"] == "semester_not_current" for response in checks)

    historical = db.get(Semester, sid)
    assert historical is not None
    historical.status = SemesterStatus.archived.value
    db.commit()
    archived = client.post(f"/api/leaves/{daily_world['wang_leave']}/cancel")
    assert archived.status_code == 409
    assert archived.json()["detail"]["code"] == "semester_read_only"
