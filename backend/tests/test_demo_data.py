"""国内初中示例数据测试。

除了验证数据规模，还要保证示例数据能够通过预检并实际生成课表。否则用户首次体验
自动排课时只会得到一个无法解释的失败结果。
"""

import pytest

from app.models.assignment import CourseAssignment
from app.models.basedata import ClassUnit, Teacher
from app.models.semester import Semester
from app.models.user import Role
from app.services import assignments as assign_svc
from app.services import demo_data
from tests.conftest import make_user

PW = "password123"


@pytest.fixture
def admin_client(env):
    client, db = env
    make_user(db, "adm", PW, roles=[Role.admin])
    client.post("/api/auth/login", json={"username": "adm", "password": PW})
    return client, db


def test_spec_gives_every_class_the_same_weekly_periods():
    spec = demo_data.load_spec()
    per_grade = {
        grade: sum(s["periods"].get(str(grade), 0) for s in spec["subjects"])
        for grade in spec["classes"]["grades"]
    }
    assert set(per_grade.values()) == {33}, f"各年级课时数不一致：{per_grade}"


def test_spec_capacity_covers_demand():
    """示例教师的应授课时总量应覆盖教学任务，且不能明显超编。"""
    spec = demo_data.load_spec()
    count = spec["classes"]["per_grade"]
    demand = sum(
        subject["periods"].get(str(grade), 0) * count
        for subject in spec["subjects"]
        for grade in spec["classes"]["grades"]
    )
    classes = demo_data._class_names(spec)
    plans = demo_data._plan_teachers(spec, [name for _, name in classes])
    capacity = sum(plan.target for plan in plans)
    assert capacity >= demand
    assert capacity / demand < 1.15, "示例教师明显过剩，工作量统计缺少代表性"


def test_spec_has_one_homeroom_teacher_per_class():
    spec = demo_data.load_spec()
    classes = demo_data._class_names(spec)
    homerooms = sum(
        dept.get(demo_data.ROLE_HOMEROOM, 0) for dept in spec["departments"]
    )
    assert homerooms == len(classes)


def test_generate_builds_a_complete_school(admin_client):
    client, _ = admin_client
    response = client.post("/api/demo-data")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["classes"] == 18
    assert body["subjects"] == 16
    assert body["total_periods"] == 33 * 18
    assert body["assignments"] > 200
    assert body["rooms"] >= 18


def test_demo_has_35_schedulable_periods_per_class(admin_client):
    client, db = admin_client
    body = client.post("/api/demo-data").json()
    semester = db.get(Semester, body["semester_id"])
    regular = [period for period in semester.period_tables[0].periods if period.type == "regular"]
    assert len(regular) == 35


def test_class_names_use_grade_plus_serial(admin_client):
    client, db = admin_client
    client.post("/api/demo-data")
    names = sorted(class_unit.name for class_unit in db.query(ClassUnit).all())
    assert names == [
        "701", "702", "703", "704", "705", "706",
        "801", "802", "803", "804", "805", "806",
        "901", "902", "903", "904", "905", "906",
    ]


def test_school_name_is_reported(admin_client):
    client, _ = admin_client
    expected = "海州市启明实验初级中学"
    assert client.get("/api/demo-data").json()["school_name"] == expected
    assert client.post("/api/demo-data").json()["school_name"] == expected


def test_every_class_has_a_homeroom_teacher(admin_client):
    client, db = admin_client
    client.post("/api/demo-data")
    for class_unit in db.query(ClassUnit).all():
        assert class_unit.homeroom_teacher_id is not None, f"{class_unit.name} 没有班主任"


def test_nobody_exceeds_the_overtime_limit(admin_client):
    client, db = admin_client
    body = client.post("/api/demo-data").json()
    loads = assign_svc.teacher_loads(db, body["semester_id"])
    over = [row for row in loads if row["over_limit"]]
    assert not over, f"教师超过上限：{[(r['name'], r['delta']) for r in over]}"
    assert body["max_overtime_used"] <= 8


def test_shows_both_over_and_under_hours(admin_client):
    client, db = admin_client
    body = client.post("/api/demo-data").json()
    loads = assign_svc.teacher_loads(db, body["semester_id"])
    assert any(row["delta"] > 0 for row in loads), "没有教师处于超课时状态"
    assert any(row["delta"] < 0 for row in loads), "没有教师处于课时不足状态"


