"""Issue #33：账号与固定角色变更的管理员确认和审计边界。"""

import io

import pytest
from openpyxl import Workbook

from app.api.imports import XLSX_MIME
from app.models.basedata import Teacher
from app.models.user import Role, User
from tests.conftest import make_user

PW = "password123"


def _login(client, username: str, password: str = PW) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text


def _confirmation(operation_id: str, target: str) -> dict[str, object]:
    return {
        "operation_id": operation_id,
        "confirmed": True,
        "target": target,
    }


def _create_payload(operation_id: str, *, username: str = "new-teacher") -> dict:
    return {
        "username": username,
        "display_name": "新教师",
        "temporary_password": "temporary123",
        "roles": ["teacher"],
        "confirmation": _confirmation(operation_id, f"account:{username}"),
    }


def _teacher_xlsx(username: str) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for _ in range(3):
        sheet.append(["表头"] * 11)
    sheet.append(["王老师", "1234", "", 18, "", "", "否", username, "", "", ""])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_non_admin_account_creation_is_rejected_and_audited(env):
    client, db = env
    make_user(db, "scheduler", PW, roles=[Role.scheduler])
    make_user(db, "audit-admin", PW, roles=[Role.admin])
    _login(client, "scheduler")

    denied = client.post(
        "/api/accounts",
        json=_create_payload("10000000-0000-4000-8000-000000000001"),
    )

    assert denied.status_code == 403
    assert db.query(User).filter(User.username == "new-teacher").one_or_none() is None
    client.post("/api/auth/logout")
    _login(client, "audit-admin")
    logs = client.get("/api/audit-logs?action=create_account").json()
    assert len(logs) == 1
    assert logs[0]["username"] == "scheduler"
    assert logs[0]["actor_roles"] == ["scheduler"]
    assert logs[0]["target_version"] == "new-teacher"
    assert logs[0]["result"] == "rejected"
    assert logs[0]["reason"] == "high_risk_permission_denied"


def test_admin_account_creation_requires_confirmation_and_is_idempotent(env):
    client, db = env
    make_user(db, "admin", PW, roles=[Role.admin])
    _login(client, "admin")
    payload = _create_payload("10000000-0000-4000-8000-000000000002")

    missing = client.post("/api/accounts", json={**payload, "confirmation": None})
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "high_risk_confirmation_required"

    created = client.post("/api/accounts", json=payload)
    assert created.status_code == 201, created.text
    account = created.json()
    assert account["username"] == "new-teacher"
    assert account["display_name"] == "新教师"
    assert account["roles"] == ["teacher"]
    assert account["is_active"] is True
    assert account["must_change_password"] is True

    repeated = client.post("/api/accounts", json=payload)
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["code"] == "high_risk_duplicate_operation"
    assert db.query(User).filter(User.username == "new-teacher").count() == 1

    listed = client.get("/api/accounts").json()
    assert [item["username"] for item in listed] == ["admin", "new-teacher"]


def test_admin_can_change_roles_and_deactivate_an_account_with_exact_target(env):
    client, db = env
    make_user(db, "admin", PW, roles=[Role.admin])
    target = make_user(db, "operator", PW, roles=[Role.scheduler])
    _login(client, "admin")
    body = {
        "display_name": "兼任教师",
        "roles": ["scheduler", "teacher"],
        "is_active": False,
        "confirmation": _confirmation(
            "10000000-0000-4000-8000-000000000003",
            f"account:{target.id}",
        ),
    }

    changed = client.patch(f"/api/accounts/{target.id}", json=body)

    assert changed.status_code == 200, changed.text
    assert changed.json()["display_name"] == "兼任教师"
    assert changed.json()["roles"] == ["scheduler", "teacher"]
    assert changed.json()["is_active"] is False
    logs = client.get("/api/audit-logs?action=update_account").json()
    assert len(logs) == 1
    assert logs[0]["target_id"] == target.id
    assert logs[0]["target_version"] == "operator"
    assert logs[0]["result"] == "success"
    assert "scheduler" in logs[0]["detail"]
    assert "teacher" in logs[0]["detail"]


def test_account_change_rejects_wrong_target_and_protects_current_admin(env):
    client, db = env
    admin = make_user(db, "admin", PW, roles=[Role.admin])
    _login(client, "admin")

    wrong = client.patch(
        f"/api/accounts/{admin.id}",
        json={
            "roles": ["teacher"],
            "confirmation": _confirmation(
                "10000000-0000-4000-8000-000000000004",
                "account:99999",
            ),
        },
    )
    assert wrong.status_code == 409
    assert wrong.json()["detail"]["code"] == "high_risk_target_mismatch"

    self_demotion = client.patch(
        f"/api/accounts/{admin.id}",
        json={
            "roles": ["teacher"],
            "confirmation": _confirmation(
                "10000000-0000-4000-8000-000000000005",
                f"account:{admin.id}",
            ),
        },
    )
    assert self_demotion.status_code == 409
    assert self_demotion.json()["detail"]["code"] == "current_admin_protected"
    db.refresh(admin)
    assert admin.role_names == {Role.admin.value}

    logs = client.get("/api/audit-logs?action=update_account").json()
    assert [(log["result"], log["reason"]) for log in reversed(logs)] == [
        ("rejected", "high_risk_target_mismatch"),
        ("rejected", "current_admin_protected"),
    ]


