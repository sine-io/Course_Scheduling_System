"""管理员破坏性删除的确认、幂等、只读边界与审计测试。"""

from uuid import UUID, uuid4

from app.models.audit import AuditLog
from app.models.user import Role
from tests.conftest import make_user

PW = "password123"


def _login(client, username: str) -> None:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": PW}
    )
    assert response.status_code == 200


def _confirmation(target: str, operation_id: UUID | None = None) -> dict:
    return {
        "operation_id": str(operation_id or uuid4()),
        "confirmed": True,
        "target": target,
    }


def _delete(client, path: str, target: str, operation_id: UUID | None = None):
    return client.request(
        "DELETE", path, json=_confirmation(target, operation_id=operation_id)
    )


def _subject_exists(client, semester_id: int, subject_id: int) -> bool:
    subjects = client.get(f"/api/subjects?semester_id={semester_id}").json()
    return any(item["id"] == subject_id for item in subjects)


def _build_delete_targets(client) -> tuple[int, list[tuple[str, str, str]]]:
    semester = client.post(
        "/api/semesters", json={"academic_year": 2026, "term": 1}
    ).json()
    sid = semester["id"]
    table = client.post(
        f"/api/semesters/{sid}/period-tables", json={"name": "删除测试作息"}
    ).json()
    subject = client.post(
        f"/api/subjects?semester_id={sid}", json={"name": "删除测试科目"}
    ).json()
    teacher = client.post(
        f"/api/teachers?semester_id={sid}", json={"name": "删除测试教师"}
    ).json()
    room = client.post(
        f"/api/rooms?semester_id={sid}", json={"name": "删除测试教室"}
    ).json()
    classes = [
        client.post(
            f"/api/class-units?semester_id={sid}",
            json={"grade": 1, "name": name, "track": "junior_high"},
        ).json()
        for name in ("删除甲班", "删除乙班")
    ]
    group = client.post(
        f"/api/scheduling-units?semester_id={sid}",
        json={"name": "删除测试走班", "class_ids": [item["id"] for item in classes]},
    ).json()
    assignment = client.post(
        f"/api/assignments?semester_id={sid}",
        json={
            "scheduling_unit_id": group["id"],
            "subject_id": subject["id"],
            "periods_per_week": 1,
            "teachers": [{"teacher_id": teacher["id"]}],
        },
    ).json()
    timetable = client.post(
        f"/api/timetables?semester_id={sid}", json={"name": "删除测试课表"}
    ).json()

    # 顺序同时也是成功删除时的依赖解除顺序。
    targets = [
        (
            f"/api/timetables/{timetable['id']}",
            f"timetable:{timetable['id']}",
            "delete_timetable",
        ),
        (
            f"/api/assignments/{assignment['id']}",
            f"assignment:{assignment['id']}",
            "delete_assignment",
        ),
        (
            f"/api/scheduling-units/{group['id']}",
            f"scheduling-unit:{group['id']}",
            "delete_scheduling_unit",
        ),
        (
            f"/api/class-units/{classes[0]['id']}",
            f"class-unit:{classes[0]['id']}",
            "delete_class_unit",
        ),
        (
            f"/api/class-units/{classes[1]['id']}",
            f"class-unit:{classes[1]['id']}",
            "delete_class_unit",
        ),
        (
            f"/api/rooms/{room['id']}",
            f"room:{room['id']}",
            "delete_room",
        ),
        (
            f"/api/teachers/{teacher['id']}",
            f"teacher:{teacher['id']}",
            "delete_teacher",
        ),
        (
            f"/api/subjects/{subject['id']}",
            f"subject:{subject['id']}",
            "delete_subject",
        ),
        (
            f"/api/period-tables/{table['id']}",
            f"period-table:{table['id']}",
            "delete_period_table",
        ),
        (
            f"/api/semesters/{sid}",
            f"semester:{sid}",
            "delete_semester",
        ),
    ]
    return sid, targets


