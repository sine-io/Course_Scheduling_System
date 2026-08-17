"""三套学制验证数据集的共用 builder。

测试策略总则(tasks.md)要求整个项目共用三套 fixtures(小学/初中/中职),作为排课引擎
(M3)与 E2E 总验收(M5-4)的基准数据。

以 Python builder 而非静态 JSON 表达,因为数据之间有数值依赖:
教师教学任务数 ≤ 可排格数、连堂节数 ≤ 每周节数、走班群组成员须同作息时间表(D7#4)。
使用程序构建,便于在修改时统一维护,并直接复用 app.services 现有的验证逻辑。
"""

from dataclasses import dataclass, field
from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment import (
    AssignmentTeacher,
    BlockRule,
    CourseAssignment,
    SchedulingUnit,
)
from app.models.basedata import (
    ClassUnit,
    Room,
    RoomType,
    Subject,
    Teacher,
    TeacherRuleType,
    TeacherTimeRule,
)
from app.models.period import Period, PeriodTable, PeriodType
from app.models.semester import Semester
from app.services.assignments import create_group, get_or_create_single_unit

_SUBJECTS: dict[str, tuple[str, ...]] = {
    "elementary": (
        "语文", "数学", "生活", "科学", "道德与法治", "体育与健康", "艺术", "综合实践活动",
        "英语", "地方课程",
    ),
    "junior_high": (
        "语文", "英语", "数学", "生物学", "道德与法治", "体育与健康", "艺术", "综合实践活动",
        "信息科技", "劳动",
    ),
    "vocational": (
        "语文", "英语", "数学", "体育", "专业实习", "专业核心课程", "实训课程",
        "校本课程", "选修课程",
    ),
}

_JUNIOR_SLOTS = (
    (1, "早自习", "07:50", "08:20", PeriodType.morning),
    (2, "第一节", "08:20", "09:05", PeriodType.regular),
    (3, "第二节", "09:15", "10:00", PeriodType.regular),
    (4, "第三节", "10:20", "11:05", PeriodType.regular),
    (5, "第四节", "11:15", "12:00", PeriodType.regular),
    (6, "午休", "12:00", "13:10", PeriodType.lunch),
    (7, "第五节", "13:10", "13:55", PeriodType.regular),
    (8, "第六节", "14:05", "14:50", PeriodType.regular),
    (9, "第七节", "15:10", "15:55", PeriodType.regular),
)

_LONG_SLOTS = (
    (1, "早自习", "07:50", "08:10", PeriodType.morning),
    (2, "第一节", "08:10", "09:00", PeriodType.regular),
    (3, "第二节", "09:10", "10:00", PeriodType.regular),
    (4, "第三节", "10:10", "11:00", PeriodType.regular),
    (5, "第四节", "11:10", "12:00", PeriodType.regular),
    (6, "午休", "12:00", "13:10", PeriodType.lunch),
    (7, "第五节", "13:10", "14:00", PeriodType.regular),
    (8, "第六节", "14:10", "15:00", PeriodType.regular),
    (9, "第七节", "15:20", "16:10", PeriodType.regular),
    (10, "第八节", "16:20", "17:10", PeriodType.regular),
)


