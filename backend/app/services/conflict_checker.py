"""手动排课的硬约束单格检查(architecture.md §3.2 H1–H10 的单格版)。

将教学任务放入或移动到某个单元格时，检查是否违反硬约束并返回易懂的冲突说明。
跨作息时间表的教师(H2)和教室/场地(H3)冲突以「同星期 + 墙钟时间区间重叠」判定
(architecture.md D7);同作息时间表则退化为 period_no 相等(常见情形,零额外成本)。
走班群组:同群组多项教学任务同时排在同一格(H7),批量一起检查;群组成员班级由
多门课共用(不互相视为 H1 冲突),但彼此的教师和教室/场地仍不可重复。
"""

from dataclasses import dataclass
from datetime import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assignment import (
    AssignmentTeacher,
    CourseAssignment,
    SchedulingUnitMember,
    SchedulingUnitType,
)
from app.models.basedata import ClassUnit, Room, Subject
from app.models.period import Period, PeriodType
from app.models.timetable import ScheduleEntry, Timetable
from app.services import period_tables as pt_service
from app.services.solver_data import load_config

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


@dataclass
class Conflict:
    code: str  # H1..H10
    message: str


@dataclass
class Placement:
    assignment: CourseAssignment
    weekday: int
    period_no: int
    span: int = 1
    # 本单元格实际使用的教室/场地(空=沿用教学任务教室/场地);手动改教室或引擎逐格指派时带入
    room_id: int | None = None

    @property
    def effective_room_id(self) -> int | None:
        return self.room_id if self.room_id is not None else self.assignment.room_id


@dataclass
class _Occ:
    weekday: int
    table_id: int
    period_no: int
    start: time | None
    end: time | None
    desc: str


def _wd(w: int) -> str:
    return WEEKDAY_CN[w - 1] if 1 <= w <= len(WEEKDAY_CN) else f"星期{w}"


