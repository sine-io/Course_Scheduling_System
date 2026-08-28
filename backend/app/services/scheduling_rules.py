"""规则目录、版本草稿与纯规则编译器。

该模块负责 ORM 到 solver 领域对象的最后一跳，但不把数据库对象带入
``app.solver``。规则模板是显式白名单；新增模板必须同时补上校验和编译逻辑。
"""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment import CourseAssignment, SchedulingUnit, SchedulingUnitMember
from app.models.basedata import ClassUnit, Subject, Teacher
from app.models.period import Period, PeriodTable, PeriodType
from app.models.scheduling_rule import (
    RuleRevisionStatus,
    SchedulingRule,
    SchedulingRuleRevision,
    SchedulingRuleSet,
)
from app.models.semester import Semester
from app.solver.problem import (
    AssignmentSpec,
    CompiledSoftRule,
    Problem,
    RuleConstraints,
    Slot,
)


@dataclass(frozen=True, slots=True)
class TemplateDefinition:
    key: str
    label: str
    description: str
    supported: bool
    target_types: tuple[str, ...]
    operators: tuple[str, ...]
    strengths: tuple[str, ...]
    unavailable_reason: str | None = None


TEMPLATES: tuple[TemplateDefinition, ...] = (
    TemplateDefinition(
        "global_blackout",
        "全校禁排",
        "保留全校会议、活动或公共时段",
        True,
        ("school",),
        ("forbid",),
        ("hard",),
    ),
    TemplateDefinition(
        "teacher_availability",
        "教师时段",
        "不可用、避开或偏好某些课位",
        True,
        ("teacher",),
        ("forbid", "avoid", "prefer"),
        ("hard", "soft"),
    ),
    TemplateDefinition(
        "time_window",
        "时段窗口",
        "把年级、班级或科目限制在时间范围内",
        True,
        ("grade", "class", "subject", "assignment"),
        ("allow", "forbid"),
        ("hard", "soft"),
    ),
    TemplateDefinition(
        "fixed_placement",
        "固定课位",
        "将课程固定在指定日期和节次",
        True,
        ("assignment",),
        ("allow",),
        ("hard",),
    ),
    TemplateDefinition(
        "load_limit",
        "课时上下限",
        "设置每日或每周的数量边界",
        False,
        ("grade", "class", "subject", "teacher", "assignment"),
        ("at_most", "at_least", "exactly"),
        ("hard", "soft"),
        "首版暂沿用教学任务和求解器参数，尚未开放通用数量边界",
    ),
    TemplateDefinition(
        "block_sequence",
        "连堂与间隔",
        "控制连续节数、间隔或不连堂",
        False,
        ("assignment", "subject"),
        ("allow", "forbid", "prefer"),
        ("hard", "soft"),
        "连堂结构请在教学任务中维护，通用间隔规则尚未开放",
    ),
    TemplateDefinition(
        "distribution",
        "跨日分布",
        "控制一周内的上课天数和分布",
        False,
        ("class", "subject", "assignment"),
        ("prefer", "forbid"),
        ("soft",),
        "首版尚未将自定义跨日分布编译进目标函数",
    ),
    TemplateDefinition(
        "relation",
        "同时与错开",
        "表达同步、互斥和简单顺序",
        False,
        ("teacher", "class", "assignment"),
        ("together", "apart"),
        ("hard", "soft"),
        "跨对象关系需要周次和关系变量，首版暂不支持",
    ),
    TemplateDefinition(
        "resource",
        "教室资源",
        "约束设备、容量和可用数量",
        False,
        ("room", "subject", "assignment"),
        ("require", "forbid"),
        ("hard", "soft"),
        "教室类型和互斥沿用教学任务配置，资源规则编辑尚未开放",
    ),
    TemplateDefinition(
        "periodic",
        "单双周",
        "按周次切换课程安排",
        False,
        ("assignment",),
        ("allow", "forbid"),
        ("hard", "soft", "informational"),
        "求解器尚未建模周次维度，不能激活单双周规则",
    ),
)

TEMPLATE_BY_KEY = {item.key: item for item in TEMPLATES}
PRIORITY_WEIGHT = {"high": 8, "medium": 4, "low": 1}


class SchedulingRuleError(ValueError):
    """可安全转换为规则 API 4xx 的领域错误。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def template_catalog() -> list[TemplateDefinition]:
    return list(TEMPLATES)


def allowed_strengths(definition: TemplateDefinition, operator: str) -> tuple[str, ...]:
    """Return strengths that preserve the operator's business meaning."""
    if operator in {"avoid", "prefer"}:
        return ("soft",)
    return definition.strengths