def test_duplicate_username_is_zero_write_and_audited(env):
    client, db = env
    make_user(db, "admin", PW, roles=[Role.admin])
    make_user(db, "existing", PW, roles=[Role.teacher])
    _login(client, "admin")

    duplicate = client.post(
        "/api/accounts",
        json=_create_payload(
            "10000000-0000-4000-8000-000000000006",
            username="existing",
        ),
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "account_username_exists"
    assert db.query(User).filter(User.username == "existing").count() == 1
    log = client.get("/api/audit-logs?action=create_account").json()[0]
    assert log["result"] == "rejected"
    assert log["reason"] == "account_username_exists"


@pytest.mark.parametrize(
    ("username", "role"),
    [
        ("scheduler", Role.scheduler),
        ("director", Role.director),
        ("teacher-user", Role.teacher),
    ],
)
def test_non_admin_cannot_bind_a_login_account_to_teacher(env, username, role):
    client, db = env
    account = make_user(db, "teacher-login", PW, roles=[Role.teacher])
    make_user(db, "audit-admin", PW, roles=[Role.admin])
    make_user(db, username, PW, roles=[role])
    _login(client, "audit-admin")
    semester = client.post(
        "/api/semesters",
        json={"academic_year": 2026, "term": 1},
    ).json()
    client.post("/api/auth/logout")
    _login(client, username)

    denied = client.post(
        f"/api/teachers?semester_id={semester['id']}",
        json={
            "name": "王老师",
            "user_id": account.id,
            "account_confirmation": _confirmation(
                "10000000-0000-4000-8000-000000000007",
                f"teacher:{semester['id']}:王老师:account:{account.id}",
            ),
        },
    )

    assert denied.status_code == 403
    assert db.query(Teacher).filter(Teacher.semester_id == semester["id"]).count() == 0
    client.post("/api/auth/logout")
    _login(client, "audit-admin")
    log = client.get("/api/audit-logs?action=bind_teacher_account").json()[0]
    assert log["username"] == username
    assert log["result"] == "rejected"
    assert log["reason"] == "high_risk_permission_denied"


def test_scheduler_cannot_create_accounts_through_teacher_import(env):
    client, db = env
    make_user(db, "scheduler", PW, roles=[Role.scheduler])
    make_user(db, "audit-admin", PW, roles=[Role.admin])
    _login(client, "scheduler")
    semester = client.post(
        "/api/semesters",
        json={"academic_year": 2026, "term": 1},
    ).json()
    operation_id = "10000000-0000-4000-8000-000000000008"

    denied = client.post(
        f"/api/import/teachers?semester_id={semester['id']}&create_accounts=true",
        data={
            "operation_id": operation_id,
            "confirmed": "true",
            "target": f"semester:{semester['id']}:teacher-accounts",
        },
        files={"file": ("teachers.xlsx", _teacher_xlsx("imported-teacher"), XLSX_MIME)},
    )

    assert denied.status_code == 403
    assert db.query(User).filter(User.username == "imported-teacher").one_or_none() is None
    assert db.query(Teacher).filter(Teacher.semester_id == semester["id"]).count() == 0
    client.post("/api/auth/logout")
    _login(client, "audit-admin")
    log = client.get("/api/audit-logs?action=bulk_create_accounts").json()[0]
    assert log["username"] == "scheduler"
    assert log["semester_id"] == semester["id"]
    assert log["result"] == "rejected"
    assert log["reason"] == "high_risk_permission_denied"


def test_bulk_account_import_rolls_back_when_final_audit_cannot_commit(
    env, monkeypatch
):
    from app.api import imports as imports_api

    client, db = env
    make_user(db, "admin", PW, roles=[Role.admin])
    _login(client, "admin")
    semester = client.post(
        "/api/semesters",
        json={"academic_year": 2026, "term": 1},
    ).json()

    def fail_finish(session, *_args, **_kwargs):
        session.rollback()
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(imports_api.high_risk, "finish", fail_finish)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        client.post(
            f"/api/import/teachers?semester_id={semester['id']}&create_accounts=true",
            data={
                "operation_id": "10000000-0000-4000-8000-000000000009",
                "confirmed": "true",
                "target": f"semester:{semester['id']}:teacher-accounts",
            },
            files={
                "file": (
                    "teachers.xlsx",
                    _teacher_xlsx("rollback-teacher"),
                    XLSX_MIME,
                )
            },
        )

    assert db.query(User).filter(User.username == "rollback-teacher").one_or_none() is None
    assert db.query(Teacher).filter(Teacher.semester_id == semester["id"]).count() == 0
