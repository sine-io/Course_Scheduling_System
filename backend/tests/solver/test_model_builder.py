"""M3-2:CP-SAT 硬约束建模。

**每个解都用 `app.solver.validator` 逐项验过**(测试策略总则第 2 点)——
建模写错时 solver 会很有信心地交出违反硬约束的「可行解」,不能信它自己说的话。
"""

import time
from dataclasses import replace

import pytest

from app.models.basedata import ClassTrack, RoomType, TeacherRuleType, TeacherTimeRule
from app.services.solver_data import load_problem
from app.solver import preflight
from app.solver.model_builder import SolveOptions, SolverInputError, solve
from app.solver.problem import FixedEntry, SolverConfig
from app.solver.validator import validate
from tests.fixtures import (
    Builder,
    build_elementary_small,
    build_junior_high_mid,
    build_vocational_high,
)

FAST = SolveOptions(max_seconds=120.0, workers=4, random_seed=1)
# 这张卡验的是硬约束建模;关掉软约束目标,让求解退化为纯可行性问题(也最快)。
HARD = SolverConfig.hard_only()

BUILDERS = {
    "elementary_small": build_elementary_small,
    "junior_high_mid": build_junior_high_mid,
    "vocational_high": build_vocational_high,
}


def _solve_fixture(db, key, **kwargs):
    fx = BUILDERS[key](db)
    problem = load_problem(db, fx.semester_id, **kwargs)
    assert preflight.run(problem).ok
    result = solve(problem, FAST, config=HARD)
    return fx, problem, result


# ── 验收①:三套 fixtures 各自可解,且零硬约束违反 ──────────────
@pytest.mark.parametrize("key", list(BUILDERS))
def test_fixture_solves_with_zero_violations(key, db):
    _fx, problem, result = _solve_fixture(db, key)
    assert result.solved, f"{key} 应可解,实得 {result.status}"

    violations = validate(problem, result.entries)
    assert not violations, [v.message for v in violations[:5]]

    # 每项教学任务都排满(走班群组的每门课各自生成单元格,故总和 = 各教学任务周节数之和)
    total = sum(e.span for e in result.entries)
    assert total == sum(a.periods_per_week for a in problem.assignments)


# ── 验收②:中职的 3 连堂与实训场地 ───────────────────────────
def test_vocational_blocks_are_contiguous_and_workshops_exclusive(db):
    fx, problem, result = _solve_fixture(db, "vocational_high")
    assert result.solved
    assert not validate(problem, result.entries)

    practicum_ids = {
        a.id for a in problem.assignments if a.subject_name == "实训场地"
    }
    blocks = [e for e in result.entries if e.assignment_id in practicum_ids]
    assert len(blocks) == 30  # 15 班 × 2 个 3 连堂
    assert all(e.span == 3 for e in blocks)

    # 连堂涵盖的三节都是连续的一般课,且不跨午休
    for e in blocks:
        table = problem.table_of(next(a for a in problem.assignments if a.id == e.assignment_id))
        assert table is not None
        covered = [table.slot(e.weekday, e.period_no + k) for k in range(3)]
        assert all(s is not None for s in covered)

    # 实训场地同时段至多一班(D8 互斥)
    occupied: set[tuple[int, int, int]] = set()
    for e in blocks:
        assert e.room_id is not None
        for k in range(3):
            cell = (e.room_id, e.weekday, e.period_no + k)
            assert cell not in occupied, "同一实训室同时段排了两班"
            occupied.add(cell)

    # 企业兼职教师只在周二/周四上课
    external = next(t for t in problem.teachers.values() if t.is_external)
    his = [
        e for e in result.entries
        if external.id in next(
            a for a in problem.assignments if a.id == e.assignment_id
        ).teacher_ids
    ]
    assert his and {e.weekday for e in his} <= {2, 4}


def test_group_courses_share_the_same_slots(db):
    """H7:走班群组的 5 门选修必须同时段开课。"""
    _fx, problem, result = _solve_fixture(db, "vocational_high")
    group = next(u for u in problem.units.values() if u.is_group)
    members = [a.id for a in problem.assignments if a.unit_id == group.id]

    slots_per_member = {
        aid: sorted((e.weekday, e.period_no) for e in result.entries if e.assignment_id == aid)
        for aid in members
    }
    distinct = {tuple(v) for v in slots_per_member.values()}
    assert len(distinct) == 1, "群组内各门课的时段应完全相同"
    assert len(next(iter(distinct))) == 3  # 每周 3 节


def test_junior_high_assigns_rooms_by_type(db):
    """只指定教室/场地类型的教学任务,引擎须逐项挑出合法教室。"""
    _fx, problem, result = _solve_fixture(db, "junior_high_mid")
    art = [a for a in problem.assignments if a.subject_name == "艺术"]
    assert all(a.room_id is None and a.required_room_type == "special" for a in art)

    art_ids = {a.id for a in art}
    art_entries = [e for e in result.entries if e.assignment_id in art_ids]
    assert art_entries and all(e.room_id is not None for e in art_entries)
    chosen = {problem.rooms[e.room_id].name for e in art_entries if e.room_id}
    assert chosen <= {"音乐教室", "美术教室"}, chosen  # room_subjects 限制了候选