def _template(rule: SchedulingRule) -> TemplateDefinition:
    return TEMPLATE_BY_KEY.get(
        rule.template,
        TemplateDefinition(
            rule.template,
            rule.template,
            "未知规则模板",
            False,
            (),
            (),
            (),
            "系统没有该模板的编译器",
        ),
    )


def _get_rule_set(
    db: Session,
    semester_id: int,
    *,
    create: bool,
    lock: bool = False,
) -> SchedulingRuleSet | None:
    statement = select(SchedulingRuleSet).where(SchedulingRuleSet.semester_id == semester_id)
    if lock:
        statement = statement.with_for_update()
    result = db.scalar(statement)
    if result is None and create:
        if db.get(Semester, semester_id) is None:
            raise SchedulingRuleError("semester_not_found", "找不到学期")
        result = SchedulingRuleSet(semester_id=semester_id)
        db.add(result)
        db.flush()
    return result


def _active_revision(rule_set: SchedulingRuleSet | None) -> SchedulingRuleRevision | None:
    if rule_set is None or rule_set.active_revision_no is None:
        return None
    revision = next(
        (r for r in rule_set.revisions if r.revision_no == rule_set.active_revision_no), None
    )
    if revision is None or revision.status != RuleRevisionStatus.active.value:
        raise SchedulingRuleError("rule_revision_invalid", "规则集的当前激活版本指针无效")
    return revision


def _draft_revision(rule_set: SchedulingRuleSet | None) -> SchedulingRuleRevision | None:
    if rule_set is None:
        return None
    return next((r for r in rule_set.revisions if r.status == RuleRevisionStatus.draft.value), None)


def _next_revision_no(rule_set: SchedulingRuleSet) -> int:
    return max((r.revision_no for r in rule_set.revisions), default=0) + 1


def _clone_active_to_draft(
    db: Session,
    rule_set: SchedulingRuleSet,
    *,
    user_id: int | None,
    username: str,
) -> SchedulingRuleRevision:
    draft = _draft_revision(rule_set)
    if draft is not None:
        return draft
    active = _active_revision(rule_set)
    draft = SchedulingRuleRevision(
        rule_set=rule_set,
        revision_no=_next_revision_no(rule_set),
        status=RuleRevisionStatus.draft.value,
        created_by_user_id=user_id,
        created_by_name=username,
    )
    db.add(draft)
    db.flush()
    if active is not None:
        for old in active.rules:
            db.add(
                SchedulingRule(
                    revision_id=draft.id,
                    rule_key=old.rule_key,
                    name=old.name,
                    template=old.template,
                    target=dict(old.target),
                    timing=dict(old.timing),
                    operator=old.operator,
                    strength=old.strength,
                    priority=old.priority,
                    source_kind=old.source_kind,
                    source_text=old.source_text,
                    enabled=old.enabled,
                    compiler_version=old.compiler_version,
                )
            )
        db.flush()
    return draft


def ensure_draft(
    db: Session,
    semester_id: int,
    *,
    user_id: int | None,
    username: str,
) -> SchedulingRuleRevision:
    rule_set = _get_rule_set(db, semester_id, create=True, lock=True)
    assert rule_set is not None
    return _clone_active_to_draft(db, rule_set, user_id=user_id, username=username)


def _rule_row(db: Session, semester_id: int, rule: SchedulingRule) -> dict:
    definition = _template(rule)
    if not rule.enabled:
        compiler_status = "已停用"
    elif definition.supported:
        compiler_status = "已支持"
    else:
        compiler_status = "暂不支持"
    status = (
        "disabled"
        if not rule.enabled
        else "unsupported"
        if not definition.supported
        else rule.revision.status
    )
    return {
        "id": rule.id,
        "rule_key": rule.rule_key,
        "revision_id": rule.revision_id,
        "name": rule.name,
        "template": rule.template,
        "template_label": definition.label,
        "target": rule.target,
        "timing": rule.timing,
        "operator": rule.operator,
        "strength": rule.strength,
        "priority": rule.priority,
        "source_kind": rule.source_kind,
        "source_text": rule.source_text,
        "enabled": rule.enabled,
        "status": status,
        "compiler_version": rule.compiler_version,
        "compiler_status": compiler_status,
        "summary": summarize(db, semester_id, rule),
    }


def _revision_row(revision: SchedulingRuleRevision | None) -> dict | None:
    if revision is None:
        return None
    return {
        "id": revision.id,
        "revision_no": revision.revision_no,
        "status": revision.status,
        "note": revision.note,
        "created_by_name": revision.created_by_name,
        "created_at": revision.created_at,
        "activated_at": revision.activated_at,
    }


