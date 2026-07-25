"""课表硬约束验证器(architecture.md §3.2 H1–H10)。

**刻意与 `model_builder` 完全不共用代码。** 测试策略总则第 2 点:排课引擎的解统一以
本验证器逐项检查,绝不以 solver 自身报告的状态为准——建模写错时 solver 会很有信心地
交出一个违反硬约束的「可行解」。

同一支验证器日后也用于「导入外部课表 → 检查冲突」。
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.solver.problem import (
    AssignmentSpec,
    Problem,
    Slot,
    SolvedEntry,
    slots_overlap,
)

DEFAULT_DAILY_SUBJECT_CAP = 2  # H10 同班同科目每日单节上限(连堂不计)


@dataclass(frozen=True, slots=True)
class Violation:
    code: str  # H1..H10 / room_type
    message: str
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _Occurrence:
    """一个单元格在某一节次上的占用。"""

    entry: SolvedEntry
    assignment: AssignmentSpec
    table_id: int
    slot: Slot


def _wd(weekday: int) -> str:
    names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return names[weekday - 1] if 1 <= weekday <= 7 else f"星期{weekday}"


def _effective_room(problem: Problem, entry: SolvedEntry, a: AssignmentSpec) -> int | None:
    return entry.room_id if entry.room_id is not None else a.room_id


def validate(
    problem: Problem,
    entries: Sequence[SolvedEntry],
    *,
    daily_subject_cap: int = DEFAULT_DAILY_SUBJECT_CAP,
) -> tuple[Violation, ...]:
    """返回所有硬约束违反;空 tuple 表示这份课表完全合法。"""
    v: list[Violation] = []
    by_id = {a.id: a for a in problem.assignments}

    unknown = [e for e in entries if e.assignment_id not in by_id]
    if unknown:
        return (Violation("input", f"有 {len(unknown)} 个单元格指向不存在的教学任务"),)

    occurrences = _expand(problem, entries, by_id, v)
    _h1_class(problem, occurrences, v)
    _h2_teacher(problem, occurrences, v)
    _h3_room(problem, occurrences, v)
    _h4_unavailable(problem, occurrences, v)
    _h7_group_sync(problem, entries, by_id, v)
    _h8_weekly_periods(problem, entries, by_id, v)
    _h9_locked(problem, entries, v)
    _h10_daily_cap(problem, entries, by_id, daily_subject_cap, v)
    _room_type(problem, entries, by_id, v)
    return tuple(v)


def _expand(
    problem: Problem,
    entries: Sequence[SolvedEntry],
    by_id: dict[int, AssignmentSpec],
    v: list[Violation],
) -> list[_Occurrence]:
    """展开每个单元格涵盖的节次,顺带验 H5(节次有效)与 H6(连堂连续不跨午休)。"""
    out: list[_Occurrence] = []
    for e in entries:
        a = by_id[e.assignment_id]
        table = problem.table_of(a)
        if table is None:
            v.append(
                Violation(
                    "H5",
                    f"教学任务「{a.subject_name}」无作息时间表",
                    {"assignment_id": a.id},
                )
            )
            continue
        for k in range(e.span):
            slot = table.slot(e.weekday, e.period_no + k)
            if slot is None:
                code = "H6" if e.span > 1 else "H5"
                reason = (
                    f"{e.span} 连堂涵盖的第 {k + 1} 节不是连续的一般课(跨越午休或不存在)"
                    if e.span > 1
                    else "不是一般上课节次"
                )
                v.append(Violation(
                    code,
                    f"「{a.subject_name}」{_wd(e.weekday)}第 {e.period_no + k} 格{reason}",
                    {"assignment_id": a.id, "weekday": e.weekday, "period_no": e.period_no + k},
                ))
                continue
            out.append(_Occurrence(e, a, table.id, slot))
    return out


def _h1_class(problem: Problem, occ: list[_Occurrence], v: list[Violation]) -> None:
    """班级同时段至多一门课。走班群组同进同出,整组只占班级一格。"""
    seen: dict[tuple[int, int, int], set[tuple[str, int]]] = {}
    for o in occ:
        key_course = problem.course_key(o.assignment)
        for cls in problem.classes_of(o.assignment):
            key = (cls.id, o.slot.weekday, o.slot.period_no)
            courses = seen.setdefault(key, set())
            courses.add(key_course)
            if len(courses) > 1:
                v.append(Violation(
                    "H1",
                    f"班级 {cls.name} {_wd(o.slot.weekday)}{o.slot.name} 同时有多门课",
                    {"class_id": cls.id, "weekday": o.slot.weekday,
                     "period_no": o.slot.period_no},
                ))


def _pairwise_resource_clash(
    problem: Problem,
    occ: list[_Occurrence],
    resource_of,
    label: str,
    code: str,
    name_of,
    v: list[Violation],
) -> None:
    """教师和教室/场地是跨班级共用的资源:同一资源的两项占用在墙钟上重叠即冲突(D7)。"""
    buckets: dict[int, list[_Occurrence]] = {}
    for o in occ:
        for rid in resource_of(o):
            buckets.setdefault(rid, []).append(o)

    for rid, items in buckets.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if a.entry is b.entry:
                    continue
                if not slots_overlap(a.slot, b.slot, same_table=a.table_id == b.table_id):
                    continue
                v.append(Violation(
                    code,
                    f"{label} {name_of(rid)} {_wd(a.slot.weekday)}{a.slot.name} 同时有"
                    f"「{a.assignment.subject_name}」与「{b.assignment.subject_name}」",
                    {"resource_id": rid, "weekday": a.slot.weekday},
                ))


def _h2_teacher(problem: Problem, occ: list[_Occurrence], v: list[Violation]) -> None:
    _pairwise_resource_clash(
        problem, occ,
        resource_of=lambda o: o.assignment.teacher_ids,
        label="教师", code="H2",
        name_of=lambda tid: problem.teachers[tid].name,
        v=v,
    )


def _h3_room(problem: Problem, occ: list[_Occurrence], v: list[Violation]) -> None:
    def rooms(o: _Occurrence) -> tuple[int, ...]:
        rid = _effective_room(problem, o.entry, o.assignment)
        return (rid,) if rid is not None else ()

    _pairwise_resource_clash(
        problem, occ,
        resource_of=rooms, label="教室/场地", code="H3",
        name_of=lambda rid: problem.rooms[rid].name if rid in problem.rooms else str(rid),
        v=v,
    )


def _h4_unavailable(problem: Problem, occ: list[_Occurrence], v: list[Violation]) -> None:
    for o in occ:
        for tid in o.assignment.teacher_ids:
            teacher = problem.teachers.get(tid)
            if teacher and o.slot.key in teacher.unavailable:
                v.append(Violation(
                    "H4",
                    f"教师{teacher.name} {_wd(o.slot.weekday)}{o.slot.name} 为不可排时段",
                    {"teacher_id": tid, "weekday": o.slot.weekday,
                     "period_no": o.slot.period_no},
                ))


def _h7_group_sync(
    problem: Problem,
    entries: Sequence[SolvedEntry],
    by_id: dict[int, AssignmentSpec],
    v: list[Violation],
) -> None:
    """走班群组内的所有教学任务必须排在完全相同的时段。"""
    by_assignment: dict[int, set[tuple[int, int, int]]] = {}
    for e in entries:
        by_assignment.setdefault(e.assignment_id, set()).add((e.weekday, e.period_no, e.span))

    for unit in problem.units.values():
        if not unit.is_group:
            continue
        members = [a for a in problem.assignments if a.unit_id == unit.id]
        slots = {frozenset(by_assignment.get(a.id, set())) for a in members}
        if len(slots) > 1:
            v.append(Violation(
                "H7",
                f"走班群组「{unit.name}」的各门课未排在相同时段",
                {"unit_id": unit.id},
            ))


def _h8_weekly_periods(
    problem: Problem,
    entries: Sequence[SolvedEntry],
    by_id: dict[int, AssignmentSpec],
    v: list[Violation],
) -> None:
    """每项教学任务排入的节数 = 设置的每周节数,且连堂结构符合 block_rule。"""
    spans: dict[int, list[int]] = {}
    for e in entries:
        spans.setdefault(e.assignment_id, []).append(e.span)

    for a in problem.assignments:
        got = sorted(spans.get(a.id, []), reverse=True)
        expected: list[int] = []
        for b in a.blocks:
            expected.extend([b.size] * b.count)
        expected.extend([1] * (a.periods_per_week - a.block_periods))
        expected.sort(reverse=True)
        if got != expected:
            v.append(Violation(
                "H8",
                f"「{a.subject_name}」排入 {sum(got)} 节(节长 {got or '无'}),"
                f"应为 {a.periods_per_week} 节(节长 {expected})",
                {"assignment_id": a.id, "placed": got, "expected": expected},
            ))


def _h9_locked(problem: Problem, entries: Sequence[SolvedEntry], v: list[Violation]) -> None:
    placed = {(e.assignment_id, e.weekday, e.period_no, e.span) for e in entries}
    for f in problem.fixed_entries:
        if not f.locked:
            continue
        if (f.assignment_id, f.weekday, f.period_no, f.span) not in placed:
            slot = f"{_wd(f.weekday)}第 {f.period_no} 格"
            v.append(
                Violation(
                    "H9",
                    f"锁定的单元格（教学任务 {f.assignment_id}，{slot}）被移动了",
                    {
                        "assignment_id": f.assignment_id,
                        "weekday": f.weekday,
                        "period_no": f.period_no,
                    },
                )
            )


def _h10_daily_cap(
    problem: Problem,
    entries: Sequence[SolvedEntry],
    by_id: dict[int, AssignmentSpec],
    cap: int,
    v: list[Violation],
) -> None:
    """同班同科目每日至多 N 节。连堂本来就是一次上完,不计入。"""
    counts: dict[tuple[int, int, int], int] = {}
    for e in entries:
        if e.span != 1:
            continue
        a = by_id[e.assignment_id]
        for cls in problem.classes_of(a):
            key = (cls.id, e.weekday, a.subject_id)
            counts[key] = counts.get(key, 0) + 1

    for (class_id, weekday, _subject_id), n in counts.items():
        if n > cap:
            cls = problem.classes[class_id]
            v.append(Violation(
                "H10",
                f"班级 {cls.name} {_wd(weekday)} 同一科目排了 {n} 节,超过每日上限 {cap} 节",
                {"class_id": class_id, "weekday": weekday, "count": n},
            ))


def _room_type(
    problem: Problem,
    entries: Sequence[SolvedEntry],
    by_id: dict[int, AssignmentSpec],
    v: list[Violation],
) -> None:
    for e in entries:
        a = by_id[e.assignment_id]
        if not a.required_room_type:
            continue
        rid = _effective_room(problem, e, a)
        room = problem.rooms.get(rid) if rid is not None else None
        if room is None:
            v.append(Violation(
                "room_type", f"「{a.subject_name}」需要教室/场地,却未指派",
                {"assignment_id": a.id},
            ))
        elif room.room_type != a.required_room_type:
            v.append(Violation(
                "room_type",
                f"「{a.subject_name}」需要 {a.required_room_type} 类型的教室/场地,"
                f"却排在 {room.name}({room.room_type})",
                {"assignment_id": a.id, "room_id": room.id},
            ))
