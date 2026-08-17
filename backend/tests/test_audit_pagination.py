from datetime import UTC, datetime, timedelta

from app.models.audit import AuditLog
from app.models.user import Role
from app.services.users import create_user

PW = "password123"


def _login_admin(client, db) -> None:
    create_user(
        db,
        username="audit-page-admin",
        password=PW,
        roles=[Role.admin],
        must_change_password=False,
    )
    db.commit()
    response = client.post(
        "/api/auth/login",
        json={"username": "audit-page-admin", "password": PW},
    )
    assert response.status_code == 200


def _add_log(db, index: int, *, created_at: datetime, **overrides) -> AuditLog:
    values = {
        "username": f"operator-{index}",
        "actor_roles": ["scheduler"],
        "action": "publish_timetable",
        "target_type": "timetable",
        "target_id": index,
        "target_version": f"draft-{index}",
        "result": "success",
        "reason": "",
        "detail": f"record {index}",
        "created_at": created_at,
    }
    values.update(overrides)
    row = AuditLog(**values)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_audit_logs_return_exact_page_and_total(env):
    client, db = env
    _login_admin(client, db)
    base = datetime(2042, 8, 1, tzinfo=UTC)
    rows = [_add_log(db, i, created_at=base + timedelta(minutes=i)) for i in range(25)]

    first = client.get("/api/audit-logs").json()
    assert first["total"] == 25
    assert first["page"] == 1
    assert first["page_size"] == 20
    assert [item["id"] for item in first["items"]] == [row.id for row in reversed(rows[5:])]

    second = client.get("/api/audit-logs?page=2&page_size=20").json()
    assert second["total"] == 25
    assert [item["id"] for item in second["items"]] == [row.id for row in reversed(rows[:5])]


def test_audit_logs_use_id_as_stable_sort_tiebreaker(env):
    client, db = env
    _login_admin(client, db)
    timestamp = datetime(2042, 8, 1, tzinfo=UTC)
    rows = [_add_log(db, i, created_at=timestamp) for i in range(3)]

    body = client.get("/api/audit-logs?page_size=2").json()

    assert [item["id"] for item in body["items"]] == [rows[2].id, rows[1].id]


def test_audit_search_matches_all_tokens_across_visible_labels_and_values(env):
    client, db = env
    _login_admin(client, db)
    timestamp = datetime(2042, 8, 1, tzinfo=UTC)
    wanted = _add_log(
        db,
        1,
        created_at=timestamp,
        username="alice",
        actor_roles=["scheduler"],
        action="delete_subject",
        target_type="subject",
        target_id=23,
        target_version="",
        result="rejected",
        reason="权限不足",
        detail="删除请求被拦截",
    )
    _add_log(db, 2, created_at=timestamp, username="bob", detail="100 percent complete")
    percent = _add_log(db, 3, created_at=timestamp, username="carol", detail="进度 100%")

    by_labels = client.get(
        "/api/audit-logs",
        params={"q": "alice 排课管理员 删除科目 科目 23 已拒绝"},
    ).json()
    assert [item["id"] for item in by_labels["items"]] == [wanted.id]

    by_words = client.get("/api/audit-logs", params={"q": "权限 不足"}).json()
    assert [item["id"] for item in by_words["items"]] == [wanted.id]

    literal_wildcard = client.get("/api/audit-logs", params={"q": "%"}).json()
    assert [item["id"] for item in literal_wildcard["items"]] == [percent.id]


def test_audit_action_filter_combines_with_search_before_pagination(env):
    client, db = env
    _login_admin(client, db)
    timestamp = datetime(2042, 8, 1, tzinfo=UTC)
    wanted = _add_log(
        db,
        1,
        created_at=timestamp,
        username="alice",
        action="delete_subject",
    )
    _add_log(db, 2, created_at=timestamp, username="bob", action="delete_subject")
    _add_log(db, 3, created_at=timestamp, username="alice", action="publish_timetable")

    body = client.get(
        "/api/audit-logs",
        params={"action": "delete_subject", "q": "alice", "page_size": 1},
    ).json()

    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [wanted.id]


def test_audit_pagination_validates_parameters_and_reports_empty_overflow_page(env):
    client, db = env
    _login_admin(client, db)
    _add_log(db, 1, created_at=datetime(2042, 8, 1, tzinfo=UTC))

    assert client.get("/api/audit-logs?page=0").status_code == 422
    assert client.get("/api/audit-logs?page_size=101").status_code == 422
    assert client.get("/api/audit-logs", params={"q": "x" * 101}).status_code == 422

    overflow = client.get("/api/audit-logs?page=99").json()
    assert overflow == {"items": [], "total": 1, "page": 99, "page_size": 20}
