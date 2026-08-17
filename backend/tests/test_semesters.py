"""学期与作息时间表测试。"""

from uuid import uuid4

from app.models.user import Role
from tests.api_helpers import create_api_semester
from tests.conftest import make_user

PW = "password123"


def login(client, db, roles=(Role.scheduler,), username="s"):
    make_user(db, username, PW, roles=list(roles))
    response = client.post("/api/auth/login", json={"username": username, "password": PW})
    assert response.status_code == 200


def test_school_templates_are_not_a_public_api(env):
    client, db = env
    login(client, db)

    response = client.get("/api/school-templates")

    assert response.status_code == 404


def test_create_semester_starts_from_a_neutral_empty_state(env):
    client, db = env
    login(client, db)

    response = client.post(
        "/api/semesters",
        json={"academic_year": 2026, "term": 1},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["label"] == "2026-2027学年第一学期"
    assert body["period_tables"] == []
    subjects = client.get(f"/api/subjects?semester_id={body['id']}").json()
    assert subjects == []
    assert client.get(f"/api/semesters/{body['id']}/calendar-exceptions").json() == []


def test_create_semester_rejects_reversed_dates(env):
    client, db = env
    login(client, db)

    response = client.post(
        "/api/semesters",
        json={
            "academic_year": 2026,
            "term": 1,
            "start_date": "2026-09-01",
            "end_date": "2026-08-31",
        },
    )

    assert response.status_code == 422


def test_template_fields_are_rejected_by_creation_contracts(env):
    client, db = env
    login(client, db)

    semester_response = client.post(
        "/api/semesters",
        json={"academic_year": 2026, "term": 1, "template_key": "junior_high_draft"},
    )
    assert semester_response.status_code == 422

    semester = client.post(
        "/api/semesters", json={"academic_year": 2026, "term": 1}
    ).json()
    table_response = client.post(
        f"/api/semesters/{semester['id']}/period-tables",
        json={"name": "空白作息时间表", "template_key": "junior_high_draft"},
    )
    assert table_response.status_code == 422


def test_create_period_table_starts_empty_and_keeps_explicit_shape(env):
    client, db = env
    login(client, db)
    semester = client.post(
        "/api/semesters", json={"academic_year": 2026, "term": 1}
    ).json()

    response = client.post(
        f"/api/semesters/{semester['id']}/period-tables",
        json={"name": "六天作息", "num_weekdays": 6, "is_default": True},
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "semester_id": semester["id"],
        "name": "六天作息",
        "num_weekdays": 6,
        "is_default": True,
        "periods": [],
    }


def test_create_duplicate_semester_conflict(env):
    client, db = env
    login(client, db)
    payload = {"academic_year": 2026, "term": 1}
    assert client.post("/api/semesters", json=payload).status_code == 201
    assert client.post("/api/semesters", json=payload).status_code == 409


def test_academic_year_outside_supported_range_is_rejected(env):
    client, db = env
    login(client, db)
    for year in (1899, 2101):
        response = client.post("/api/semesters", json={"academic_year": year, "term": 1})
        assert response.status_code == 422


def test_available_slots_reflect_type_change(env):
    client, db = env
    login(client, db)
    semester = create_api_semester(client)
    table = semester["period_tables"][0]
    table_id = table["id"]

    before = client.get(f"/api/period-tables/{table_id}/available-slots").json()
    target = next(
        period
        for period in table["periods"]
        if period["weekday"] == 5 and period["type"] == "regular"
    )
    for period in table["periods"]:
        if period["id"] == target["id"]:
            period["type"] = "homeroom"
    payload = [
        {
            key: period[key]
            for key in ("weekday", "period_no", "name", "start_time", "end_time", "type")
        }
        for period in table["periods"]
    ]
    assert client.put(f"/api/period-tables/{table_id}/periods", json=payload).status_code == 200

    after = client.get(f"/api/period-tables/{table_id}/available-slots").json()
    assert len(after) == len(before) - 1
    assert not any(
        slot["weekday"] == 5 and slot["period_no"] == target["period_no"] for slot in after
    )


def test_second_period_table_can_become_default(env):
    client, db = env
    login(client, db)
    semester = create_api_semester(client)
    first_table_id = semester["period_tables"][0]["id"]

    response = client.post(
        f"/api/semesters/{semester['id']}/period-tables",
        json={"name": "备用作息时间表", "is_default": True},
    )

    assert response.status_code == 201
    full = client.get(f"/api/semesters/{semester['id']}").json()
    assert len(full["period_tables"]) == 2
    defaults = [table for table in full["period_tables"] if table["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] != first_table_id


def test_update_semester_status(env):
    client, db = env
    login(client, db)
    semester = client.post(
        "/api/semesters", json={"academic_year": 2026, "term": 1}
    ).json()
    response = client.patch(f"/api/semesters/{semester['id']}", json={"status": "active"})
    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_delete_semester_cascades(env):
    client, db = env
    login(client, db, roles=(Role.admin,))
    semester = create_api_semester(client)
    assert client.request(
        "DELETE",
        f"/api/semesters/{semester['id']}",
        json={
            "operation_id": str(uuid4()),
            "confirmed": True,
            "target": f"semester:{semester['id']}",
        },
    ).status_code == 204
    assert client.get(f"/api/semesters/{semester['id']}").status_code == 404


def test_teacher_cannot_create_semester(env):
    client, db = env
    login(client, db, roles=(Role.teacher,), username="t")
    assert (
        client.post("/api/semesters", json={"academic_year": 2026, "term": 1}).status_code
        == 403
    )


def test_replace_periods_rejects_duplicate_cell(env):
    client, db = env
    login(client, db)
    semester = client.post(
        "/api/semesters", json={"academic_year": 2026, "term": 1}
    ).json()
    table = client.post(
        f"/api/semesters/{semester['id']}/period-tables", json={"name": "空白作息时间表"}
    ).json()
    duplicate = [
        {"weekday": 1, "period_no": 1, "name": "第一节", "type": "regular"},
        {"weekday": 1, "period_no": 1, "name": "重复", "type": "regular"},
    ]
    assert (
        client.put(f"/api/period-tables/{table['id']}/periods", json=duplicate).status_code
        == 400
    )
