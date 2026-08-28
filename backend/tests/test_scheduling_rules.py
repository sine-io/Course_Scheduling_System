"""版本化排课规则的公开 API 与求解器接线测试。"""

import pytest

from app.models.timetable import Timetable
from app.models.user import Role
from app.services.solver_data import load_problem
from app.solver.model_builder import Relaxation, SolveOptions, solve
from app.solver.problem import SolverConfig
from app.solver.validator import validate
from tests.api_helpers import create_api_semester, create_period_table
from tests.conftest import make_user

PW = "password123"


@pytest.fixture
def rules_env(env):
    client, db = env
    make_user(db, "director", PW, roles=[Role.director])
    assert (
        client.post("/api/auth/login", json={"username": "director", "password": PW}).status_code
        == 200
    )
    semester = create_api_semester(client)
    sid = semester["id"]
    subject = client.post(f"/api/subjects?semester_id={sid}", json={"name": "体育与健康"}).json()
    teacher = client.post(
        f"/api/teachers?semester_id={sid}",
        json={"name": "刘老师", "base_periods": 8},
    ).json()
    class_unit = client.post(
        f"/api/class-units?semester_id={sid}",
        json={"grade": 7, "name": "七年级一班", "track": "junior_high"},
    ).json()
    assignment_response = client.post(
        f"/api/assignments?semester_id={sid}",
        json={
            "class_id": class_unit["id"],
            "subject_id": subject["id"],
            "periods_per_week": 2,
            "teachers": [{"teacher_id": teacher["id"]}],
        },
    )
    assert assignment_response.status_code == 201, assignment_response.text
    return {
        "client": client,
        "db": db,
        "semester": semester,
        "subject": subject,
        "teacher": teacher,
        "class_unit": class_unit,
        "assignment": assignment_response.json(),
    }


def _global_blackout(name: str = "行政会保留时段") -> dict:
    return {
        "name": name,
        "template": "global_blackout",
        "target": {"entity_type": "school", "ids": []},
        "timing": {"weekdays": [1], "period_nos": [2], "period_table_ids": []},
        "operator": "forbid",
        "strength": "hard",
        "priority": "high",
        "source_text": "行政会周一第一节，全校不排课",
        "enabled": True,
    }


def test_template_catalog_and_workspace_expose_builtin_and_custom_rules(rules_env):
    client = rules_env["client"]
    sid = rules_env["semester"]["id"]

    templates = client.get("/api/scheduling-rules/templates")
    assert templates.status_code == 200
    by_key = {item["key"]: item for item in templates.json()}
    assert by_key["global_blackout"]["supported"] is True
    assert by_key["teacher_availability"]["supported"] is True
    assert by_key["periodic"]["supported"] is False

    workspace = client.get(f"/api/scheduling-rules?semester_id={sid}")
    assert workspace.status_code == 200
    body = workspace.json()
    assert body["active_revision"] is None
    assert body["draft_revision"] is None
    assert body["rules"] == []
    assert any(rule["source_kind"] == "builtin" for rule in body["builtin_rules"])
    assert body["options"]["teachers"][0]["id"] == rules_env["teacher"]["id"]
    assert body["options"]["period_tables"][0]["slots"][0]["period_no"] == 2