class _Checker:
    def __init__(self, db: Session, timetable: Timetable, daily_subject_cap: int) -> None:
        self.db = db
        self.timetable = timetable
        self.cap = daily_subject_cap
        self._pmap_cache: dict[int, dict[tuple[int, int], Period]] = {}
        self._table_cache: dict[int, int | None] = {}
        self._class_table_cache: dict[int, int | None] = {}
        self._default_table_cache: dict[int, int | None] = {}
        self._room_name_cache: dict[int, str] = {}

    def _room_name(self, room_id: int) -> str:
        if room_id not in self._room_name_cache:
            room = self.db.get(Room, room_id)
            self._room_name_cache[room_id] = room.name if room else str(room_id)
        return self._room_name_cache[room_id]

    def _period_map(self, table_id: int) -> dict[tuple[int, int], Period]:
        if table_id not in self._pmap_cache:
            rows = self.db.scalars(select(Period).where(Period.period_table_id == table_id))
            self._pmap_cache[table_id] = {(p.weekday, p.period_no): p for p in rows}
        return self._pmap_cache[table_id]

    def _default_table_id(self, semester_id: int) -> int | None:
        if semester_id not in self._default_table_cache:
            t = pt_service.semester_default_table(self.db, semester_id)
            self._default_table_cache[semester_id] = t.id if t else None
        return self._default_table_cache[semester_id]

    def _table_for_class(self, class_id: int, semester_id: int, table_id: int | None) -> int | None:
        """等同 resolve_period_table(指定表 → 回退学期默认表),但于单次检查内缓存,
        避免每项教学任务都重查一次学期默认表(check-conflict 需 <100ms)。"""
        if class_id not in self._class_table_cache:
            self._class_table_cache[class_id] = (
                table_id if table_id is not None else self._default_table_id(semester_id)
            )
        return self._class_table_cache[class_id]

    def _class_table_id(self, cls: ClassUnit) -> int | None:
        return self._table_for_class(cls.id, cls.semester_id, cls.period_table_id)

    def _table_id(self, a: CourseAssignment) -> int | None:
        if a.id not in self._table_cache:
            members = a.scheduling_unit.members
            cls = members[0].class_unit if members else None
            self._table_cache[a.id] = self._class_table_id(cls) if cls else None
        return self._table_cache[a.id]

    def _classes(self, a: CourseAssignment):
        return [m.class_unit for m in a.scheduling_unit.members]

    def _desc(self, a: CourseAssignment) -> str:
        names = "、".join(m.class_unit.name for m in a.scheduling_unit.members)
        return f"{names} 班{a.subject.name}"

    def _slot(self, pmap: dict[tuple[int, int], Period], weekday: int, pno: int) -> str:
        """易懂说明时段标签:用作息时间表里的名称(早自习/午休/第一节),而非内部 period_no。

        period_no 是含早自习/午休的内部索引(初中模板第一节的 period_no 是 2),
        直接显示会与排课管理员的认知不符。
        """
        p = pmap.get((weekday, pno))
        return f"{_wd(weekday)}{p.name}" if p else f"{_wd(weekday)}第{pno}节"

    def _overlap(
        self, occ: _Occ, weekday: int, table_id: int, pno: int, start: time | None, end: time | None
    ) -> bool:
        if occ.weekday != weekday:
            return False
        if occ.table_id == table_id:
            return occ.period_no == pno  # 同表:节次号相等
        # 跨作息时间表:墙钟时间区间重叠(D7)
        if occ.start and occ.end and start and end:
            return start < occ.end and occ.start < end
        return False

    def _build_occupancy(self, ignore_entry_ids: set[int]):
        """以字段查询(非 ORM 实体)创建现有单元格的占用索引。

        check-conflict 是拖拽时的热路径(目标 p95 <100ms),逐格 hydrate ORM 对象
        在 60 班规模下代价过高,故此处只取需要的字段并在 Python 端组装。
        """
        class_occ: dict[tuple[int, int, int], str] = {}
        teacher_occ: dict[int, list[_Occ]] = {}
        room_occ: dict[int, list[_Occ]] = {}
        subj_count: dict[tuple[int, int, int], int] = {}

        rows = self.db.execute(
            select(
                ScheduleEntry.id, ScheduleEntry.weekday, ScheduleEntry.period_no,
                ScheduleEntry.span, CourseAssignment.id, CourseAssignment.subject_id,
                # 单元格教室/场地优先,未指定才沿用教学任务教室/场地
                func.coalesce(ScheduleEntry.room_id, CourseAssignment.room_id),
                CourseAssignment.scheduling_unit_id, Subject.name,
            )
            .join(CourseAssignment, ScheduleEntry.course_assignment_id == CourseAssignment.id)
            .join(Subject, Subject.id == CourseAssignment.subject_id)
            .where(ScheduleEntry.timetable_id == self.timetable.id)
        ).all()
        rows = [r for r in rows if r[0] not in ignore_entry_ids]
        if not rows:
            return class_occ, teacher_occ, room_occ, subj_count

        unit_ids = {r[7] for r in rows}
        a_ids = {r[4] for r in rows}

        # 排课单位 → 成员班级(id, 班名, 作息时间表)
        classes_by_unit: dict[int, list[tuple[int, str, int | None]]] = {}
        for uid, cid, cname, c_sem, c_table in self.db.execute(
            select(
                SchedulingUnitMember.scheduling_unit_id, ClassUnit.id, ClassUnit.name,
                ClassUnit.semester_id, ClassUnit.period_table_id,
            )
            .join(ClassUnit, ClassUnit.id == SchedulingUnitMember.class_unit_id)
            .where(SchedulingUnitMember.scheduling_unit_id.in_(unit_ids))
        ).all():
            classes_by_unit.setdefault(uid, []).append(
                (cid, cname, self._table_for_class(cid, c_sem, c_table))
            )

        # 教学任务 → 教师
        teachers_by_a: dict[int, list[int]] = {}
        for aid, tid in self.db.execute(
            select(AssignmentTeacher.course_assignment_id, AssignmentTeacher.teacher_id)
            .where(AssignmentTeacher.course_assignment_id.in_(a_ids))
        ).all():
            teachers_by_a.setdefault(aid, []).append(tid)

        for _e_id, wd, pno0, span, a_id, subject_id, room_id, unit_id, subj_name in rows:
            classes = classes_by_unit.get(unit_id, [])
            if not classes:
                continue
            table_id = classes[0][2]
            if table_id is None:
                continue
            pmap = self._period_map(table_id)
            desc = f"{'、'.join(c[1] for c in classes)} 班{subj_name}"
            t_ids = teachers_by_a.get(a_id, [])
            for k in range(span):
                pno = pno0 + k
                p = pmap.get((wd, pno))
                start = p.start_time if p else None
                end = p.end_time if p else None
                occ = _Occ(wd, table_id, pno, start, end, desc)
                for cid, _cname, _ct in classes:
                    class_occ[(cid, wd, pno)] = desc
                for t_id in t_ids:
                    teacher_occ.setdefault(t_id, []).append(occ)
                if room_id:
                    room_occ.setdefault(room_id, []).append(occ)
            # H10 只计单节:连堂是一次上完的整块,本来就不受每日上限限制
            if span == 1:
                for cid, _cname, _ct in classes:
                    key = (cid, wd, subject_id)
                    subj_count[key] = subj_count.get(key, 0) + 1
        return class_occ, teacher_occ, room_occ, subj_count

    def check(self, placements: list[Placement], ignore_entry_ids: set[int]) -> list[Conflict]:
        class_occ, teacher_occ, room_occ, subj_count = self._build_occupancy(ignore_entry_ids)
        conflicts: list[Conflict] = []
        batch_teacher: dict[int, list[_Occ]] = {}
        batch_room: dict[int, list[_Occ]] = {}

        for pl in placements:
            a = pl.assignment
            wd = pl.weekday
            table_id = self._table_id(a)
            if table_id is None:
                conflicts.append(Conflict("H5", f"{self._desc(a)} 尚无可用作息时间表"))
                continue
            pmap = self._period_map(table_id)

            # H5/H6:区块涵盖的节次须存在且均为一般课
            covered: list[tuple[int, time | None, time | None]] = []
            block_ok = True
            for k in range(pl.span):
                pno = pl.period_no + k
                p = pmap.get((wd, pno))
                if p is None or p.type != PeriodType.regular.value:
                    block_ok = False
                    break
                covered.append((pno, p.start_time, p.end_time))
            if not block_ok:
                if pl.span > 1:
                    conflicts.append(Conflict(
                        "H6",
                        f"连堂课排在 {self._slot(pmap, wd, pl.period_no)} 会跨越午休或非上课时段"
                        f"(需连续 {pl.span} 节一般课)",
                    ))
                else:
                    conflicts.append(Conflict(
                        "H5",
                        f"{self._slot(pmap, wd, pl.period_no)} 非一般上课节次,不可排课"))
                continue

            # H1:班级不冲堂(仅比对现有单元格;同群组成员班级共用不算冲突)
            for c in self._classes(a):
                for pno, _s, _e in covered:
                    d = class_occ.get((c.id, wd, pno))
                    if d:
                        conflicts.append(Conflict(
                            "H1", f"班级 {c.name} {self._slot(pmap, wd, pno)} 已有 {d}"))

            # H4 教师不可排时段 + H2 教师不冲堂(含跨表时间重叠、同群组其他门课)
            for at in a.teachers:
                t = at.teacher
                for pno, s, e in covered:
                    label = self._slot(pmap, wd, pno)
                    for rule in t.time_rules:
                        if (rule.rule_type == "unavailable"
                                and rule.weekday == wd and rule.period_no == pno):
                            conflicts.append(Conflict(
                                "H4", f"教师{t.name} {label} 为不可排时段"))
                    for occ in teacher_occ.get(at.teacher_id, []):
                        if self._overlap(occ, wd, table_id, pno, s, e):
                            conflicts.append(Conflict(
                                "H2", f"教师{t.name} {label} 已有 {occ.desc}"))
                    for occ in batch_teacher.get(at.teacher_id, []):
                        if self._overlap(occ, wd, table_id, pno, s, e):
                            conflicts.append(Conflict(
                                "H2", f"教师{t.name} {label} 与同群组另一门课撞课"))

            # H3 教室/场地不冲堂(以单元格实际教室/场地判定,非教学任务上的默认教室/场地)
            room_id = pl.effective_room_id
            if room_id:
                for pno, s, e in covered:
                    for occ in room_occ.get(room_id, []) + batch_room.get(room_id, []):
                        if self._overlap(occ, wd, table_id, pno, s, e):
                            conflicts.append(Conflict(
                                "H3",
                                f"教室/场地 {self._room_name(room_id)} "
                                f"{self._slot(pmap, wd, pno)} 已有 {occ.desc}"))

            # H10 同班同科目每日上限。连堂(span>1)是一次上完的整块,不计亦不受限;
            # 但连堂课剩下的单节仍受限——定义以 solver/validator.py 为准。
            if pl.span == 1:
                for c in self._classes(a):
                    existing = subj_count.get((c.id, wd, a.subject_id), 0)
                    if existing + 1 > self.cap:
                        conflicts.append(Conflict(
                            "H10",
                            f"班级 {c.name} {_wd(wd)} 已排「{a.subject.name}」{existing} 节,"
                            f"达每日上限 {self.cap} 节",
                        ))

            # 累积批量教师和教室/场地占用(同群组其他门课据此互检)
            desc = self._desc(a)
            for at in a.teachers:
                for pno, s, e in covered:
                    batch_teacher.setdefault(at.teacher_id, []).append(
                        _Occ(wd, table_id, pno, s, e, desc))
            if room_id:
                for pno, s, e in covered:
                    batch_room.setdefault(room_id, []).append(_Occ(wd, table_id, pno, s, e, desc))

        return conflicts