def builtin_rules() -> list[dict]:
    return [
        {
            "rule_key": "builtin-h1",
            "name": "班级同一时段不重复上课",
            "summary": "同一班级同一教学时段最多安排一门课",
            "strength": "hard",
            "source_kind": "builtin",
            "status": "active",
        },
        {
            "rule_key": "builtin-h2",
            "name": "教师同一时段不重复上课",
            "summary": "同一教师同一教学时段最多安排一门课",
            "strength": "hard",
            "source_kind": "builtin",
            "status": "active",
        },
        {
            "rule_key": "builtin-h3",
            "name": "教室与场地同一时段不冲突",
            "summary": "同一教室或场地同一教学时段最多服务一门课",
            "strength": "hard",
            "source_kind": "builtin",
            "status": "active",
        },
        {
            "rule_key": "builtin-h8",
            "name": "教学任务周课时守恒",
            "summary": "每项教学任务按设置的每周课时完整排入课表",
            "strength": "hard",
            "source_kind": "builtin",
            "status": "active",
        },
        {
            "rule_key": "builtin-s5",
            "name": "主科优先上午",
            "summary": "标记为主科的课程尽量安排在上午",
            "strength": "soft",
            "source_kind": "builtin",
            "status": "active",
        },
    ]


def options(db: Session, semester_id: int) -> dict:
    subjects = db.scalars(
        select(Subject).where(Subject.semester_id == semester_id).order_by(Subject.name, Subject.id)
    ).all()
    teachers = db.scalars(
        select(Teacher).where(Teacher.semester_id == semester_id).order_by(Teacher.name, Teacher.id)
    ).all()
    classes = db.scalars(
        select(ClassUnit)
        .where(ClassUnit.semester_id == semester_id)
        .order_by(ClassUnit.grade, ClassUnit.name)
    ).all()
    assignments = db.scalars(
        select(CourseAssignment)
        .where(CourseAssignment.semester_id == semester_id)
        .order_by(CourseAssignment.id)
    ).all()
    tables = db.scalars(
        select(PeriodTable).where(PeriodTable.semester_id == semester_id).order_by(PeriodTable.id)
    ).all()
    table_out = []
    for table in tables:
        periods = db.scalars(
            select(Period)
            .where(Period.period_table_id == table.id, Period.type == PeriodType.regular.value)
            .order_by(Period.weekday, Period.period_no)
        ).all()
        table_out.append(
            {
                "id": table.id,
                "name": table.name,
                "num_weekdays": table.num_weekdays,
                "slots": [
                    {"weekday": p.weekday, "period_no": p.period_no, "name": p.name, "type": p.type}
                    for p in periods
                ],
            }
        )
    grade_values = sorted({c.grade for c in classes})
    return {
        "subjects": [{"id": s.id, "name": s.name} for s in subjects],
        "teachers": [{"id": t.id, "name": t.name} for t in teachers],
        "classes": [{"id": c.id, "name": c.name, "grade": c.grade} for c in classes],
        "grades": [{"id": grade, "name": f"{grade}年级"} for grade in grade_values],
        "assignments": [
            {"id": a.id, "name": a.subject.name, "periods_per_week": a.periods_per_week}
            for a in assignments
        ],
        "period_tables": table_out,
    }


def workspace(db: Session, semester_id: int) -> dict:
    if db.get(Semester, semester_id) is None:
        raise SchedulingRuleError("semester_not_found", "找不到学期")
    rule_set = _get_rule_set(db, semester_id, create=False)
    active = _active_revision(rule_set)
    draft = _draft_revision(rule_set)
    visible = draft or active
    return {
        "semester_id": semester_id,
        "active_revision": _revision_row(active),
        "draft_revision": _revision_row(draft),
        "rules": [_rule_row(db, semester_id, rule) for rule in visible.rules] if visible else [],
        "builtin_rules": builtin_rules(),
        "options": options(db, semester_id),
    }