def test_rule_crud_creates_new_draft_after_activation(rules_env):
    client = rules_env["client"]
    sid = rules_env["semester"]["id"]

    created = client.post(f"/api/scheduling-rules?semester_id={sid}", json=_global_blackout())
    assert created.status_code == 201, created.text
    rule = created.json()
    assert rule["status"] == "draft"
    assert rule["summary"] == "全校在周一第1节禁排"

    checked = client.post(f"/api/scheduling-rules/validate?semester_id={sid}")
    assert checked.status_code == 200
    assert checked.json()["valid"] is True
    assert checked.json()["matched_assignment_count"] == 1
    assert checked.json()["excluded_candidate_count"] == 1

    activated = client.post(
        f"/api/scheduling-rules/activate?semester_id={sid}",
        json={"note": "启用行政会规则"},
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["active_revision"]["revision_no"] == 1
    assert activated.json()["draft_revision"] is None

    updated_body = _global_blackout("行政会调整为周二第一节")
    updated_body["timing"]["weekdays"] = [2]
    updated = client.put(
        f"/api/scheduling-rules/{rule['rule_key']}?semester_id={sid}",
        json=updated_body,
    )
    assert updated.status_code == 200, updated.text

    workspace = client.get(f"/api/scheduling-rules?semester_id={sid}").json()
    assert workspace["active_revision"]["revision_no"] == 1
    assert workspace["draft_revision"]["revision_no"] == 2
    assert workspace["rules"][0]["name"] == "行政会调整为周二第一节"

    deleted = client.delete(f"/api/scheduling-rules/{rule['rule_key']}?semester_id={sid}")
    assert deleted.status_code == 204
    deleted_workspace = client.get(f"/api/scheduling-rules?semester_id={sid}").json()
    assert len(deleted_workspace["rules"]) == 1
    assert deleted_workspace["rules"][0]["enabled"] is False
    assert deleted_workspace["rules"][0]["status"] == "disabled"
    assert deleted_workspace["rules"][0]["source_text"] == "行政会周一第一节，全校不排课"


def test_unsupported_template_can_be_recorded_but_not_activated(rules_env):
    client = rules_env["client"]
    sid = rules_env["semester"]["id"]
    response = client.post(
        f"/api/scheduling-rules?semester_id={sid}",
        json={
            "name": "单双周体育轮换",
            "template": "periodic",
            "target": {"entity_type": "assignment", "ids": [rules_env["assignment"]["id"]]},
            "timing": {"weekdays": [2], "period_nos": [3], "week_pattern": "odd"},
            "operator": "allow",
            "strength": "informational",
            "priority": "low",
            "source_text": "单双周轮换",
            "enabled": True,
        },
    )
    assert response.status_code == 201, response.text

    checked = client.post(f"/api/scheduling-rules/validate?semester_id={sid}")
    assert checked.status_code == 200
    assert checked.json()["valid"] is False
    assert checked.json()["diagnostics"][0]["code"] == "unsupported_template"

    activated = client.post(f"/api/scheduling-rules/activate?semester_id={sid}", json={})
    assert activated.status_code == 409
    assert activated.json()["detail"]["code"] == "rule_revision_invalid"


def test_preference_operator_cannot_be_saved_as_a_hard_rule(rules_env):
    client = rules_env["client"]
    sid = rules_env["semester"]["id"]

    response = client.post(
        f"/api/scheduling-rules?semester_id={sid}",
        json={
            "name": "刘老师偏好周五下午",
            "template": "teacher_availability",
            "target": {"entity_type": "teacher", "ids": [rules_env["teacher"]["id"]]},
            "timing": {"weekdays": [5], "period_nos": [7, 8, 9]},
            "operator": "prefer",
            "strength": "hard",
            "priority": "high",
            "source_text": "刘老师最好周五下午上课",
            "enabled": True,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "strength_not_supported"


def test_fixed_placement_requires_enough_distinct_starts_for_all_lessons(rules_env):
    client = rules_env["client"]
    sid = rules_env["semester"]["id"]

    response = client.post(
        f"/api/scheduling-rules?semester_id={sid}",
        json={
            "name": "体育固定周一第一节",
            "template": "fixed_placement",
            "target": {
                "entity_type": "assignment",
                "ids": [rules_env["assignment"]["id"]],
            },
            "timing": {"weekdays": [1], "period_nos": [2]},
            "operator": "allow",
            "strength": "hard",
            "priority": "high",
            "source_text": "每周两节体育都要固排",
            "enabled": True,
        },
    )
    assert response.status_code == 201

    checked = client.post(f"/api/scheduling-rules/validate?semester_id={sid}")
    assert checked.status_code == 200
    assert checked.json()["valid"] is False
    assert any(item["code"] == "no_candidate_after_rules" for item in checked.json()["diagnostics"])


def test_fixed_placement_requires_the_whole_block_inside_selected_cells(rules_env):
    client = rules_env["client"]
    sid = rules_env["semester"]["id"]
    assignment = client.post(
        f"/api/assignments?semester_id={sid}",
        json={
            "class_id": rules_env["class_unit"]["id"],
            "subject_id": rules_env["subject"]["id"],
            "periods_per_week": 4,
            "teachers": [{"teacher_id": rules_env["teacher"]["id"]}],
            "block_rules": [{"block_size": 2, "count_per_week": 2}],
        },
    )
    assert assignment.status_code == 201, assignment.text

    response = client.post(
        f"/api/scheduling-rules?semester_id={sid}",
        json={
            "name": "体育连堂固定周一前两节",
            "template": "fixed_placement",
            "target": {"entity_type": "assignment", "ids": [assignment.json()["id"]]},
            "timing": {"weekdays": [1], "period_nos": [2, 3]},
            "operator": "allow",
            "strength": "hard",
            "priority": "high",
            "source_text": "两次连堂都必须完整落在周一前两节",
            "enabled": True,
        },
    )
    assert response.status_code == 201, response.text

    checked = client.post(f"/api/scheduling-rules/validate?semester_id={sid}")
    assert checked.status_code == 200
    assert checked.json()["valid"] is False
    assert any(item["code"] == "no_candidate_after_rules" for item in checked.json()["diagnostics"])


def test_table_scoped_rule_does_not_affect_another_period_table(rules_env):
    client = rules_env["client"]
    db = rules_env["db"]
    sid = rules_env["semester"]["id"]
    first_table_id = client.get(f"/api/scheduling-rules?semester_id={sid}").json()["options"][
        "period_tables"
    ][0]["id"]
    second_table = create_period_table(client, sid, name="另一套作息")
    second_class = client.post(
        f"/api/class-units?semester_id={sid}",
        json={
            "grade": 7,
            "name": "七年级二班",
            "track": "junior_high",
            "period_table_id": second_table["id"],
        },
    ).json()
    second_assignment = client.post(
        f"/api/assignments?semester_id={sid}",
        json={
            "class_id": second_class["id"],
            "subject_id": rules_env["subject"]["id"],
            "periods_per_week": 1,
            "teachers": [{"teacher_id": rules_env["teacher"]["id"]}],
        },
    ).json()

    body = _global_blackout()
    body["timing"]["period_table_ids"] = [first_table_id]
    created = client.post(f"/api/scheduling-rules?semester_id={sid}", json=body)
    assert created.status_code == 201, created.text
    activated = client.post(f"/api/scheduling-rules/activate?semester_id={sid}", json={})
    assert activated.status_code == 200, activated.text

    db.expire_all()
    problem = load_problem(db, sid)
    first_id = rules_env["assignment"]["id"]
    assert (1, 2) in problem.rule_constraints.hard_forbidden[first_id]
    assert (1, 2) not in problem.rule_constraints.hard_forbidden.get(second_assignment["id"], set())


def test_non_periodic_template_rejects_week_pattern(rules_env):
    client = rules_env["client"]
    sid = rules_env["semester"]["id"]
    body = _global_blackout()
    body["timing"]["week_pattern"] = "odd"
    response = client.post(f"/api/scheduling-rules?semester_id={sid}", json=body)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "week_pattern_not_supported"


def test_active_hard_rule_changes_solver_candidate_domain(rules_env):
    client = rules_env["client"]
    db = rules_env["db"]
    sid = rules_env["semester"]["id"]
    assignment_id = rules_env["assignment"]["id"]

    assert (
        client.post(f"/api/scheduling-rules?semester_id={sid}", json=_global_blackout()).status_code
        == 201
    )
    assert (
        client.post(f"/api/scheduling-rules/activate?semester_id={sid}", json={}).status_code == 200
    )

    db.expire_all()
    problem = load_problem(db, sid)
    assert problem.rule_revision_id is not None
    assert (1, 2) in problem.rule_constraints.hard_forbidden[assignment_id]

    result = solve(
        problem,
        SolveOptions(max_seconds=30, workers=1, random_seed=1),
        config=SolverConfig.hard_only(),
    )
    assert result.solved
    assert not validate(problem, result.entries)
    assert all((entry.weekday, entry.period_no) != (1, 2) for entry in result.entries)


def test_relaxing_teacher_availability_keeps_custom_hard_rules(rules_env):
    client = rules_env["client"]
    db = rules_env["db"]
    sid = rules_env["semester"]["id"]

    body = {
        "name": "体育只排周一前两节",
        "template": "time_window",
        "target": {"entity_type": "assignment", "ids": [rules_env["assignment"]["id"]]},
        "timing": {"weekdays": [1], "period_nos": [2, 3]},
        "operator": "allow",
        "strength": "hard",
        "priority": "high",
        "source_text": "部分排课也不能绕过这条规则",
        "enabled": True,
    }
    assert client.post(f"/api/scheduling-rules?semester_id={sid}", json=body).status_code == 201
    assert (
        client.post(f"/api/scheduling-rules/activate?semester_id={sid}", json={}).status_code == 200
    )

    db.expire_all()
    problem = load_problem(db, sid)
    result = solve(
        problem,
        SolveOptions(max_seconds=30, workers=1, random_seed=1),
        config=SolverConfig.hard_only(),
        relax=Relaxation(soft_codes=frozenset({"H4"})),
    )

    assert result.solved
    assert not result.unscheduled
    assert {(entry.weekday, entry.period_no) for entry in result.entries} == {(1, 2), (1, 3)}
    assert not validate(problem, result.entries)


def test_time_window_and_teacher_preference_compile_to_assignment_rules(rules_env):
    client = rules_env["client"]
    db = rules_env["db"]
    sid = rules_env["semester"]["id"]
    assignment_id = rules_env["assignment"]["id"]

    window = {
        "name": "体育从第三节开始",
        "template": "time_window",
        "target": {"entity_type": "subject", "ids": [rules_env["subject"]["id"]]},
        "timing": {"weekdays": [1, 2, 3, 4, 5], "period_nos": [4, 5, 7, 8, 9]},
        "operator": "allow",
        "strength": "hard",
        "priority": "high",
        "source_text": "体育课一般从第三节开始",
        "enabled": True,
    }
    teacher_preference = {
        "name": "刘老师周五下午尽量空课",
        "template": "teacher_availability",
        "target": {"entity_type": "teacher", "ids": [rules_env["teacher"]["id"]]},
        "timing": {"weekdays": [5], "period_nos": [7, 8, 9]},
        "operator": "avoid",
        "strength": "soft",
        "priority": "medium",
        "source_text": "刘老师周五下午教研",
        "enabled": True,
    }
    assert client.post(f"/api/scheduling-rules?semester_id={sid}", json=window).status_code == 201
    assert (
        client.post(f"/api/scheduling-rules?semester_id={sid}", json=teacher_preference).status_code
        == 201
    )
    assert (
        client.post(f"/api/scheduling-rules/activate?semester_id={sid}", json={}).status_code == 200
    )

    db.expire_all()
    problem = load_problem(db, sid)
    assert {(1, 2), (1, 3)} <= problem.rule_constraints.hard_forbidden[assignment_id]
    assert len(problem.rule_constraints.soft_rules) == 1
    soft = problem.rule_constraints.soft_rules[0]
    assert soft.assignment_ids == frozenset({assignment_id})
    assert soft.penalty_cells[assignment_id] == frozenset({(5, 7), (5, 8), (5, 9)})


def test_timetable_pins_rule_revision_and_manual_placement_uses_it(rules_env):
    client = rules_env["client"]
    db = rules_env["db"]
    sid = rules_env["semester"]["id"]
    assignment_id = rules_env["assignment"]["id"]

    created = client.post(
        f"/api/scheduling-rules?semester_id={sid}", json=_global_blackout()
    ).json()
    active_v1 = client.post(f"/api/scheduling-rules/activate?semester_id={sid}", json={}).json()[
        "active_revision"
    ]
    timetable = client.post(
        f"/api/timetables?semester_id={sid}", json={"name": "按 v1 排课"}
    ).json()
    assert timetable["rule_revision_id"] == active_v1["id"]

    blocked = client.post(
        f"/api/timetables/{timetable['id']}/check-conflict",
        json={
            "course_assignment_id": assignment_id,
            "weekday": 1,
            "period_no": 2,
            "span": 1,
        },
    ).json()
    assert blocked["ok"] is False
    assert blocked["conflicts"][0]["code"] == "R1"

    changed = _global_blackout("行政会调整为周二第一节")
    changed["timing"]["weekdays"] = [2]
    assert (
        client.put(
            f"/api/scheduling-rules/{created['rule_key']}?semester_id={sid}", json=changed
        ).status_code
        == 200
    )
    active_v2 = client.post(f"/api/scheduling-rules/activate?semester_id={sid}", json={}).json()[
        "active_revision"
    ]
    assert active_v2["revision_no"] == 2

    db.expire_all()
    timetable_row = db.get(Timetable, timetable["id"])
    assert timetable_row is not None
    v1_problem = load_problem(db, sid, timetable_row)
    current_problem = load_problem(db, sid)
    assert (1, 2) in v1_problem.rule_constraints.hard_forbidden[assignment_id]
    assert (2, 2) not in v1_problem.rule_constraints.hard_forbidden[assignment_id]
    assert (2, 2) in current_problem.rule_constraints.hard_forbidden[assignment_id]


def test_timetable_created_without_rules_stays_on_the_empty_snapshot(rules_env):
    client = rules_env["client"]
    db = rules_env["db"]
    sid = rules_env["semester"]["id"]
    assignment_id = rules_env["assignment"]["id"]

    timetable = client.post(
        f"/api/timetables?semester_id={sid}", json={"name": "无规则快照"}
    ).json()
    assert timetable["rule_revision_id"] is None

    assert (
        client.post(f"/api/scheduling-rules?semester_id={sid}", json=_global_blackout()).status_code
        == 201
    )
    assert (
        client.post(f"/api/scheduling-rules/activate?semester_id={sid}", json={}).status_code == 200
    )

    placement = client.post(
        f"/api/timetables/{timetable['id']}/check-conflict",
        json={
            "course_assignment_id": assignment_id,
            "weekday": 1,
            "period_no": 2,
            "span": 1,
        },
    ).json()
    assert placement["ok"] is True

    db.expire_all()
    timetable_row = db.get(Timetable, timetable["id"])
    assert timetable_row is not None
    problem = load_problem(db, sid, timetable_row)
    assert problem.rule_revision_id is None
    assert problem.rule_constraints.hard_forbidden == {}
