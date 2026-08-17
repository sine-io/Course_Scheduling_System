"""作息分组建议与原子应用 API 测试。"""

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models.basedata import ClassUnit
from app.models.period import Period, PeriodTable
from app.models.user import Role
from tests.conftest import make_user

PW = "password123"


@pytest.fixture
def setup_env(env):
    client, db = env
    make_user(db, "schedule", PW, roles=[Role.scheduler])
    assert client.post(
        "/api/auth/login", json={"username": "schedule", "password": PW}
    ).status_code == 200
    semester = client.post(
        "/api/semesters",
        json={
            "academic_year": 2026,
            "term": 1,
            "start_date": "2026-09-01",
            "end_date": "2027-01-20",
        },
    ).json()
    return client, db, semester["id"]


def add_class(client, semester_id: int, name: str, track: str, grade: int = 1) -> int:
    response = client.post(
        f"/api/class-units?semester_id={semester_id}",
        json={"grade": grade, "name": name, "track": track},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def pattern(
    number: int,
    name: str,
    period_type: str = "regular",
    weekdays: list[int] | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict:
    return {
        "period_no": number,
        "weekdays": weekdays or [1, 2, 3, 4, 5],
        "name": name,
        "type": period_type,
        "start_time": start_time,
        "end_time": end_time,
    }


def apply(client, semester_id: int, fingerprint: str, groups: list[dict]):
    return client.put(
        f"/api/semesters/{semester_id}/period-setup",
        json={"fingerprint": fingerprint, "groups": groups},
    )


def test_empty_semester_gets_a_neutral_period_suggestion(setup_env):
    client, db, semester_id = setup_env

    response = client.get(f"/api/semesters/{semester_id}/period-setup")

    assert response.status_code == 200
    draft = response.json()
    assert draft["source"] == "suggested"
    assert len(draft["groups"]) == 1
    assert draft["groups"][0] == {
        "key": "default",
        "table_id": None,
        "name": "默认作息",
        "num_weekdays": 5,
        "is_default": True,
        "class_ids": [],
        "periods": [pattern(1, "第一节")],
    }
    assert "初中" not in response.text
    assert draft["ready"] is True
    assert draft["warnings"] == [
        "当前学期还没有班级，作息分组建议会随基础数据补充",
        "有节次尚未填写完整的开始和结束时间",
    ]
    assert db.query(PeriodTable).count() == 0


def test_mixed_tracks_are_only_suggested_and_do_not_write(setup_env):
    client, db, semester_id = setup_env
    junior_a = add_class(client, semester_id, "初一1班", "junior_high", 7)
    junior_b = add_class(client, semester_id, "初一2班", "junior_high", 7)
    senior = add_class(client, semester_id, "高一1班", "senior_high", 10)

    response = client.get(f"/api/semesters/{semester_id}/period-setup")

    assert response.status_code == 200
    draft = response.json()
    assert draft["source"] == "suggested"
    assert [(group["name"], group["class_ids"]) for group in draft["groups"]] == [
        ("初中作息", [junior_a, junior_b]),
        ("普通高中作息", [senior]),
    ]
    assert all(group["table_id"] is None for group in draft["groups"])
    assert all(group["periods"][0]["type"] == "regular" for group in draft["groups"])
    assert db.query(PeriodTable).count() == 0
    assert all(item.period_table_id is None for item in db.query(ClassUnit).all())


def test_apply_can_mix_tracks_and_split_one_track_atomically(setup_env):
    client, db, semester_id = setup_env
    junior_a = add_class(client, semester_id, "初一1班", "junior_high", 7)
    junior_b = add_class(client, semester_id, "初一2班", "junior_high", 7)
    senior = add_class(client, semester_id, "高一1班", "senior_high", 10)
    fingerprint = client.get(f"/api/semesters/{semester_id}/period-setup").json()[
        "fingerprint"
    ]
    groups = [
        {
            "key": "shared",
            "table_id": None,
            "name": "共同作息",
            "num_weekdays": 5,
            "is_default": True,
            "class_ids": [junior_a, senior],
            "periods": [
                pattern(1, "早自习", "morning", start_time="07:40", end_time="08:00"),
                pattern(2, "第一节", "regular", start_time="08:10", end_time="08:50"),
                pattern(3, "午休", "lunch"),
                pattern(4, "班会", "homeroom", weekdays=[1]),
                pattern(4, "固定活动", "reserved", weekdays=[2, 3, 4, 5]),
            ],
        },
        {
            "key": "junior-late",
            "table_id": None,
            "name": "初中错峰作息",
            "num_weekdays": 6,
            "is_default": False,
            "class_ids": [junior_b],
            "periods": [pattern(1, "第一节", weekdays=[1, 2, 3, 4, 5, 6])],
        },
    ]

    response = apply(client, semester_id, fingerprint, groups)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["ready"] is True
    assert result["blockers"] == []
    assert "有节次尚未填写完整的开始和结束时间" in result["warnings"]
    tables = db.query(PeriodTable).order_by(PeriodTable.id).all()
    assert [(table.name, table.num_weekdays, table.is_default) for table in tables] == [
        ("共同作息", 5, True),
        ("初中错峰作息", 6, False),
    ]
    assignments = {
        item.name: item.period_table_id for item in db.query(ClassUnit).order_by(ClassUnit.id)
    }
    assert assignments["初一1班"] == assignments["高一1班"]
    assert assignments["初一2班"] != assignments["初一1班"]
    assert db.query(Period).count() == 5 * 4 + 6


def test_reapply_can_merge_existing_groups_and_remove_unused_table(setup_env):
    client, db, semester_id = setup_env
    first = add_class(client, semester_id, "一班", "junior_high", 7)
    second = add_class(client, semester_id, "二班", "senior_high", 10)
    initial = client.get(f"/api/semesters/{semester_id}/period-setup").json()
    created = apply(client, semester_id, initial["fingerprint"], initial["groups"])
    assert created.status_code == 200
    existing = client.get(f"/api/semesters/{semester_id}/period-setup").json()
    assert existing["source"] == "existing"
    keep = existing["groups"][0]
    keep.update({"name": "合并作息", "class_ids": [first, second], "is_default": True})

    response = apply(client, semester_id, existing["fingerprint"], [keep])

    assert response.status_code == 200, response.text
    assert db.query(PeriodTable).count() == 1
    table = db.query(PeriodTable).one()
    assert table.name == "合并作息"
    assert {item.period_table_id for item in db.query(ClassUnit).all()} == {table.id}


def test_apply_rejects_stale_or_invalid_grouping_without_partial_writes(setup_env):
    client, db, semester_id = setup_env
    first = add_class(client, semester_id, "一班", "junior_high", 7)
    draft = client.get(f"/api/semesters/{semester_id}/period-setup").json()
    second = add_class(client, semester_id, "二班", "junior_high", 7)

    stale = apply(client, semester_id, draft["fingerprint"], draft["groups"])
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "period_setup_stale"
    assert db.query(PeriodTable).count() == 0

    current = client.get(f"/api/semesters/{semester_id}/period-setup").json()
    invalid_groups = [
        {
            **current["groups"][0],
            "class_ids": [first],
        }
    ]
    invalid = apply(client, semester_id, current["fingerprint"], invalid_groups)
    assert invalid.status_code == 409
    assert invalid.json()["detail"]["code"] == "period_setup_invalid"
    assert str(second) in invalid.json()["detail"]["message"]
    assert db.query(PeriodTable).count() == 0


def test_database_failure_rolls_back_every_group(setup_env, monkeypatch):
    client, db, semester_id = setup_env
    add_class(client, semester_id, "一班", "junior_high", 7)
    add_class(client, semester_id, "二班", "senior_high", 10)
    draft = client.get(f"/api/semesters/{semester_id}/period-setup").json()

    from app.services import period_setup

    original = period_setup._replace_periods
    calls = 0

    def fail_on_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SQLAlchemyError("simulated write failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(period_setup, "_replace_periods", fail_on_second)

    response = apply(client, semester_id, draft["fingerprint"], draft["groups"])

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "period_setup_write_conflict"
    db.expire_all()
    assert db.query(PeriodTable).count() == 0
    assert all(item.period_table_id is None for item in db.query(ClassUnit).all())


def test_apply_rejects_setup_without_any_regular_period(setup_env):
    client, db, semester_id = setup_env
    draft = client.get(f"/api/semesters/{semester_id}/period-setup").json()
    group = {
        **draft["groups"][0],
        "periods": [pattern(1, "午休", "lunch")],
    }

    response = apply(client, semester_id, draft["fingerprint"], [group])

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "period_setup_invalid"
    assert response.json()["detail"]["message"] == "至少需要一个常规课节次"
    assert db.query(PeriodTable).count() == 0