def _validate_target(
    db: Session, semester_id: int, target: dict
) -> tuple[list[CourseAssignment], str | None]:
    entity = target.get("entity_type")
    ids = {int(item) for item in target.get("ids", [])}
    assignments = db.scalars(
        select(CourseAssignment).where(CourseAssignment.semester_id == semester_id)
    ).all()
    members: dict[int, set[int]] = {}
    for unit_id, class_id in db.execute(
        select(SchedulingUnitMember.scheduling_unit_id, SchedulingUnitMember.class_unit_id)
        .join(SchedulingUnit, SchedulingUnit.id == SchedulingUnitMember.scheduling_unit_id)
        .where(SchedulingUnit.semester_id == semester_id)
    ):
        members.setdefault(unit_id, set()).add(class_id)
    classes = {
        c.id: c for c in db.scalars(select(ClassUnit).where(ClassUnit.semester_id == semester_id))
    }
    if entity == "school":
        return list(assignments), None
    if not ids:
        return [], "规则必须至少选择一个目标对象"
    if entity == "assignment":
        valid_ids = {assignment.id for assignment in assignments}
        found = [a for a in assignments if a.id in ids]
        return found, None if ids <= valid_ids else "存在不属于本学期的教学任务"
    if entity == "subject":
        valid_ids = set(db.scalars(select(Subject.id).where(Subject.semester_id == semester_id)))
        found = [a for a in assignments if a.subject_id in ids]
        return found, None if ids <= valid_ids else "存在不属于本学期的科目"
    if entity in {"teacher", "teacher_group"}:
        valid_ids = set(db.scalars(select(Teacher.id).where(Teacher.semester_id == semester_id)))
        found = [a for a in assignments if ids.intersection(at.teacher_id for at in a.teachers)]
        return found, None if ids <= valid_ids else "存在不属于本学期的教师"
    if entity in {"class", "grade"}:
        valid_grades = {item.grade for item in classes.values()}
        if entity == "grade" and not ids <= valid_grades:
            return [], "存在不属于本学期的年级"
        selected_classes = {
            cid
            for cid, item in classes.items()
            if (cid in ids if entity == "class" else item.grade in ids)
        }
        if entity == "class" and selected_classes != ids:
            return [], "存在不属于本学期的班级"
        found = [
            assignment
            for assignment in assignments
            if selected_classes.intersection(members.get(assignment.scheduling_unit_id, set()))
        ]
        return found, None
    if entity in {"room", "resource"}:
        return [], "首版暂不支持教室资源规则"
    return [], f"未知的规则对象类型:{entity}"


def _timing_cells(
    rule: SchedulingRule, problem: Problem, assignment: AssignmentSpec
) -> set[tuple[int, int]] | None:
    timing = rule.timing or {}
    weekdays = {int(day) for day in timing.get("weekdays", [])}
    period_nos = {int(period) for period in timing.get("period_nos", [])}
    table_ids = {int(table_id) for table_id in timing.get("period_table_ids", [])}
    table = problem.table_of(assignment)
    if table is None or (table_ids and table.id not in table_ids):
        # A table-scoped rule does not apply to assignments using another table.
        # Keep that distinct from an applicable rule whose filters match no slots.
        return None if table is not None and table_ids else set()
    return {
        slot.key
        for slot in table.slots
        if (not weekdays or slot.weekday in weekdays)
        and (not period_nos or slot.period_no in period_nos)
    }


def _all_cells(problem: Problem, assignment: AssignmentSpec) -> set[tuple[int, int]]:
    table = problem.table_of(assignment)
    return {slot.key for slot in table.slots} if table is not None else set()


def _lesson_lengths(assignment: AssignmentSpec) -> Counter[int]:
    lengths: list[int] = []
    for block in assignment.blocks:
        lengths.extend([block.size] * block.count)
    lengths.extend([1] * (assignment.periods_per_week - assignment.block_periods))
    return Counter(lengths)


def _non_overlapping_candidate_count(
    problem: Problem,
    assignments: list[AssignmentSpec],
    length: int,
    compiled: RuleConstraints,
) -> int:
    table = problem.table_of(assignments[0])
    if table is None:
        return 0
    forbidden = set().union(
        *(compiled.hard_forbidden.get(item.id, frozenset()) for item in assignments)
    )
    restrictions = [
        compiled.hard_allowed_starts[item.id]
        for item in assignments
        if item.id in compiled.hard_allowed_starts
    ]
    allowed_starts: set[tuple[int, int]] | None = None
    if restrictions:
        allowed_starts = set(restrictions[0])
        for restriction_cells in restrictions[1:]:
            allowed_starts.intersection_update(restriction_cells)

    runs: list[list[Slot]] = []
    current: list[Slot] = []
    for slot in table.slots:
        if (
            current
            and current[-1].weekday == slot.weekday
            and current[-1].period_no + 1 == slot.period_no
        ):
            current.append(slot)
        else:
            if current:
                runs.append(current)
            current = [slot]
    if current:
        runs.append(current)

    intervals_by_day: dict[int, list[tuple[int, int]]] = {}
    for run in runs:
        for index in range(len(run) - length + 1):
            candidate_cells = tuple(slot.key for slot in run[index : index + length])
            if allowed_starts is not None and any(
                cell not in allowed_starts for cell in candidate_cells
            ):
                continue
            if any(cell in forbidden for cell in candidate_cells):
                continue
            intervals_by_day.setdefault(run[index].weekday, []).append(
                (run[index].period_no, run[index + length - 1].period_no)
            )

    capacity = 0
    for intervals in intervals_by_day.values():
        previous_end: int | None = None
        for start, end in sorted(intervals, key=lambda item: (item[1], item[0])):
            if previous_end is None or start > previous_end:
                capacity += 1
                previous_end = end
    return capacity