def test_all_destructive_deletes_are_admin_only_confirmed_and_audited(env):
    client, db = env
    make_user(db, "admin", PW, roles=[Role.admin])
    make_user(db, "scheduler", PW, roles=[Role.scheduler])
    _login(client, "admin")
    _sid, targets = _build_delete_targets(client)

    _login(client, "scheduler")
    for path, target, _action in targets:
        denied = _delete(client, path, target)
        assert denied.status_code == 403, (path, denied.text)
        assert denied.json()["detail"]["code"] == "high_risk_permission_denied"

    rejected = db.query(AuditLog).filter(AuditLog.result == "rejected").all()
    assert [item.action for item in rejected] == [item[2] for item in targets]
    assert all(item.username == "scheduler" for item in rejected)
    assert all(item.actor_roles == [Role.scheduler.value] for item in rejected)

    _login(client, "admin")
    for path, target, _action in targets:
        deleted = _delete(client, path, target)
        assert deleted.status_code == 204, (path, deleted.text)

    succeeded = db.query(AuditLog).filter(AuditLog.result == "success").all()
    assert [item.action for item in succeeded] == [item[2] for item in targets]
    assert all(item.username == "admin" for item in succeeded)
    assert all(item.created_at is not None for item in succeeded)


def test_delete_requires_exact_confirmation_and_reused_operation_is_zero_write(env):
    client, db = env
    make_user(db, "admin", PW, roles=[Role.admin])
    _login(client, "admin")
    semester = client.post(
        "/api/semesters", json={"academic_year": 2026, "term": 1}
    ).json()
    sid = semester["id"]
    first = client.post(
        f"/api/subjects?semester_id={sid}", json={"name": "科目甲"}
    ).json()
    second = client.post(
        f"/api/subjects?semester_id={sid}", json={"name": "科目乙"}
    ).json()

    missing = client.request("DELETE", f"/api/subjects/{first['id']}")
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "high_risk_confirmation_required"
    mismatch = _delete(client, f"/api/subjects/{first['id']}", "subject:wrong")
    assert mismatch.status_code == 409
    assert mismatch.json()["detail"]["code"] == "high_risk_target_mismatch"

    operation_id = uuid4()
    assert (
        _delete(
            client,
            f"/api/subjects/{first['id']}",
            f"subject:{first['id']}",
            operation_id,
        ).status_code
        == 204
    )
    duplicate = _delete(
        client,
        f"/api/subjects/{second['id']}",
        f"subject:{second['id']}",
        operation_id,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "high_risk_duplicate_operation"
    assert _subject_exists(client, sid, second["id"])


def test_historical_archived_and_referenced_delete_fail_without_partial_data(env):
    client, db = env
    make_user(db, "admin", PW, roles=[Role.admin])
    _login(client, "admin")
    first = client.post(
        "/api/semesters", json={"academic_year": 2026, "term": 1}
    ).json()
    sid = first["id"]
    subject = client.post(
        f"/api/subjects?semester_id={sid}", json={"name": "受保护科目"}
    ).json()
    client.post(
        f"/api/teachers?semester_id={sid}",
        json={"name": "引用教师", "subject_ids": [subject["id"]]},
    )

    referenced = _delete(
        client, f"/api/subjects/{subject['id']}", f"subject:{subject['id']}"
    )
    assert referenced.status_code == 409
    assert _subject_exists(client, sid, subject["id"])

    second = client.post(
        "/api/semesters", json={"academic_year": 2027, "term": 1}
    ).json()
    context = client.get("/api/semester-context").json()
    assert client.put(
        "/api/semester-context",
        json={
            "semester_id": second["id"],
            "expected_revision": context["revision"],
        },
    ).status_code == 200
    historical = _delete(
        client, f"/api/subjects/{subject['id']}", f"subject:{subject['id']}"
    )
    assert historical.status_code == 409
    assert historical.json()["detail"]["code"] == "semester_not_current"

    context = client.get("/api/semester-context").json()
    assert client.put(
        "/api/semester-context",
        json={"semester_id": sid, "expected_revision": context["revision"]},
    ).status_code == 200
    assert client.patch(
        f"/api/semesters/{sid}", json={"status": "archived"}
    ).status_code == 200
    archived = _delete(
        client, f"/api/subjects/{subject['id']}", f"subject:{subject['id']}"
    )
    assert archived.status_code == 409
    assert archived.json()["detail"]["code"] == "semester_read_only"
    assert _subject_exists(client, sid, subject["id"])

    results = [item.result for item in db.query(AuditLog).order_by(AuditLog.id)]
    assert results == ["rejected", "rejected", "rejected"]