def placements_for(
    db: Session,
    assignment: CourseAssignment,
    weekday: int,
    period_no: int,
    span: int,
    room_id: int | None = None,
) -> list[Placement]:
    """展开实际要放入的教学任务:走班群组 → 群组内全部教学任务同格(span=1);单班 → 该教学任务。

    room_id 为「本次放入的教室/场地」,只套用在被拖拽的那一项教学任务上;
    群组内的其他门课各自使用自己的教室/场地(走班的每组本来就在不同教室)。
    """
    su = assignment.scheduling_unit
    if su.unit_type == SchedulingUnitType.group.value:
        sibs = list(
            db.scalars(
                select(CourseAssignment).where(CourseAssignment.scheduling_unit_id == su.id)
            )
        )
        return [
            Placement(s, weekday, period_no, 1, room_id if s.id == assignment.id else None)
            for s in sibs
        ]
    return [Placement(assignment, weekday, period_no, span, room_id)]


def check_conflict(
    db: Session,
    timetable: Timetable,
    assignment: CourseAssignment,
    weekday: int,
    period_no: int,
    span: int = 1,
    ignore_entry_ids: set[int] | None = None,
    room_id: int | None = None,
    daily_subject_cap: int | None = None,
) -> list[Conflict]:
    """检查将 assignment 放到 (weekday, period_no) 是否违反硬约束。

    移动现有单元格时传 ignore_entry_ids(被搬动的那几格),使其不与自己相冲。
    room_id 为单元格指定教室/场地(空=沿用教学任务教室/场地)。返回空列表表示可放。

    H10 的每日上限**必须与自动排课用同一个值**(学期的 constraint_config),
    否则同一张草稿会出现「自动排课排得出来、手动拖拽却报违规」的双轨判定。
    未指定时自动读取该学期设置。
    """
    if daily_subject_cap is None:
        daily_subject_cap = load_config(db, timetable.semester_id).daily_subject_cap
    checker = _Checker(db, timetable, daily_subject_cap)
    placements = placements_for(db, assignment, weekday, period_no, span, room_id)
    return checker.check(placements, ignore_entry_ids or set())