def validate_rules(db: Session, semester_id: int, problem: Problem | None = None) -> dict:
    rule_set = _get_rule_set(db, semester_id, create=False)
    revision = _draft_revision(rule_set) if rule_set else None
    if revision is None:
        return {
            "revision_id": None,
            "valid": True,
            "diagnostics": [],
            "matched_assignment_count": 0,
            "excluded_candidate_count": 0,
        }
    if problem is None:
        problem = _problem_context(db, semester_id)
    diagnostics: list[dict] = []
    matched_ids: set[int] = set()
    affected_cells: set[tuple[int, tuple[int, int]]] = set()
    for rule in revision.rules:
        if not rule.enabled:
            continue
        definition = _template(rule)
        if not definition.supported:
            diagnostics.append(
                {
                    "level": "error",
                    "code": "unsupported_template",
                    "message": definition.unavailable_reason or "规则模板暂不支持",
                    "rule_key": rule.rule_key,
                }
            )
            continue
        if rule.strength not in allowed_strengths(definition, rule.operator):
            diagnostics.append(
                {
                    "level": "error",
                    "code": "strength_not_supported",
                    "message": f"{definition.label}不支持强度 {rule.strength}",
                    "rule_key": rule.rule_key,
                }
            )
            continue
        if rule.timing.get("week_pattern") and rule.template != "periodic":
            diagnostics.append(
                {
                    "level": "error",
                    "code": "week_pattern_not_supported",
                    "message": "周次模式只能用于单双周模板",
                    "rule_key": rule.rule_key,
                }
            )
            continue
        if not rule.timing.get("weekdays") or not rule.timing.get("period_nos"):
            diagnostics.append(
                {
                    "level": "error",
                    "code": "timing_required",
                    "message": "可执行规则必须选择星期和教学节次",
                    "rule_key": rule.rule_key,
                }
            )
            continue
        if rule.target.get("entity_type") not in definition.target_types:
            diagnostics.append(
                {
                    "level": "error",
                    "code": "target_type_not_supported",
                    "message": f"{definition.label}不支持对象类型 {rule.target.get('entity_type')}",
                    "rule_key": rule.rule_key,
                }
            )
            continue
        targets, target_error = _validate_target(db, semester_id, rule.target)
        if target_error:
            diagnostics.append(
                {
                    "level": "error",
                    "code": "invalid_target",
                    "message": target_error,
                    "rule_key": rule.rule_key,
                }
            )
            continue
        if not targets:
            diagnostics.append(
                {
                    "level": "warning",
                    "code": "no_matching_assignments",
                    "message": "规则没有匹配到教学任务，激活后不会影响当前课表",
                    "rule_key": rule.rule_key,
                }
            )
            continue
        matched_ids.update(a.id for a in targets)
        resolved_any = False
        saw_applicable_table = False
        for assignment in targets:
            selected = _timing_cells(rule, problem, _assignment_spec(problem, assignment.id))
            if selected is None:
                continue
            saw_applicable_table = True
            resolved_any = resolved_any or bool(selected)
            all_cells = _all_cells(problem, _assignment_spec(problem, assignment.id))
            if rule.operator in {"forbid", "avoid"}:
                affected_cells.update((assignment.id, cell) for cell in selected)
            elif rule.operator == "allow":
                affected_cells.update((assignment.id, cell) for cell in all_cells - selected)
            elif rule.operator == "prefer":
                affected_cells.update((assignment.id, cell) for cell in selected)
        if saw_applicable_table and not resolved_any:
            diagnostics.append(
                {
                    "level": "error",
                    "code": "no_matching_slots",
                    "message": "所选星期和节次没有匹配到目标对象的作息时间表",
                    "rule_key": rule.rule_key,
                }
            )
    if not any(item["level"] == "error" for item in diagnostics):
        compiled = compile_active_rules(
            db,
            semester_id,
            problem,
            revision_id=revision.id,
        )
        checked_courses: set[tuple[str, int]] = set()
        for assignment_spec in problem.assignments:
            course_key = problem.course_key(assignment_spec)
            if course_key in checked_courses:
                continue
            checked_courses.add(course_key)
            course = [
                item for item in problem.assignments if problem.course_key(item) == course_key
            ]
            constrained = any(
                item.id in compiled.hard_forbidden or item.id in compiled.hard_allowed_starts
                for item in course
            )
            if not constrained:
                continue
            for length, required in _lesson_lengths(course[0]).items():
                available = _non_overlapping_candidate_count(problem, course, length, compiled)
                if available >= required:
                    continue
                diagnostics.append(
                    {
                        "level": "error",
                        "code": "no_candidate_after_rules",
                        "message": (
                            f"教学任务「{course[0].subject_name}」需要 {required} 个"
                            f"{length} 节课位，当前硬规则只留下 {available} 个可用位置"
                        ),
                        "rule_key": f"course:{course_key[0]}:{course_key[1]}",
                    }
                )
    return {
        "revision_id": revision.id,
        "valid": not any(item["level"] == "error" for item in diagnostics),
        "diagnostics": diagnostics,
        "matched_assignment_count": len(matched_ids),
        "excluded_candidate_count": len(affected_cells),
    }