def _clock(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _create_fixture_semester(
    db: Session, academic_year: int, term: int, dataset_key: str
) -> Semester:
    """直接构建测试数据，不依赖任何公开初始化预设。"""
    if dataset_key not in _SUBJECTS:
        raise ValueError(f"未知测试数据类型：{dataset_key}")
    semester = Semester(academic_year=academic_year, term=term)
    table = PeriodTable(
        name={
            "elementary": "小学作息时间表",
            "junior_high": "初中作息时间表",
            "vocational": "中职作息时间表",
        }[dataset_key],
        num_weekdays=5,
        is_default=True,
    )
    slots = _LONG_SLOTS if dataset_key == "vocational" else _JUNIOR_SLOTS
    for weekday in range(1, 6):
        for period_no, name, start, end, period_type in slots:
            cell_type = period_type
            if dataset_key == "elementary" and weekday == 3 and period_no in {7, 8, 9}:
                cell_type = PeriodType.reserved
            table.periods.append(
                Period(
                    weekday=weekday,
                    period_no=period_no,
                    name=name,
                    start_time=_clock(start),
                    end_time=_clock(end),
                    type=cell_type.value,
                )
            )
    semester.period_tables.append(table)
    db.add(semester)
    db.flush()
    for name in _SUBJECTS[dataset_key]:
        db.add(Subject(semester_id=semester.id, name=name))
    db.flush()
    return semester


@dataclass
class Fixture:
    """一套构建完成的学期数据集。以名称索引,测试可直接取用实体。"""

    semester: Semester
    table: PeriodTable
    subjects: dict[str, Subject] = field(default_factory=dict)
    teachers: dict[str, Teacher] = field(default_factory=dict)
    rooms: dict[str, Room] = field(default_factory=dict)
    classes: dict[str, ClassUnit] = field(default_factory=dict)
    groups: dict[str, SchedulingUnit] = field(default_factory=dict)
    assignments: list[CourseAssignment] = field(default_factory=list)

    @property
    def semester_id(self) -> int:
        return self.semester.id


class Builder:
    """直接创建测试学期，再逐步添加教师、班级、教室/场地和教学任务。"""

    def __init__(self, db: Session, academic_year: int, term: int, dataset_key: str) -> None:
        self.db = db
        self.semester = _create_fixture_semester(db, academic_year, term, dataset_key)
        self.table = self.semester.period_tables[0]
        self.subjects: dict[str, Subject] = {
            s.name: s
            for s in db.scalars(select(Subject).where(Subject.semester_id == self.semester.id))
        }
        self.teachers: dict[str, Teacher] = {}
        self.rooms: dict[str, Room] = {}
        self.classes: dict[str, ClassUnit] = {}
        self.groups: dict[str, SchedulingUnit] = {}
        self.assignments: list[CourseAssignment] = []

    # ── 作息时间表 ────────────────────────
    def set_period(self, weekday: int, period_no: int, ptype: PeriodType, name: str) -> None:
        p = self.db.scalar(
            select(Period).where(
                Period.period_table_id == self.table.id,
                Period.weekday == weekday,
                Period.period_no == period_no,
            )
        )
        assert p is not None, f"作息时间表无此单元格:周{weekday} 第{period_no}格"
        p.type = ptype.value
        p.name = name
        self.db.flush()

    def regular_slots(self) -> list[Period]:
        return list(
            self.db.scalars(
                select(Period)
                .where(
                    Period.period_table_id == self.table.id,
                    Period.type == PeriodType.regular.value,
                )
                .order_by(Period.weekday, Period.period_no)
            )
        )

    # ── 实体 ──────────────────────────
    def subject(
        self,
        name: str,
        *,
        domain: str | None = None,
        required_room_type: RoomType | None = None,
        default_block_size: int = 1,
        is_major: bool = False,
    ) -> Subject:
        s = self.subjects.get(name)
        if s is None:
            s = Subject(semester_id=self.semester.id, name=name)
            self.db.add(s)
            self.subjects[name] = s
        if domain:
            s.domain = domain
        if required_room_type:
            s.required_room_type = required_room_type.value
        s.default_block_size = default_block_size
        s.is_major = is_major
        self.db.flush()
        return s

    def teacher(
        self,
        name: str,
        *,
        base_periods: int = 20,
        admin_title: str | None = None,
        admin_reduction: int = 0,
        is_external: bool = False,
        subjects: list[str] | None = None,
    ) -> Teacher:
        t = Teacher(
            semester_id=self.semester.id,
            name=name,
            base_periods=base_periods,
            admin_title=admin_title,
            admin_reduction=admin_reduction,
            is_external=is_external,
        )
        for sn in subjects or []:
            t.subjects.append(self.subjects[sn])
        self.db.add(t)
        self.db.flush()
        self.teachers[name] = t
        return t

    def unavailable_days(self, teacher_name: str, weekdays: list[int]) -> None:
        """该教师在指定星期的所有一般课节次均不可排(企业兼职教师只有特定到校日)。"""
        t = self.teachers[teacher_name]
        for p in self.regular_slots():
            if p.weekday in weekdays:
                self.db.add(
                    TeacherTimeRule(
                        teacher_id=t.id,
                        weekday=p.weekday,
                        period_no=p.period_no,
                        rule_type=TeacherRuleType.unavailable.value,
                    )
                )
        self.db.flush()

    def room(
        self,
        name: str,
        *,
        room_type: RoomType = RoomType.normal,
        capacity: int | None = None,
        subjects: list[str] | None = None,
    ) -> Room:
        r = Room(
            semester_id=self.semester.id,
            name=name,
            room_type=room_type.value,
            capacity=capacity,
        )
        for sn in subjects or []:
            r.subjects.append(self.subjects[sn])
        self.db.add(r)
        self.db.flush()
        self.rooms[name] = r
        return r

    def klass(
        self,
        name: str,
        *,
        grade: int,
        track: str,
        department: str | None = None,
        student_count: int = 30,
        homeroom: str | None = None,
    ) -> ClassUnit:
        c = ClassUnit(
            semester_id=self.semester.id,
            grade=grade,
            name=name,
            track=track,
            department=department,
            student_count=student_count,
            homeroom_teacher_id=self.teachers[homeroom].id if homeroom else None,
        )
        self.db.add(c)
        self.db.flush()
        self.classes[name] = c
        return c

    def group(self, name: str, class_names: list[str]) -> SchedulingUnit:
        """走班群组。create_group 会验证成员班级同作息时间表(D7#4)。"""
        g = create_group(
            self.db,
            self.semester.id,
            name,
            [self.classes[n].id for n in class_names],
        )
        self.groups[name] = g
        return g

    # ── 教学任务 ──────────────────────────
    def assign(
        self,
        *,
        subject: str,
        teachers: list[str],
        periods: int,
        classes: list[str] | None = None,
        group: str | None = None,
        room: str | None = None,
        required_room_type: RoomType | None = None,
        blocks: tuple[int, int] | None = None,
        lock_room: bool = False,
    ) -> list[CourseAssignment]:
        """创建教学任务。classes → 每班一项(single unit);group → 群组一项。

        teachers 第一位为主讲教师,其余为协同教师。blocks=(连堂长度, 每周次数)。
        """
        if (classes is None) == (group is None):
            raise ValueError("classes 与 group 择一")
        units = (
            [get_or_create_single_unit(self.db, self.classes[n]) for n in classes]
            if classes
            else [self.groups[group]]  # type: ignore[index]
        )
        out = []
        for unit in units:
            a = CourseAssignment(
                semester_id=self.semester.id,
                scheduling_unit_id=unit.id,
                subject_id=self.subjects[subject].id,
                periods_per_week=periods,
                required_room_type=required_room_type.value if required_room_type else None,
                room_id=self.rooms[room].id if room else None,
                lock_room=lock_room,
            )
            for i, tn in enumerate(teachers):
                a.teachers.append(
                    AssignmentTeacher(teacher_id=self.teachers[tn].id, is_lead=(i == 0))
                )
            if blocks:
                size, count = blocks
                a.block_rules.append(BlockRule(block_size=size, count_per_week=count))
            self.db.add(a)
            self.db.flush()
            self.assignments.append(a)
            out.append(a)
        return out

    def build(self) -> Fixture:
        self.db.commit()
        return Fixture(
            semester=self.semester,
            table=self.table,
            subjects=self.subjects,
            teachers=self.teachers,
            rooms=self.rooms,
            classes=self.classes,
            groups=self.groups,
            assignments=self.assignments,
        )


# ── 分析 helper(供烟雾测试与日后 pre-flight 对照)────────────────
def teacher_available_slots(db: Session, fx: Fixture, teacher: Teacher) -> int:
    """教师可排格数 = 一般课格数 − 其 unavailable 规则落在一般课单元格的数量。

    单一作息时间表(绝大多数学校)的定义;跨表任教的教师以墙钟区间并集去重,
    留待 M3-1 pre-flight 实现。
    """
    regular = {
        (p.weekday, p.period_no)
        for p in db.scalars(
            select(Period).where(
                Period.period_table_id == fx.table.id,
                Period.type == PeriodType.regular.value,
            )
        )
    }
    blocked = {
        (r.weekday, r.period_no)
        for r in teacher.time_rules
        if r.rule_type == TeacherRuleType.unavailable.value
    }
    return len(regular - blocked)


def room_demand(fx: Fixture) -> dict[int, int]:
    """每个「已指定教室/场地」的教学任务节数需求(room_id → 节数)。"""
    demand: dict[int, int] = {}
    for a in fx.assignments:
        if a.room_id:
            demand[a.room_id] = demand.get(a.room_id, 0) + a.periods_per_week
    return demand
