"""核心排课工作流的角色边界测试。

这些测试只通过 HTTP seam 验证角色可见范围和动作权限，避免把前端隐藏入口当成安全边界。
"""

from app.models.basedata import Teacher
from app.models.user import Role
from tests.conftest import make_user

PW = "password123"


def _login(client, username: str, password: str = PW) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text


def _switch_user(client, db, username: str, roles: tuple[Role, ...]) -> None:
    client.post("/api/auth/logout")
    make_user(db, username, PW, roles=roles)
    _login(client, username)


def test_core_viewer_can_read_drafts_and_templates_but_teacher_cannot(env):
    client, db = env
    make_user(db, "director", PW, roles=[Role.director])
    _login(client, "director")
    semester = client.post(
        "/api/semesters",
        json={
            "academic_year": 2026,
            "term": 1,
            "start_date": "2026-09-01",
            "end_date": "2027-01-20",
        },
    ).json()
    semester_id = semester["id"]
    timetable = client.post(
        f"/api/timetables?semester_id={semester_id}", json={"name": "草稿A"}
    )
    assert timetable.status_code == 201, timetable.text

    assert client.get(f"/api/subjects?semester_id={semester_id}").status_code == 200
    assert client.get(f"/api/timetables?semester_id={semester_id}").status_code == 200
    # 教务主任承担完整排课职责，可以下载模板、导入并使用管理导出。
    assert client.get("/api/import/templates/subjects").status_code == 200
    assert client.post(
        f"/api/import/subjects?semester_id={semester_id}",
        files={"file": ("subjects.xlsx", b"not-an-xlsx", "application/octet-stream")},
    ).status_code != 403
    assert client.get(f"/api/export/school.xlsx?semester_id={semester_id}").status_code != 403

    _switch_user(client, db, "teacher", (Role.teacher,))
    assert client.get(f"/api/subjects?semester_id={semester_id}").status_code == 403
    assert client.get(f"/api/timetables?semester_id={semester_id}").status_code == 403
    assert client.get("/api/import/templates/subjects").status_code == 403
    assert client.post(
        f"/api/import/subjects?semester_id={semester_id}",
        files={"file": ("subjects.xlsx", b"not-an-xlsx", "application/octet-stream")},
    ).status_code == 403
    assert client.get(f"/api/export/school.xlsx?semester_id={semester_id}").status_code == 403


def test_removed_workspace_overview_endpoint_is_not_registered(env):
    client, _db = env

    response = client.get("/api/workspace-overview", params={"semester_id": 1})

    assert response.status_code == 404


def test_core_writes_and_publish_are_director_or_admin_only(env):
    client, db = env
    make_user(db, "director", PW, roles=[Role.director])
    _login(client, "director")
    semester_id = client.post(
        "/api/semesters",
        json={
            "academic_year": 2026,
            "term": 1,
            "start_date": "2026-09-01",
            "end_date": "2027-01-20",
        },
    ).json()["id"]

    assert client.post(
        f"/api/subjects?semester_id={semester_id}", json={"name": "主任科目"}
    ).status_code == 201
    assert client.post(
        f"/api/timetables?semester_id={semester_id}", json={"name": "主任草稿"}
    ).status_code == 201
    assert client.put(f"/api/solver/config?semester_id={semester_id}", json={}).status_code == 200
    assert client.post("/api/timetables/999999/publish").status_code == 404

    _switch_user(client, db, "teacher", (Role.teacher,))
    assert client.post(
        f"/api/subjects?semester_id={semester_id}", json={"name": "教师不应写入"}
    ).status_code == 403
    assert client.post("/api/timetables/999999/publish").status_code == 403

    _switch_user(client, db, "admin", (Role.admin,))
    assert client.post(
        f"/api/subjects?semester_id={semester_id}", json={"name": "管理员科目"}
    ).status_code == 201
    assert client.post(
        f"/api/timetables?semester_id={semester_id}", json={"name": "管理员草稿"}
    ).status_code == 201


def test_director_teacher_union_keeps_core_and_personal_roles(env):
    client, db = env
    user = make_user(db, "director-teacher", PW, roles=[Role.director, Role.teacher])
    _login(client, "director-teacher")
    semester_id = client.post(
        "/api/semesters",
        json={
            "academic_year": 2026,
            "term": 1,
            "start_date": "2026-09-01",
            "end_date": "2026-12-31",
        },
    ).json()["id"]

    assert client.post(
        f"/api/subjects?semester_id={semester_id}", json={"name": "兼任科目"}
    ).status_code == 201
    teacher = client.post(
        f"/api/teachers?semester_id={semester_id}",
        json={"name": "兼任教师", "base_periods": 20},
    )
    assert teacher.status_code == 201, teacher.text
    teacher_model = db.get(Teacher, teacher.json()["id"])
    assert teacher_model is not None
    teacher_model.user_id = user.id
    db.commit()
    leave = client.post(
        f"/api/leaves?semester_id={semester_id}",
        json={
            "leave_type": "sick",
            "start_date": "2026-09-02",
            "end_date": "2026-09-02",
            "reason": "本人事务",
        },
    )
    assert leave.status_code == 201, leave.text
    assert leave.json()["teacher_id"] == teacher.json()["id"]
    assert client.get("/api/published/semesters").status_code == 200


def test_director_can_manage_scheduling_settings_but_not_system_administration(env):
    client, db = env
    make_user(db, "director", PW, roles=[Role.director])
    _login(client, "director")

    assert client.get("/api/settings/scheduling").status_code == 200
    changed = client.put("/api/settings/scheduling", json={"max_overtime": 6})
    assert changed.status_code == 200
    assert changed.json() == {"max_overtime": 6}

    assert client.get("/api/settings/school").status_code == 403
    assert client.get("/api/settings/smtp").status_code == 403
    assert client.get("/api/accounts").status_code == 403
    assert client.get("/api/audit-logs").status_code == 403
    assert client.get("/api/backups").status_code == 403