# ── 验收③:锁定 5 格后重解,位置不变 ─────────────────────────
def test_locked_entries_survive_resolve(db):
    fx = build_elementary_small(db)
    problem = load_problem(db, fx.semester_id)
    first = solve(problem, FAST, config=HARD)
    assert first.solved

    locked = tuple(
        FixedEntry(e.assignment_id, e.weekday, e.period_no, e.span, e.room_id, locked=True)
        for e in first.entries[:5]
    )
    # 换一颗乱数种子重解:若 H9 没建对,solver 会很乐意把这 5 格搬走
    pinned = replace(problem, fixed_entries=locked)
    second = solve(pinned, SolveOptions(max_seconds=120.0, workers=4, random_seed=99),
                   config=HARD)
    assert second.solved
    assert not validate(pinned, second.entries)

    placed = {(e.assignment_id, e.weekday, e.period_no, e.span) for e in second.entries}
    for f in locked:
        assert (f.assignment_id, f.weekday, f.period_no, f.span) in placed
    assert sum(1 for e in second.entries if e.locked) == 5


# ── 验收④:12 班初中 fixture 在 60 秒内解出 ──────────────────
def test_junior_high_solves_within_60_seconds(db):
    fx = build_junior_high_mid(db)
    problem = load_problem(db, fx.semester_id)
    started = time.perf_counter()
    result = solve(problem, SolveOptions(max_seconds=60.0, workers=4, random_seed=7),
                   config=HARD)
    elapsed = time.perf_counter() - started

    assert result.solved, f"12 班初中应在 60 秒内解出,实得 {result.status}"
    assert elapsed < 60, f"耗时 {elapsed:.1f}s"
    assert not validate(problem, result.entries)


# ── 建模的边界情形 ───────────────────────────────────────────
def test_infeasible_when_teacher_has_no_free_slot(db):
    """王师两门课 5+5 节,但只剩 4 格可排 → CP-SAT 证明无解。"""
    b = Builder(db, 2041, 1, "junior_high")
    b.teacher("王师", base_periods=40)
    b.klass("301", grade=3, track=ClassTrack.junior_high.value)
    b.assign(subject="语文", teachers=["王师"], periods=5, classes=["301"])
    b.assign(subject="数学", teachers=["王师"], periods=5, classes=["301"])
    wang = b.teachers["王师"]
    keep = {(1, 2), (1, 3), (2, 2), (2, 3)}
    for p in b.regular_slots():
        if (p.weekday, p.period_no) not in keep:
            db.add(TeacherTimeRule(teacher_id=wang.id, weekday=p.weekday,
                                   period_no=p.period_no,
                                   rule_type=TeacherRuleType.unavailable.value))
    fx = b.build()

    problem = load_problem(db, fx.semester_id)
    assert not preflight.run(problem).ok  # pre-flight 就拦下了(10 节 > 4 格)
    result = solve(problem, SolveOptions(max_seconds=30.0, workers=2), config=HARD)
    assert result.status == "infeasible"


def test_group_with_mismatched_periods_is_rejected(db):
    """走班群组同时段开课,节数不一致无法建模;pre-flight 也应拦下。"""
    b = Builder(db, 2042, 1, "junior_high")
    b.teacher("甲师", base_periods=40)
    b.teacher("乙师", base_periods=40)
    b.klass("201", grade=2, track=ClassTrack.junior_high.value)
    b.klass("202", grade=2, track=ClassTrack.junior_high.value)
    b.group("选修课程", ["201", "202"])
    b.subject("选修甲")
    b.subject("选修乙")
    b.assign(subject="选修甲", teachers=["甲师"], periods=3, group="选修课程")
    b.assign(subject="选修乙", teachers=["乙师"], periods=2, group="选修课程")
    fx = b.build()

    problem = load_problem(db, fx.semester_id)
    report = preflight.run(problem)
    issue = next(i for i in report.errors if i.code == "group_shape_mismatch")
    assert "选修课程" in issue.message

    with pytest.raises(SolverInputError, match="无法同时段开课"):
        solve(problem, SolveOptions(max_seconds=5.0), config=HARD)


def test_daily_subject_cap_counts_single_periods_only(db):
    """H10:连堂不计入每日上限,但连堂课剩下的单节仍受限。"""
    b = Builder(db, 2043, 1, "junior_high")
    b.teacher("陈师", base_periods=40)
    b.klass("301", grade=3, track=ClassTrack.junior_high.value)
    # 8 节 = 3 连堂 ×2 + 2 单节
    b.assign(subject="劳动", teachers=["陈师"], periods=8, classes=["301"], blocks=(3, 2))
    fx = b.build()

    problem = load_problem(db, fx.semester_id)
    result = solve(problem, SolveOptions(max_seconds=30.0, workers=2), config=HARD)
    assert result.solved
    assert not validate(problem, result.entries)

    spans = sorted(e.span for e in result.entries)
    assert spans == [1, 1, 3, 3]


def test_room_type_without_any_room_raises(db):
    b = Builder(db, 2044, 1, "junior_high")
    b.subject("音乐", required_room_type=RoomType.special)
    b.teacher("音乐师", base_periods=40)
    b.klass("301", grade=3, track=ClassTrack.junior_high.value)
    b.assign(subject="音乐", teachers=["音乐师"], periods=2, classes=["301"],
             required_room_type=RoomType.special)
    fx = b.build()

    problem = load_problem(db, fx.semester_id)
    with pytest.raises(SolverInputError, match="没有"):
        solve(problem, SolveOptions(max_seconds=5.0), config=HARD)
