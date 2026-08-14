"""基础数据 API:教师、科目、教室/场地、班级。

权限:读取 = 排课管理员/教务主任;写入 = 排课管理员(admin 统一通过)。
所有资源以 semester_id 为范围。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.db import get_db
from app.models.basedata import (
    ClassUnit,
    Room,
    Subject,
    Teacher,
    TeacherTimeRule,
    room_subjects,
    teacher_subjects,
)
from app.models.period import PeriodTable
from app.models.user import Role, User, UserRole
from app.schemas.basedata import (
    BindableAccount,
    ClassUnitIn,
    ClassUnitOut,
    RoomIn,
    RoomOut,
    SubjectIn,
    SubjectOut,
    TeacherIn,
    TeacherOut,
    TeacherTimeRuleIn,
    TeacherTimeRuleOut,
)
from app.schemas.semester import AvailableSlot, PeriodTableOut
from app.services import period_tables as pt_service
from app.services import semester_context

router = APIRouter(tags=["basedata"])

viewer = require_roles(Role.scheduler, Role.director)
editor = require_roles(Role.scheduler)


def _require_writable(db: Session, semester_id: int) -> None:
    try:
        semester_context.require_writable(db, semester_id)
    except semester_context.SemesterContextError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": exc.message}) from exc


def _resolve_subjects(db: Session, semester_id: int, ids: list[int]) -> list[Subject]:
    if not ids:
        return []
    subjects = db.scalars(
        select(Subject).where(Subject.id.in_(ids), Subject.semester_id == semester_id)
    ).all()
    if len(subjects) != len(set(ids)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "科目列表含无效或跨学期的科目")
    return list(subjects)


# ── 科目 ──────────────────────────────
@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(
    semester_id: int = Query(...),
    q: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(viewer),
):
    stmt = select(Subject).where(Subject.semester_id == semester_id)
    if q:
        stmt = stmt.where(Subject.name.contains(q))
    return db.scalars(stmt.order_by(Subject.name)).all()


@router.post("/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(
    body: SubjectIn,
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(editor),
) -> Subject:
    _require_writable(db, semester_id)
    subject = Subject(
        semester_id=semester_id,
        name=body.name,
        domain=body.domain,
        required_room_type=body.required_room_type.value if body.required_room_type else None,
        default_block_size=body.default_block_size,
        is_major=body.is_major,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.patch("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject(
    subject_id: int, body: SubjectIn, db: Session = Depends(get_db), _: object = Depends(editor)
) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到科目")
    _require_writable(db, subject.semester_id)
    subject.name = body.name
    subject.domain = body.domain
    subject.required_room_type = body.required_room_type.value if body.required_room_type else None
    subject.default_block_size = body.default_block_size
    subject.is_major = body.is_major
    db.commit()
    db.refresh(subject)
    return subject


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: int, db: Session = Depends(get_db), _: object = Depends(editor)
) -> None:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到科目")
    _require_writable(db, subject.semester_id)
    t_count = db.scalar(
        select(func.count()).select_from(teacher_subjects).where(
            teacher_subjects.c.subject_id == subject_id
        )
    )
    r_count = db.scalar(
        select(func.count()).select_from(room_subjects).where(
            room_subjects.c.subject_id == subject_id
        )
    )
    if t_count or r_count:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"此科目已被 {t_count} 位教师、{r_count} 个教室/场地引用,请先解除关联再删除",
        )
    db.delete(subject)
    db.commit()


def _validate_teacher_user(
    db: Session, semester_id: int, user_id: int | None, exclude_teacher_id: int | None = None
) -> None:
    """验证欲绑定的账号:须存在,且同学期未被其他教师绑定(否则 409)。"""
    if user_id is None:
        return
    if db.get(User, user_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "欲绑定的账号不存在")
    stmt = select(Teacher.id).where(
        Teacher.semester_id == semester_id, Teacher.user_id == user_id
    )
    if exclude_teacher_id is not None:
        stmt = stmt.where(Teacher.id != exclude_teacher_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "此账号在本学期已绑定其他教师")


# ── 教师 ──────────────────────────────
@router.get("/teachers/bindable-accounts", response_model=list[BindableAccount])
def list_bindable_accounts(
    semester_id: int = Query(...),
    current_teacher_id: int | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(viewer),
):
    """teacher 角色且在本学期尚未绑定的账号;编辑时另纳入该教师目前绑定的账号。"""
    bound = set(
        db.scalars(
            select(Teacher.user_id).where(
                Teacher.semester_id == semester_id, Teacher.user_id.is_not(None)
            )
        )
    )
    if current_teacher_id is not None:
        cur = db.get(Teacher, current_teacher_id)
        if cur is not None and cur.user_id is not None:
            bound.discard(cur.user_id)
    teacher_user_ids = db.scalars(
        select(UserRole.user_id).where(UserRole.role == Role.teacher.value)
    )
    available = [uid for uid in set(teacher_user_ids) if uid not in bound]
    if not available:
        return []
    return db.scalars(
        select(User).where(User.id.in_(available), User.is_active.is_(True)).order_by(User.username)
    ).all()


@router.get("/teachers", response_model=list[TeacherOut])
def list_teachers(
    semester_id: int = Query(...),
    q: str | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    _: object = Depends(viewer),
):
    stmt = select(Teacher).where(Teacher.semester_id == semester_id)
    if q:
        stmt = stmt.where(Teacher.name.contains(q))
    if active_only:
        stmt = stmt.where(Teacher.is_active.is_(True))
    return db.scalars(stmt.order_by(Teacher.name)).all()


@router.post("/teachers", response_model=TeacherOut, status_code=status.HTTP_201_CREATED)
def create_teacher(
    body: TeacherIn,
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(editor),
) -> Teacher:
    _require_writable(db, semester_id)
    _validate_teacher_user(db, semester_id, body.user_id)
    teacher = Teacher(
        semester_id=semester_id,
        name=body.name,
        id_last4=body.id_last4,
        base_periods=body.base_periods,
        admin_title=body.admin_title,
        admin_reduction=body.admin_reduction,
        is_external=body.is_external,
        is_active=body.is_active,
        email=body.email,
        phone=body.phone,
        line_id=body.line_id,
        user_id=body.user_id,
        subjects=_resolve_subjects(db, semester_id, body.subject_ids),
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


@router.get("/teachers/{teacher_id}", response_model=TeacherOut)
def get_teacher(
    teacher_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
) -> Teacher:
    teacher = db.get(Teacher, teacher_id)
    if teacher is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到教师")
    return teacher


@router.patch("/teachers/{teacher_id}", response_model=TeacherOut)
def update_teacher(
    teacher_id: int, body: TeacherIn, db: Session = Depends(get_db), _: object = Depends(editor)
) -> Teacher:
    teacher = db.get(Teacher, teacher_id)
    if teacher is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到教师")
    _require_writable(db, teacher.semester_id)
    _validate_teacher_user(db, teacher.semester_id, body.user_id, exclude_teacher_id=teacher.id)
    teacher.name = body.name
    teacher.id_last4 = body.id_last4
    teacher.base_periods = body.base_periods
    teacher.admin_title = body.admin_title
    teacher.admin_reduction = body.admin_reduction
    teacher.is_external = body.is_external
    teacher.is_active = body.is_active
    teacher.email = body.email
    teacher.phone = body.phone
    teacher.line_id = body.line_id
    teacher.user_id = body.user_id
    teacher.subjects = _resolve_subjects(db, teacher.semester_id, body.subject_ids)
    db.commit()
    db.refresh(teacher)
    return teacher


@router.delete("/teachers/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher(
    teacher_id: int, db: Session = Depends(get_db), _: object = Depends(editor)
) -> None:
    teacher = db.get(Teacher, teacher_id)
    if teacher is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到教师")
    _require_writable(db, teacher.semester_id)
    homeroom_count = db.scalar(
        select(func.count()).select_from(ClassUnit).where(
            ClassUnit.homeroom_teacher_id == teacher_id
        )
    )
    if homeroom_count:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"此教师为 {homeroom_count} 个班级的班主任,无法删除;请先更换班主任,或将教师设为离职",
        )
    db.delete(teacher)
    db.commit()


@router.get("/teachers/{teacher_id}/time-rules", response_model=list[TeacherTimeRuleOut])
def get_time_rules(
    teacher_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
):
    teacher = db.get(Teacher, teacher_id)
    if teacher is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到教师")
    return teacher.time_rules


@router.put("/teachers/{teacher_id}/time-rules", response_model=list[TeacherTimeRuleOut])
def replace_time_rules(
    teacher_id: int,
    rules: list[TeacherTimeRuleIn],
    db: Session = Depends(get_db),
    _: object = Depends(editor),
):
    teacher = db.get(Teacher, teacher_id)
    if teacher is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到教师")
    _require_writable(db, teacher.semester_id)
    seen: set[tuple[int, int]] = set()
    for r in rules:
        key = (r.weekday, r.period_no)
        if key in seen:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "同一单元格不可重复设置规则")
        seen.add(key)
    teacher.time_rules.clear()
    db.flush()
    for r in rules:
        teacher.time_rules.append(
            TeacherTimeRule(weekday=r.weekday, period_no=r.period_no, rule_type=r.rule_type.value)
        )
    db.commit()
    db.refresh(teacher)
    return teacher.time_rules


# ── 教室/场地 ──────────────────────────────
@router.get("/rooms", response_model=list[RoomOut])
def list_rooms(
    semester_id: int = Query(...),
    q: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(viewer),
):
    stmt = select(Room).where(Room.semester_id == semester_id)
    if q:
        stmt = stmt.where(Room.name.contains(q))
    return db.scalars(stmt.order_by(Room.name)).all()


@router.post("/rooms", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
def create_room(
    body: RoomIn,
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(editor),
) -> Room:
    _require_writable(db, semester_id)
    room = Room(
        semester_id=semester_id,
        name=body.name,
        room_type=body.room_type.value,
        capacity=body.capacity,
        subjects=_resolve_subjects(db, semester_id, body.subject_ids),
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.patch("/rooms/{room_id}", response_model=RoomOut)
def update_room(
    room_id: int, body: RoomIn, db: Session = Depends(get_db), _: object = Depends(editor)
) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到教室/场地")
    _require_writable(db, room.semester_id)
    room.name = body.name
    room.room_type = body.room_type.value
    room.capacity = body.capacity
    room.subjects = _resolve_subjects(db, room.semester_id, body.subject_ids)
    db.commit()
    db.refresh(room)
    return room


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(room_id: int, db: Session = Depends(get_db), _: object = Depends(editor)) -> None:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到教室/场地")
    _require_writable(db, room.semester_id)
    db.delete(room)
    db.commit()


# ── 班级 ──────────────────────────────
@router.get("/class-units", response_model=list[ClassUnitOut])
def list_class_units(
    semester_id: int = Query(...),
    q: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(viewer),
):
    stmt = select(ClassUnit).where(ClassUnit.semester_id == semester_id)
    if q:
        stmt = stmt.where(ClassUnit.name.contains(q))
    return db.scalars(stmt.order_by(ClassUnit.grade, ClassUnit.name)).all()


def _require_unique_class_name(
    db: Session, semester_id: int, name: str, *, exclude_id: int | None = None
) -> None:
    """同学期不得有两个同名班级(M6-5)。

    冲突信息、课表、导出全都以班名指称班级——同学期出现两个「301」时,排课管理员在页面上
    无法区分具体班级。DB 有 uq 约束作为最后保障,这里先拦截并返回易懂说明。
    """
    stmt = select(ClassUnit).where(
        ClassUnit.semester_id == semester_id, ClassUnit.name == name
    )
    if exclude_id is not None:
        stmt = stmt.where(ClassUnit.id != exclude_id)
    if db.scalar(stmt):
        raise HTTPException(status.HTTP_409_CONFLICT, f"本学期已有班级「{name}」")


def _validate_homeroom(db: Session, semester_id: int, teacher_id: int | None) -> None:
    if teacher_id is None:
        return
    teacher = db.get(Teacher, teacher_id)
    if teacher is None or teacher.semester_id != semester_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "班主任无效或不属于本学期")


def _validate_period_table(db: Session, semester_id: int, table_id: int | None) -> None:
    if table_id is None:
        return
    table = db.get(PeriodTable, table_id)
    if table is None or table.semester_id != semester_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "作息时间表无效或不属于本学期")


@router.post("/class-units", response_model=ClassUnitOut, status_code=status.HTTP_201_CREATED)
def create_class_unit(
    body: ClassUnitIn,
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(editor),
) -> ClassUnit:
    _require_writable(db, semester_id)
    _require_unique_class_name(db, semester_id, body.name)
    _validate_homeroom(db, semester_id, body.homeroom_teacher_id)
    _validate_period_table(db, semester_id, body.period_table_id)
    cu = ClassUnit(
        semester_id=semester_id,
        grade=body.grade,
        name=body.name,
        track=body.track.value,
        department=body.department,
        student_count=body.student_count,
        homeroom_teacher_id=body.homeroom_teacher_id,
        period_table_id=body.period_table_id,
    )
    db.add(cu)
    db.commit()
    db.refresh(cu)
    return cu


@router.patch("/class-units/{class_id}", response_model=ClassUnitOut)
def update_class_unit(
    class_id: int, body: ClassUnitIn, db: Session = Depends(get_db), _: object = Depends(editor)
) -> ClassUnit:
    cu = db.get(ClassUnit, class_id)
    if cu is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到班级")
    _require_writable(db, cu.semester_id)
    _require_unique_class_name(db, cu.semester_id, body.name, exclude_id=cu.id)
    _validate_homeroom(db, cu.semester_id, body.homeroom_teacher_id)
    _validate_period_table(db, cu.semester_id, body.period_table_id)
    cu.grade = body.grade
    cu.name = body.name
    cu.track = body.track.value
    cu.department = body.department
    cu.student_count = body.student_count
    cu.homeroom_teacher_id = body.homeroom_teacher_id
    cu.period_table_id = body.period_table_id
    db.commit()
    db.refresh(cu)
    return cu


@router.get("/class-units/{class_id}/period-table", response_model=PeriodTableOut)
def class_period_table(
    class_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
) -> PeriodTable:
    """该班级所属的完整作息时间表(含午休/早自习等非上课单元格),供排课工作台渲染。

    统一经 resolve_period_table,前端不需自行处理「指定表 vs 学期默认表」。
    """
    cu = db.get(ClassUnit, class_id)
    if cu is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到班级")
    table = pt_service.resolve_period_table(db, cu)
    if table is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "此学期尚无任何作息时间表")
    return table


@router.get("/class-units/{class_id}/available-slots", response_model=list[AvailableSlot])
def class_available_slots(
    class_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
) -> list[AvailableSlot]:
    """返回该班级的可排课时段(依所属作息时间表,空则用学期默认表)。M2 排课引擎使用。"""
    cu = db.get(ClassUnit, class_id)
    if cu is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到班级")
    table = pt_service.resolve_period_table(db, cu)
    if table is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "此学期尚无任何作息时间表")
    rows = pt_service.regular_slots(db, table.id)
    return [
        AvailableSlot(
            weekday=p.weekday, period_no=p.period_no, name=p.name,
            start_time=p.start_time, end_time=p.end_time,
        )
        for p in rows
    ]


@router.delete("/class-units/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class_unit(
    class_id: int, db: Session = Depends(get_db), _: object = Depends(editor)
) -> None:
    cu = db.get(ClassUnit, class_id)
    if cu is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到班级")
    _require_writable(db, cu.semester_id)
    db.delete(cu)
    db.commit()
