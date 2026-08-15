"""示例数据生成器：一键创建一所完整的虚构初中。

系统安装后默认没有业务数据。示例数据让用户无需手工创建几十名教师和数百条
教学任务，即可验证自动排课及后续流程。

规格位于 app/data/demo_school.json；本模块负责据此推算教师名单、应授课时和
教学任务。修改 JSON 中的规模后，任务分配会自动重新平衡。

仅允许在没有任何学期的系统中执行，调用方负责校验。
"""

import json
from dataclasses import dataclass, field
from datetime import date, time
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.assignment import AssignmentTeacher, CourseAssignment
from app.models.basedata import ClassTrack, ClassUnit, Room, Subject, Teacher
from app.models.period import Period
from app.models.semester import Semester
from app.models.timetable import Timetable
from app.models.wizard import SINGLETON_ID, TOTAL_STEPS, WizardState
from app.services import settings as settings_service
from app.services import templates as template_service
from app.services.assignments import get_or_create_single_unit

_SPEC_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_school.json"

# 教师身份的顺序也是分配优先级。班主任先获取本班任务，承担管理工作的教师
# 最后补齐，避免超过其较低的应授课时。
ROLE_HOMEROOM = "班主任"
ROLE_FULLTIME = "专任教师"
ROLE_EXTERNAL = "外聘教师"
ROLE_ORDER = [
    ROLE_HOMEROOM,
    ROLE_FULLTIME,
    "教研负责人",
    "中层干部",
    "专职心理健康教师",
    ROLE_EXTERNAL,
]