def _problem_context(db: Session, semester_id: int) -> Problem:
    """用于校验影响范围的轻量问题上下文；正式求解由 solver_data 构建完整 Problem。"""
    from app.services.solver_data import load_problem

    return load_problem(db, semester_id)


def _assignment_spec(problem: Problem, assignment_id: int) -> AssignmentSpec:
    return next(a for a in problem.assignments if a.id == assignment_id)


def compile_active_rules(
    db: Session,
    semester_id: int,
    problem: Problem,
    *,
    revision_id: int | None = None,
    use_active: bool = True,
) -> RuleConstraints:
    rule_set = _get_rule_set(db, semester_id, create=False)
    revision = (
        next((item for item in rule_set.revisions if item.id == revision_id), None)
        if rule_set is not None and revision_id is not None
        else _active_revision(rule_set)
        if use_active
        else None
    )
    if revision is None:
        return RuleConstraints()
    hard_forbidden: dict[int, set[tuple[int, int]]] = {}
    hard_allowed_starts: dict[int, set[tuple[int, int]]] = {}
    soft_rules: list[CompiledSoftRule] = []
    by_assignment = {a.id: a for a in problem.assignments}
    for rule in revision.rules:
        if not rule.enabled:
            continue
        definition = _template(rule)
        if (
            not definition.supported
            or rule.strength == "informational"
            or rule.strength not in allowed_strengths(definition, rule.operator)
        ):
            continue
        targets, target_error = _validate_target(db, semester_id, rule.target)
        if target_error:
            continue
        ids = [a.id for a in targets if a.id in by_assignment]
        if not ids:
            continue
        for assignment_id in ids:
            assignment = by_assignment[assignment_id]
            selected = _timing_cells(rule, problem, assignment)
            if selected is None:
                continue
            all_cells = _all_cells(problem, assignment)
            if rule.template == "fixed_placement":
                if rule.strength == "hard":
                    current = hard_allowed_starts.setdefault(assignment_id, all_cells)
                    current.intersection_update(selected)
                else:
                    soft_rules.append(
                        CompiledSoftRule(
                            rule_key=rule.rule_key,
                            name=rule.name,
                            assignment_ids=frozenset({assignment_id}),
                            penalty_cells={assignment_id: frozenset(all_cells - selected)},
                            weight=PRIORITY_WEIGHT.get(rule.priority, 4),
                        )
                    )
                continue
            if rule.operator == "allow":
                if rule.strength == "hard":
                    hard_forbidden.setdefault(assignment_id, set()).update(all_cells - selected)
                else:
                    soft_rules.append(
                        CompiledSoftRule(
                            rule_key=rule.rule_key,
                            name=rule.name,
                            assignment_ids=frozenset({assignment_id}),
                            penalty_cells={assignment_id: frozenset(all_cells - selected)},
                            weight=PRIORITY_WEIGHT.get(rule.priority, 4),
                        )
                    )
                continue
            if rule.operator in {"forbid", "unavailable"}:
                if rule.strength == "hard":
                    hard_forbidden.setdefault(assignment_id, set()).update(selected)
                else:
                    soft_rules.append(
                        CompiledSoftRule(
                            rule_key=rule.rule_key,
                            name=rule.name,
                            assignment_ids=frozenset({assignment_id}),
                            penalty_cells={assignment_id: frozenset(selected)},
                            weight=PRIORITY_WEIGHT.get(rule.priority, 4),
                        )
                    )
            elif rule.operator == "avoid":
                soft_rules.append(
                    CompiledSoftRule(
                        rule_key=rule.rule_key,
                        name=rule.name,
                        assignment_ids=frozenset({assignment_id}),
                        penalty_cells={assignment_id: frozenset(selected)},
                        weight=PRIORITY_WEIGHT.get(rule.priority, 4),
                    )
                )
            elif rule.operator == "prefer":
                soft_rules.append(
                    CompiledSoftRule(
                        rule_key=rule.rule_key,
                        name=rule.name,
                        assignment_ids=frozenset({assignment_id}),
                        penalty_cells={assignment_id: frozenset(selected)},
                        weight=PRIORITY_WEIGHT.get(rule.priority, 4),
                        penalize_occupied=False,
                    )
                )
    return RuleConstraints(
        revision_id=revision.id,
        hard_forbidden={key: frozenset(value) for key, value in hard_forbidden.items()},
        hard_allowed_starts={key: frozenset(value) for key, value in hard_allowed_starts.items()},
        soft_rules=tuple(soft_rules),
    )


