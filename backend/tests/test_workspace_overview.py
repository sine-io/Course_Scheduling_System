"""工作空间首页总览的聚合口径与权限测试。"""

from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from app.models.basedata import Teacher
from app.models.leave import AffectedPeriod, AffectedStatus, LeaveRequest, LeaveStatus, LeaveType
from app.models.notification import Notification, NotificationType
from app.models.semester import Semester
from app.models.timetable import ScheduleEntry, Timetable, TimetableStatus
from app.models.user import Role
from tests.conftest import make_user
from tests.fixtures._common import Builder

PW = "password123"
TODAY = date(2026, 8, 17)
NOW = datetime(2026, 8, 17, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))


def _login(client, db, username: str, role: Role) -> None:
    make_user(db, username, PW, roles=[role])
    response = client.post(
        "/api/auth/login", json={"username": username, "password": PW}
    )
    assert response.status_code == 200


@pytest.mark.parametrize("role", [Role.admin, Role.scheduler, Role.director])
def test_management_roles_can_read_overview(env, role):
    client, db = env
    semester = Semester(academic_year=2026, term=1)
    db.add(semester)
    db.commit()
    _login(client, db, f"user-{role.value}", role)

    response = client.get(
        "/api/workspace-overview", params={"semester_id": semester.id}
    )

    assert response.status_code == 200
    assert response.json()["semester_id"] == semester.id


def test_teacher_cannot_read_overview(env):
    client, db = env
    semester = Semester(academic_year=2026, term=1)
    db.add(semester)
    db.commit()
    _login(client, db, "teacher", Role.teacher)

    response = client.get(
        "/api/workspace-overview", params={"semester_id": semester.id}
    )

    assert response.status_code == 403


