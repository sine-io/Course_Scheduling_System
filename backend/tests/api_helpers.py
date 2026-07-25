"""API 测试使用的数据构建工具，不依赖公开学校模板。"""

from collections.abc import Iterable

from fastapi.testclient import TestClient

from tests.dates import SEM_END, SEM_START

JUNIOR_HIGH_SLOTS = (
    (1, "早自习", "07:50", "08:20", "morning"),
    (2, "第一节", "08:20", "09:05", "regular"),
    (3, "第二节", "09:15", "10:00", "regular"),
    (4, "第三节", "10:20", "11:05", "regular"),
    (5, "第四节", "11:15", "12:00", "regular"),
    (6, "午休", "12:00", "13:10", "lunch"),
    (7, "第五节", "13:10", "13:55", "regular"),
    (8, "第六节", "14:05", "14:50", "regular"),
    (9, "第七节", "15:10", "15:55", "regular"),
)

SENIOR_HIGH_SLOTS = (
    (1, "早自习", "07:40", "08:00", "morning"),
    (2, "第一节", "08:00", "08:50", "regular"),
    (3, "第二节", "09:00", "09:50", "regular"),
    (4, "第三节", "10:00", "10:50", "regular"),
    (5, "第四节", "11:00", "11:50", "regular"),
    (6, "午休", "11:50", "13:10", "lunch"),
    (7, "第五节", "13:10", "14:00", "regular"),
    (8, "第六节", "14:10", "15:00", "regular"),
    (9, "第七节", "15:10", "16:00", "regular"),
    (10, "第八节", "16:10", "17:00", "regular"),
)


def period_rows(
    slots: Iterable[tuple[int, str, str, str, str]] = JUNIOR_HIGH_SLOTS,
    *,
    weekdays: int = 5,
) -> list[dict[str, object]]:
    return [
        {
            "weekday": weekday,
            "period_no": period_no,
            "name": name,
            "start_time": start,
            "end_time": end,
            "type": period_type,
        }
        for weekday in range(1, weekdays + 1)
        for period_no, name, start, end, period_type in slots
    ]


def create_period_table(
    client: TestClient,
    semester_id: int,
    *,
    name: str,
    slots: Iterable[tuple[int, str, str, str, str]] = JUNIOR_HIGH_SLOTS,
    is_default: bool = False,
) -> dict:
    """直接构建测试用作息时间表，不依赖公开模板。"""
    response = client.post(
        f"/api/semesters/{semester_id}/period-tables",
        json={"name": name, "is_default": is_default},
    )
    assert response.status_code == 201, response.text
    table = response.json()
    periods_response = client.put(
        f"/api/period-tables/{table['id']}/periods",
        json=period_rows(slots),
    )
    assert periods_response.status_code == 200, periods_response.text
    return periods_response.json()


def create_api_semester(
    client: TestClient,
    academic_year: int = 2026,
    term: int = 1,
    *,
    with_periods: bool = True,
    ready: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """通过业务 API 创建学期，并按需直接构建测试用作息时间表。"""
    body: dict[str, object] = {
        "academic_year": academic_year,
        "term": term,
        "start_date": start_date or (str(SEM_START) if ready else None),
        "end_date": end_date or (str(SEM_END) if ready else None),
    }
    response = client.post("/api/semesters", json=body)
    assert response.status_code == 201, response.text
    semester = response.json()
    if with_periods:
        create_period_table(
            client,
            semester["id"],
            name="初中作息时间表",
            is_default=True,
        )
    if ready:
        ready_response = client.post(f"/api/semesters/{semester['id']}/readiness")
        assert ready_response.status_code == 200, ready_response.text
    return client.get(f"/api/semesters/{semester['id']}").json()