def active_revision_id(db: Session, semester_id: int) -> int | None:
    revision = _active_revision(_get_rule_set(db, semester_id, create=False))
    return revision.id if revision is not None else None


def hard_placement_conflicts(
    db: Session,
    semester_id: int,
    revision_id: int | None,
    assignment: CourseAssignment,
    *,
    table_id: int,
    weekday: int,
    period_nos: list[int],
) -> list[str]:
    """复用已固定修订，检查一次手工放课是否违反自定义硬规则。

    这是手排热路径的窄查询版本，不为一次拖拽加载整个 ``Problem``。
    """
    if revision_id is None:
        return []
    rule_set = _get_rule_set(db, semester_id, create=False)
    revision = (
        next((item for item in rule_set.revisions if item.id == revision_id), None)
        if rule_set is not None and revision_id is not None
        else None
    )
    if revision is None:
        return []

    teacher_ids = {item.teacher_id for item in assignment.teachers}
    class_rows = [member.class_unit for member in assignment.scheduling_unit.members]
    class_ids = {item.id for item in class_rows}
    grades = {item.grade for item in class_rows}
    conflicts: list[str] = []
    for rule in revision.rules:
        if not rule.enabled or rule.strength != "hard" or not _template(rule).supported:
            continue
        entity = rule.target.get("entity_type")
        ids = {int(item) for item in rule.target.get("ids", [])}
        matches = (
            entity == "school"
            or (entity == "assignment" and assignment.id in ids)
            or (entity == "subject" and assignment.subject_id in ids)
            or (entity in {"teacher", "teacher_group"} and bool(ids & teacher_ids))
            or (entity == "class" and bool(ids & class_ids))
            or (entity == "grade" and bool(ids & grades))
        )
        if not matches:
            continue
        table_ids = {int(item) for item in rule.timing.get("period_table_ids", [])}
        if table_ids and table_id not in table_ids:
            continue
        weekdays = {int(item) for item in rule.timing.get("weekdays", [])}
        selected_periods = {int(item) for item in rule.timing.get("period_nos", [])}
        day_selected = not weekdays or weekday in weekdays
        covered_selected = day_selected and any(
            period_no in selected_periods for period_no in period_nos
        )
        covered_inside = day_selected and all(
            period_no in selected_periods for period_no in period_nos
        )
        violates = (
            rule.operator == "forbid"
            and covered_selected
            or rule.template == "fixed_placement"
            and not covered_inside
            or rule.template != "fixed_placement"
            and rule.operator == "allow"
            and not covered_inside
        )
        if violates:
            conflicts.append(rule.name)
    return conflicts