def test_no_teacher_is_left_without_classes(admin_client):
    client, db = admin_client
    body = client.post("/api/demo-data").json()
    idle = [
        row["name"]
        for row in assign_svc.teacher_loads(db, body["semester_id"])
        if row["assigned"] == 0
    ]
    assert not idle, f"教师没有任何教学任务：{idle}"


def test_homeroom_workload_is_applied(admin_client):
    client, db = admin_client
    client.post("/api/demo-data")
    homerooms = [
        teacher.base_periods
        for teacher in db.query(Teacher).all()
        if db.query(ClassUnit)
        .filter(ClassUnit.homeroom_teacher_id == teacher.id)
        .first()
    ]
    assert len(homerooms) == 18
    assert set(homerooms) == {12}


def test_admin_reduction_uses_demo_targets(admin_client):
    client, db = admin_client
    client.post("/api/demo-data")
    targets = {
        teacher.admin_title: teacher.base_periods - teacher.admin_reduction
        for teacher in db.query(Teacher).filter(Teacher.admin_title.isnot(None)).all()
    }
    assert targets
    for title, target in targets.items():
        # 国内示例将中层干部和教研负责人使用不同的应授课时。
        expected = 10 if "教研负责人" in title else 8
        assert target == expected, f"{title} 应授 {target}，预期为 {expected}"


def test_science_subjects_follow_mainland_grade_split(admin_client):
    client, db = admin_client
    semester_id = client.post("/api/demo-data").json()["semester_id"]
    assignments = (
        db.query(CourseAssignment)
        .filter(CourseAssignment.semester_id == semester_id)
        .all()
    )
    by_grade: dict[int, set[str]] = {}
    for assignment in assignments:
        for member in assignment.scheduling_unit.members:
            by_grade.setdefault(member.class_unit.grade, set()).add(assignment.subject.name)
    assert "生物学" in by_grade[7] and "物理" not in by_grade[7]
    assert {"生物学", "物理"} <= by_grade[8] and "化学" not in by_grade[8]
    assert {"物理", "化学"} <= by_grade[9]
    assert "生物学" not in by_grade[9] and "地理" not in by_grade[9]


def test_refuses_when_a_semester_already_exists(admin_client):
    client, _ = admin_client
    assert client.post("/api/demo-data").status_code == 201
    again = client.post("/api/demo-data")
    assert again.status_code == 409
    assert "已有学期数据" in again.json()["detail"]


def test_status_endpoint_reflects_availability(admin_client):
    client, _ = admin_client
    assert client.get("/api/demo-data").json()["available"] is True
    client.post("/api/demo-data")
    after = client.get("/api/demo-data").json()
    assert after["available"] is False and after["reason"]


def test_non_admin_cannot_load_demo_data(env):
    client, db = env
    make_user(db, "s", PW, roles=[Role.scheduler])
    client.post("/api/auth/login", json={"username": "s", "password": PW})
    assert client.post("/api/demo-data").status_code == 403


def test_demo_data_is_actually_solvable(admin_client):
    from app.services.solver_data import load_problem
    from app.solver import preflight
    from app.solver.model_builder import SolveOptions, solve
    from app.solver.problem import SolverConfig
    from app.solver.validator import validate

    client, db = admin_client
    semester_id = client.post("/api/demo-data").json()["semester_id"]
    problem = load_problem(db, semester_id)
    errors = preflight.run(problem).errors
    assert not errors, f"预检失败：{[(item.code, item.message) for item in errors]}"

    result = solve(
        problem,
        SolveOptions(max_seconds=120, workers=4),
        config=SolverConfig.hard_only(),
    )
    assert result.status in ("optimal", "feasible"), f"示例数据无法排课：{result.status}"
    assert not validate(problem, result.entries), "求解结果违反硬约束"
    assert len(result.entries) == 33 * 18


def test_demo_data_marks_the_setup_wizard_complete(admin_client):
    from app.models.wizard import SINGLETON_ID, WizardState

    client, db = admin_client
    body = client.post("/api/demo-data").json()
    state = db.get(WizardState, SINGLETON_ID)
    assert state is not None and state.completed is True
    assert state.semester_id == body["semester_id"]
    assert client.get("/api/wizard/state").json()["completed"] is True
    readiness = client.get(f"/api/semesters/{body['semester_id']}/readiness").json()
    assert readiness["ready"] is True
    timetables = client.get(f"/api/timetables?semester_id={body['semester_id']}").json()
    assert len(timetables) == 1
    assert timetables[0]["status"] == "draft"
