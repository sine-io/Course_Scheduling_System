"""真实 Word/Excel 参考文件适配器的端到端契约测试。"""

from collections import Counter
from pathlib import Path

from app.models.assignment import CourseAssignment
from app.models.basedata import ClassUnit, Subject, Teacher
from app.models.period import Period
from app.models.reference_import import ReferenceImportBatch, ReferenceSchedulingRule
from app.models.timetable import ScheduleEntry
from app.models.user import Role
from tests.conftest import make_user

PW = "password123"
REPO_ROOT = Path(__file__).resolve().parents[2]
WORD = REPO_ROOT / "ref" / "排课规则.docx"
XLSX = REPO_ROOT / "ref" / "教师安排8.24.xlsx"


def _files() -> dict[str, tuple[str, bytes, str]]:
    return {
        "word_file": (
            WORD.name,
            WORD.read_bytes(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        "xlsx_file": (
            XLSX.name,
            XLSX.read_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    }


def _target_semester(env):
    client, db = env
    make_user(db, "reference-import", PW, roles=[Role.director])
    login = client.post("/api/auth/login", json={"username": "reference-import", "password": PW})
    assert login.status_code == 200, login.json()
    response = client.post(
        "/api/semesters",
        json={
            "academic_year": 2026,
            "term": 1,
            "start_date": "2026-09-01",
            "end_date": "2027-01-25",
        },
    )
    assert response.status_code == 201, response.json()
    return client, db, response.json()["id"]


def test_reference_files_preview_commit_and_repeat_without_overwriting_manual_data(env):
    client, db, semester_id = _target_semester(env)

    preview_response = client.post(
        f"/api/import/reference/preview?semester_id={semester_id}",
        files=_files(),
    )
    assert preview_response.status_code == 200, preview_response.json()
    preview = preview_response.json()
    assert preview["can_commit"] is True
    assert preview["errors"] == []
    assert preview["semester"]["end_date"] == "2027-01-25"
    assert preview["counts"]["classes"] == 12
    assert preview["counts"]["teachers"] == 43
    assert preview["counts"]["assignments"] == 184
    assert any("心理" in warning and "忽略" in warning for warning in preview["warnings"])

    totals = Counter()
    for row in preview["assignments"]:
        totals[row["class_name"]] += row["periods"]
    assert len(totals) == 12
    assert set(totals.values()) == {35}
    assert not any(row["subject"] == "心理健康教育" for row in preview["assignments"])
    assert db.query(CourseAssignment).count() == 0
    assert db.query(ClassUnit).count() == 0

    unconfirmed = client.post(
        f"/api/import/reference/commit?semester_id={semester_id}",
        data={"fingerprint": preview["fingerprint"], "confirm_changes": "false"},
        files=_files(),
    )
    assert unconfirmed.status_code == 409
    assert unconfirmed.json()["detail"]["code"] == "reference_import_changes_unconfirmed"
    assert db.query(CourseAssignment).count() == 0

    committed = client.post(
        f"/api/import/reference/commit?semester_id={semester_id}",
        data={"fingerprint": preview["fingerprint"], "confirm_changes": "true"},
        files=_files(),
    )
    assert committed.status_code == 200, committed.json()
    assert committed.json()["created"]["assignments"] == 184
    assert db.query(CourseAssignment).count() == 184
    assert db.query(Period).count() == 40
    assert db.query(ScheduleEntry).count() == 5
    assert db.query(ScheduleEntry).filter(ScheduleEntry.locked.is_(True)).count() == 5
    assert db.query(ReferenceImportBatch).count() == 1
    assert db.query(ReferenceSchedulingRule).count() > 0
    assert db.query(Subject).filter(Subject.name == "心理健康教育").count() == 1
    assert db.query(Teacher).filter(Teacher.name == "金铭").count() == 0
    assert db.query(Teacher).filter(Teacher.name.in_(["三周八年级", "四周九年级", "八年级主管", "九年级主管"])).count() == 0
    assert db.query(Teacher).filter(Teacher.name.in_(["王怡凡", "劼唅"]), Teacher.is_active.is_(True)).count() == 2
    homerooms = {
        class_unit.name: class_unit.homeroom_teacher.name
        for class_unit in db.query(ClassUnit).all()
        if class_unit.homeroom_teacher is not None
    }
    assert len(homerooms) == 12
    assert homerooms["7.1"] == "韩晶雪"
    assert homerooms["7.5"] == "耿雪琪"

    follow_up = client.post(
        f"/api/import/reference/preview?semester_id={semester_id}",
        files=_files(),
    )
    assert follow_up.status_code == 200, follow_up.json()
    repeated = client.post(
        f"/api/import/reference/commit?semester_id={semester_id}",
        data={"fingerprint": follow_up.json()["fingerprint"], "confirm_changes": "true"},
        files=_files(),
    )
    assert repeated.status_code == 200, repeated.json()
    assert repeated.json()["idempotent"] is True
    assert db.query(CourseAssignment).count() == 184
    assert db.query(ReferenceImportBatch).count() == 1