@lru_cache
def load_spec() -> dict:
    with open(_SPEC_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@dataclass
class _TeacherPlan:
    """建表前的教师规划：先计算应授课时，再分配教学任务。"""

    name: str
    dept: str
    role: str
    base_periods: int
    admin_reduction: int = 0
    admin_title: str | None = None
    is_external: bool = False
    homeroom_of: str | None = None          # 班主任负责的班级
    assigned: int = 0                        # 已分教学任务时
    model: Teacher | None = field(default=None, repr=False)

    @property
    def target(self) -> int:
        return max(self.base_periods - self.admin_reduction, 0)

    @property
    def headroom(self) -> int:
        """距离应授课时的余量，负数表示已经超课时。"""
        return self.target - self.assigned


@dataclass
class DemoSummary:
    """生成结果，供 API 返回并用于测试断言。"""

    semester_id: int
    school_name: str
    classes: int
    teachers: int
    subjects: int
    rooms: int
    assignments: int
    total_periods: int
    max_overtime_used: int   # 全校教师最大超课时数
    under_target: int        # 未达到应授课时的教师数


def _base_for(spec: dict, dept: str, role: str) -> int:
    """读取该教研组和身份对应的基本课时。"""
    table = spec["base_periods"].get(dept, spec["base_periods"]["_default"])
    if role == ROLE_HOMEROOM:
        return table[ROLE_HOMEROOM]
    return table[ROLE_FULLTIME]


def _plan_teachers(spec: dict, class_names: list[str]) -> list[_TeacherPlan]:
    """按配置生成教师名单，班主任依次关联班级。"""
    surnames, givens = spec["surnames"], spec["given_names"]
    titles = {k: list(v) for k, v in spec["admin_titles"].items()}
    homeroom_queue = list(class_names)
    plans: list[_TeacherPlan] = []

    for dept in spec["departments"]:
        dept_name = dept["name"]
        for role in ROLE_ORDER:
            for _ in range(dept.get(role, 0)):
                idx = len(plans)
                # 姓名按索引错位组合，避免在一个示例学期内重复。
                name = surnames[idx % len(surnames)] + givens[(idx * 7 + 3) % len(givens)]
                plan = _TeacherPlan(
                    name=name,
                    dept=dept_name,
                    role=role,
                    base_periods=_base_for(spec, dept_name, role),
                    is_external=(role == ROLE_EXTERNAL),
                )
                if role in titles and titles[role]:
                    plan.admin_title = titles[role].pop(0)
                if role in spec["admin_targets"]:
                    # 配置给出实际应授课时，换算为减课数后写入数据库。
                    plan.admin_reduction = max(
                        plan.base_periods - spec["admin_targets"][role], 0
                    )
                if role == ROLE_HOMEROOM and homeroom_queue:
                    plan.homeroom_of = homeroom_queue.pop(0)
                if role == ROLE_EXTERNAL:
                    # 外聘教师以实际承担的课时作为应授课时。
                    plan.base_periods = 0
                plans.append(plan)
    return plans


def _class_names(spec: dict) -> list[tuple[int, str]]:
    """按年级和序号生成班级名称，如 701 至 706。"""
    cfg = spec["classes"]
    fmt = cfg.get("name_format", "{grade}{index:02d}")
    return [
        (grade, fmt.format(grade=grade, index=i))
        for grade in cfg["grades"]
        for i in range(1, cfg["per_grade"] + 1)
    ]


def _demand(spec: dict, classes: list[tuple[int, str]]) -> list[tuple[str, str, int]]:
    """展开为（班级、科目、每周课时），跳过未配置该年级的科目。"""
    rows: list[tuple[str, str, int]] = []
    for grade, cname in classes:
        for subj in spec["subjects"]:
            periods = subj["periods"].get(str(grade))
            if periods:
                rows.append((cname, subj["name"], periods))
    return rows


def _pick_teacher(pool: list[_TeacherPlan]) -> _TeacherPlan:
    """选择剩余工作量最大的教师。

    这样可以均衡分配任务；当所有教师都达到应授课时时，继续选择超课时最少者。
    """
    return max(pool, key=lambda p: (p.headroom, -p.assigned))


def _apply_demo_period_table(semester: Semester, spec: dict) -> None:
    """为示例学期填充演示作息，不改变面向正式用户的空白学校模板。"""
    table = semester.period_tables[0]
    cfg = spec["period_table"]
    table.name = cfg["name"]
    table.num_weekdays = cfg.get("num_weekdays", 5)
    for weekday in range(1, table.num_weekdays + 1):
        for slot in cfg["slots"]:
            table.periods.append(
                Period(
                    weekday=weekday,
                    period_no=slot["period_no"],
                    name=slot["name"],
                    start_time=time.fromisoformat(slot["start"]) if slot.get("start") else None,
                    end_time=time.fromisoformat(slot["end"]) if slot.get("end") else None,
                    type=slot["type"],
                )
            )


def generate(db: Session, spec: dict | None = None) -> DemoSummary:
    """创建整所示例学校。调用方负责确认系统无学期并提交事务。"""
    spec = spec or load_spec()
    classes = _class_names(spec)
    class_names = [name for _, name in classes]

    # 同步设置学校名称，保证界面和导出内容与示例数据一致。
    settings_service.save_school_name(db, spec["school_name"])

    # 正式向导仍使用空白模板；示例学期单独填充一套可直接排课的演示作息。
    semester = template_service.create_semester_from_template(
        db,
        academic_year=spec["academic_year"],
        term=spec["term"],
        template_key=spec["template_key"],
    )
    semester.is_demo = True
    # 示例路线需要能直接进入自动排课；日期和准备状态仍只属于示例学期，
    # onboarding 读模型会因为 is_demo=True 将其排除在正式首次成功之外。
    semester.start_date = date(spec["academic_year"], 9, 1)
    semester.end_date = date(spec["academic_year"] + 1, 1, 31)
    semester.readiness = "ready"
    sid = semester.id
    _apply_demo_period_table(semester, spec)

    # 清除模板带入的科目参考项，再按示例规格创建分科科目。
    for row in db.query(Subject).filter(Subject.semester_id == sid).all():
        db.delete(row)
    db.flush()

    subjects: dict[str, Subject] = {}
    for item in spec["subjects"]:
        s = Subject(
            semester_id=sid,
            name=item["name"],
            domain=item["domain"],
            is_major=item.get("major", False),
            required_room_type=item.get("room"),
        )
        db.add(s)
        subjects[item["name"]] = s

    # ── 教室与教学地点 ──
    rooms: dict[str, list[Room]] = {}
    room_count = 0
    for spec_room in spec["rooms"]:
        for i in range(spec_room["count"]):
            suffix = f"{i + 1}" if spec_room["count"] > 1 else ""
            r = Room(
                semester_id=sid,
                name=f"{spec_room['name']}{suffix}",
                room_type=spec_room["type"],
            )
            db.add(r)
            for sub_name in spec_room["subjects"]:
                rooms.setdefault(sub_name, []).append(r)
            room_count += 1
    # 每班创建一间普通教室。
    for _, cname in classes:
        db.add(Room(semester_id=sid, name=cname, room_type="normal"))
        room_count += 1
    db.flush()

    # ── 教师 ──
    plans = _plan_teachers(spec, class_names)
    by_name: dict[str, _TeacherPlan] = {}
    for plan in plans:
        t = Teacher(
            semester_id=sid,
            name=plan.name,
            base_periods=plan.base_periods,
            admin_reduction=plan.admin_reduction,
            admin_title=plan.admin_title,
            is_external=plan.is_external,
        )
        db.add(t)
        plan.model = t
        by_name[plan.name] = plan
    db.flush()

    # 外聘教师的应授课时等于实际需求，避免把全部任务误报为超课时。
    demand = _demand(spec, classes)
    dept_of = {s["name"]: s["dept"] for s in spec["subjects"]}
    for plan in plans:
        if plan.role != ROLE_EXTERNAL:
            continue
        total = sum(p for _, sname, p in demand if dept_of[sname] == plan.dept)
        plan.base_periods = total
        assert plan.model is not None
        plan.model.base_periods = total

    # ── 班级（关联班主任）──
    homeroom_by_class = {p.homeroom_of: p for p in plans if p.homeroom_of}
    class_models: dict[str, ClassUnit] = {}
    for grade, cname in classes:
        hr = homeroom_by_class.get(cname)
        assert hr is None or hr.model is not None
        cu = ClassUnit(
            semester_id=sid,
            grade=grade,
            name=cname,
            track=ClassTrack.junior_high.value,
            student_count=spec["classes"]["student_count"],
            homeroom_teacher_id=hr.model.id if hr and hr.model else None,
        )
        db.add(cu)
        class_models[cname] = cu
    db.flush()

    # ── 教学任务 ──
    pools: dict[str, list[_TeacherPlan]] = {}
    for plan in plans:
        pools.setdefault(plan.dept, []).append(plan)

    # 班主任优先承担本班、本教研组的任务，以便演示班主任排课偏好。
    def sort_key(row: tuple[str, str, int]) -> tuple[int, str, str]:
        cname, sname, _ = row
        hr = homeroom_by_class.get(cname)
        own = 0 if hr and dept_of[sname] == hr.dept else 1
        return (own, cname, sname)

    assignment_count = 0
    total_periods = 0
    for cname, sname, periods in sorted(demand, key=sort_key):
        pool = pools[dept_of[sname]]
        hr = homeroom_by_class.get(cname)
        if hr is not None and hr.dept == dept_of[sname] and hr.headroom >= periods:
            teacher = hr
        else:
            teacher = _pick_teacher(pool)

        assert teacher.model is not None
        unit = get_or_create_single_unit(db, class_models[cname])
        assignment = CourseAssignment(
            semester_id=sid,
            scheduling_unit_id=unit.id,
            subject_id=subjects[sname].id,
            periods_per_week=periods,
            required_room_type=subjects[sname].required_room_type,
        )
        db.add(assignment)
        db.flush()
        assignment.teachers.append(
            AssignmentTeacher(teacher_id=teacher.model.id, is_lead=True)
        )
        teacher.assigned += periods
        assignment_count += 1
        total_periods += periods
    db.flush()

    # 示例数据已经覆盖向导的全部准备步骤，因此直接标记向导完成。
    wizard = db.get(WizardState, SINGLETON_ID)
    if wizard is None:
        wizard = WizardState(id=SINGLETON_ID)
        db.add(wizard)
    wizard.completed = True
    wizard.current_step = TOTAL_STEPS - 1
    wizard.semester_id = sid
    wizard.route = "demo"
    db.add(Timetable(semester_id=sid, name="示例课表草稿"))
    db.flush()

    overs = [-p.headroom for p in plans if p.headroom < 0]
    return DemoSummary(
        semester_id=sid,
        school_name=spec["school_name"],
        classes=len(classes),
        teachers=len(plans),
        subjects=len(subjects),
        rooms=room_count,
        assignments=assignment_count,
        total_periods=total_periods,
        max_overtime_used=max(overs, default=0),
        under_target=sum(1 for p in plans if p.headroom > 0),
    )


def semester_is_empty(db: Session, semester_id: int) -> bool:
    """判断学期是否尚未创建班级和教师。"""
    has_class = db.query(ClassUnit).filter(ClassUnit.semester_id == semester_id).first()
    has_teacher = db.query(Teacher).filter(Teacher.semester_id == semester_id).first()
    return has_class is None and has_teacher is None


def any_semester_exists(db: Session) -> bool:
    return db.query(Semester).first() is not None