def test_overview_uses_latest_draft_and_real_operational_counts(env):
    client, db = env
    builder = Builder(db, 2026, 1, "junior_high")
    builder.teacher("王老师", subjects=["数学"])
    builder.klass("七年级1班", grade=7, track="junior_high")
    assignment = builder.assign(
        subject="数学",
        teachers=["王老师"],
        periods=4,
        classes=["七年级1班"],
    )[0]
    builder.room("普通教室")
    fixture = builder.build()
    fixture.semester.start_date = date(2026, 8, 1)
    fixture.semester.end_date = date(2027, 1, 20)
    db.add(
        Teacher(
            semester_id=fixture.semester_id,
            name="已离校教师",
            is_active=False,
        )
    )

    published = Timetable(
        semester_id=fixture.semester_id,
        name="已发布课表",
        status=TimetableStatus.published.value,
        updated_at=datetime(2026, 8, 16, tzinfo=UTC),
    )
    older_draft = Timetable(
        semester_id=fixture.semester_id,
        name="较早草稿",
        status=TimetableStatus.draft.value,
        updated_at=datetime(2026, 8, 14, tzinfo=UTC),
    )
    latest_draft = Timetable(
        semester_id=fixture.semester_id,
        name="最近草稿",
        status=TimetableStatus.draft.value,
        updated_at=datetime(2026, 8, 15, tzinfo=UTC),
    )
    db.add_all([published, older_draft, latest_draft])
    db.flush()
    db.add(
        ScheduleEntry(
            timetable_id=latest_draft.id,
            course_assignment_id=assignment.id,
            weekday=1,
            period_no=2,
            span=2,
        )
    )

    leave = LeaveRequest(
        semester_id=fixture.semester_id,
        teacher_id=fixture.teachers["王老师"].id,
        leave_type=LeaveType.personal.value,
        start_date=TODAY,
        end_date=TODAY + timedelta(days=8),
        status=LeaveStatus.registered.value,
        created_by_name="排课员",
    )
    db.add(leave)
    db.flush()
    db.add_all(
        [
            AffectedPeriod(
                leave_request_id=leave.id,
                semester_id=fixture.semester_id,
                date=TODAY,
                weekday=1,
                period_no=2,
                period_name="第一节",
                start_time=time(8, 20),
                end_time=time(9, 5),
                subject_name="数学",
                class_names="七年级1班",
                status=AffectedStatus.pending.value,
            ),
            AffectedPeriod(
                leave_request_id=leave.id,
                semester_id=fixture.semester_id,
                date=TODAY + timedelta(days=1),
                weekday=2,
                period_no=2,
                period_name="第一节",
                subject_name="数学",
                class_names="七年级1班",
                status=AffectedStatus.resolved.value,
            ),
            AffectedPeriod(
                leave_request_id=leave.id,
                semester_id=fixture.semester_id,
                date=TODAY + timedelta(days=2),
                weekday=3,
                period_no=2,
                period_name="第一节",
                subject_name="数学",
                class_names="七年级1班",
                status=AffectedStatus.cancelled.value,
            ),
            AffectedPeriod(
                leave_request_id=leave.id,
                semester_id=fixture.semester_id,
                date=TODAY + timedelta(days=8),
                weekday=2,
                period_no=3,
                period_name="第二节",
                subject_name="数学",
                class_names="七年级1班",
                status=AffectedStatus.pending.value,
            ),
        ]
    )
    db.add_all(
        [
            Notification(
                semester_id=fixture.semester_id,
                type=NotificationType.leave_registered.value,
                title="待确认通知",
            ),
            Notification(
                semester_id=fixture.semester_id,
                type=NotificationType.leave_registered.value,
                title="已确认通知",
                acknowledged_at=datetime(2026, 8, 16, tzinfo=UTC),
            ),
        ]
    )
    db.commit()
    _login(client, db, "scheduler", Role.scheduler)

    with (
        patch("app.services.workspace_overview.clock.school_today", return_value=TODAY),
        patch("app.services.workspace_overview.clock.school_now", return_value=NOW),
    ):
        response = client.get(
            "/api/workspace-overview",
            params={"semester_id": fixture.semester_id},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["metrics"] == {
        "active_teacher_count": 1,
        "class_count": 1,
        "weekly_affected_periods": 2,
        "week_start": "2026-08-17",
        "week_end": "2026-08-23",
    }
    assert body["timetable"] | {"updated_at": None} == {
        "id": latest_draft.id,
        "name": "最近草稿",
        "status": "draft",
        "updated_at": None,
        "required_periods": 4,
        "placed_periods": 2,
        "remaining_periods": 2,
        "completion_rate": 50,
    }
    assert body["today_pending_periods"] == 1
    assert body["unacknowledged_notifications"] == 1
    assert [item["code"] for item in body["focus_items"]] == [
        "today_pending_periods",
        "remaining_periods",
        "unacknowledged_notifications",
    ]


def test_published_fallback_and_no_assignments_have_no_completion_rate(env):
    client, db = env
    semester = Semester(
        academic_year=2026,
        term=1,
        start_date=date(2026, 8, 1),
        end_date=date(2027, 1, 20),
    )
    db.add(semester)
    db.flush()
    published = Timetable(
        semester_id=semester.id,
        name="当前发布版",
        status=TimetableStatus.published.value,
    )
    db.add(published)
    db.commit()
    _login(client, db, "director", Role.director)

    response = client.get(
        "/api/workspace-overview", params={"semester_id": semester.id}
    )

    assert response.status_code == 200
    timetable = response.json()["timetable"]
    assert timetable["id"] == published.id
    assert timetable["completion_rate"] is None
    assert timetable["remaining_periods"] == 0


def test_preflight_failure_does_not_blank_other_sections(env):
    client, db = env
    semester = Semester(academic_year=2026, term=1)
    db.add(semester)
    db.commit()
    _login(client, db, "scheduler", Role.scheduler)

    with patch(
        "app.services.workspace_overview.load_problem",
        side_effect=RuntimeError("preflight unavailable"),
    ):
        response = client.get(
            "/api/workspace-overview", params={"semester_id": semester.id}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["active_teacher_count"] == 0
    assert body["preflight"] == {
        "available": False,
        "error_count": 0,
        "warning_count": 0,
        "unavailable_message": "排课前置检查暂时无法读取",
    }
    assert body["focus_items"]


def test_unknown_semester_returns_404(env):
    client, db = env
    _login(client, db, "scheduler", Role.scheduler)

    response = client.get("/api/workspace-overview", params={"semester_id": 999})

    assert response.status_code == 404