def summarize(db: Session, semester_id: int, rule: SchedulingRule) -> str:
    entity = rule.target.get("entity_type", "对象")
    entity_label = {
        "school": "全校",
        "teacher": "教师",
        "teacher_group": "教师组",
        "subject": "科目",
        "class": "班级",
        "grade": "年级",
        "assignment": "教学任务",
    }.get(entity, entity)
    days = rule.timing.get("weekdays", []) if rule.timing else []
    periods = rule.timing.get("period_nos", []) if rule.timing else []
    day_names = ["一", "二", "三", "四", "五", "六", "日"]
    day_text = "、".join(f"周{day_names[day - 1]}" for day in days if 1 <= day <= 7)
    selected_tables = set(rule.timing.get("period_table_ids", [])) if rule.timing else set()
    table = db.scalar(
        select(PeriodTable)
        .where(
            PeriodTable.semester_id == semester_id,
            *([PeriodTable.id.in_(selected_tables)] if selected_tables else []),
        )
        .order_by(PeriodTable.is_default.desc(), PeriodTable.id)
    )
    ordinal_by_period: dict[int, int] = {}
    if table is not None:
        regular = db.scalars(
            select(Period)
            .where(
                Period.period_table_id == table.id,
                Period.type == PeriodType.regular.value,
            )
            .order_by(Period.weekday, Period.period_no)
        ).all()
        first_day = min((p.weekday for p in regular), default=1)
        ordinal_by_period = {
            period.period_no: index
            for index, period in enumerate((p for p in regular if p.weekday == first_day), start=1)
        }
    period_text = "、".join(str(ordinal_by_period.get(p, p)) for p in periods)
    timing = "".join(
        part for part in (day_text, f"第{period_text}节" if period_text else "") if part
    )
    verb = {
        "forbid": "禁排",
        "unavailable": "禁排",
        "allow": "限于",
        "avoid": "尽量避开",
        "prefer": "优先安排",
    }.get(rule.operator, rule.operator)
    suffix = f"{timing}" if timing else "指定时段"
    return f"{entity_label}在{suffix}{verb}"


def rule_out(db: Session, semester_id: int, rule: SchedulingRule) -> dict:
    return _rule_row(db, semester_id, rule)


def create_rule(
    db: Session,
    semester_id: int,
    body: dict,
    *,
    user_id: int | None,
    username: str,
    rule_key: str | None = None,
) -> SchedulingRule:
    definition = TEMPLATE_BY_KEY.get(body["template"])
    if definition is None:
        raise SchedulingRuleError("unknown_template", "未知的规则模板")
    if body["target"]["entity_type"] not in definition.target_types:
        raise SchedulingRuleError(
            "target_type_not_supported", f"{definition.label}不支持该对象类型"
        )
    if body["operator"] not in definition.operators:
        raise SchedulingRuleError("operator_not_supported", f"{definition.label}不支持该操作")
    if body["strength"] not in allowed_strengths(definition, body["operator"]):
        raise SchedulingRuleError("strength_not_supported", f"{definition.label}不支持该强度")
    if body["timing"].get("week_pattern") and body["template"] != "periodic":
        raise SchedulingRuleError("week_pattern_not_supported", "周次模式只能用于单双周模板")
    revision = ensure_draft(db, semester_id, user_id=user_id, username=username)
    key = rule_key or uuid4().hex
    row = next((item for item in revision.rules if item.rule_key == key), None)
    if row is None:
        if rule_key is not None:
            raise SchedulingRuleError("rule_not_found", "找不到规则")
        row = SchedulingRule(revision_id=revision.id, rule_key=key)
        db.add(row)
    row.name = body["name"].strip()
    row.template = body["template"]
    row.target = body["target"].copy()
    row.timing = body["timing"].copy()
    row.operator = body["operator"]
    row.strength = body["strength"]
    row.priority = body["priority"]
    row.source_kind = "custom"
    row.source_text = body.get("source_text", "").strip()
    row.enabled = body.get("enabled", True)
    row.compiler_version = "rules-v1"
    db.flush()
    return row


def delete_rule(
    db: Session, semester_id: int, rule_key: str, *, user_id: int | None, username: str
) -> None:
    revision = ensure_draft(db, semester_id, user_id=user_id, username=username)
    row = next((item for item in revision.rules if item.rule_key == rule_key), None)
    if row is None:
        raise SchedulingRuleError("rule_not_found", "找不到规则")
    # Keep the draft's source and structure as an auditable tombstone. The
    # next activated revision will ignore it, while history can still explain
    # which rule was intentionally stopped.
    row.enabled = False
    db.flush()


def activate(
    db: Session,
    semester_id: int,
    *,
    user_id: int | None,
    username: str,
    note: str,
) -> SchedulingRuleRevision:
    rule_set = _get_rule_set(db, semester_id, create=False, lock=True)
    revision = _draft_revision(rule_set)
    if rule_set is None or revision is None:
        raise SchedulingRuleError("no_draft", "当前没有可激活的规则草稿")
    report = validate_rules(db, semester_id)
    if not report["valid"]:
        raise SchedulingRuleError("rule_revision_invalid", "规则草稿存在不能激活的问题")
    old = _active_revision(rule_set)
    if old is not None:
        old.status = RuleRevisionStatus.superseded.value
        db.flush()
    revision.status = RuleRevisionStatus.active.value
    revision.note = note.strip()
    revision.created_by_user_id = user_id
    revision.created_by_name = username
    revision.activated_at = datetime.now(UTC)
    rule_set.active_revision_no = revision.revision_no
    db.flush()
    return revision
