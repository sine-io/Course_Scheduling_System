"""教学任务 API:排课单位(走班群组)、教学任务 CRUD、课时/负载统计。

权限:读取 = 排课管理员/教务主任;写入 = 排课管理员(admin 统一通过)。
所有资源以 semester_id 为范围。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.db import get_db
from app.models.assignment import (
    AssignmentTeacher,
    BlockRule,
    CourseAssignment,
    SchedulingUnit,
    SchedulingUnitType,
)
from app.models.basedata import ClassUnit, Room, Subject, Teacher
from app.models.semester import Semester
from app.models.user import Role
from app.schemas.assignment import (
    AssignmentIn,
    AssignmentOut,
    ClassLoad,
    GroupIn,
    SchedulingUnitOut,
    TeacherLoad,
)
from app.services import assignments as svc

router = APIRouter(tags=["assignments"])

viewer = require_roles(Role.scheduler, Role.director)
editor = require_roles(Role.scheduler)


def _require_semester(db: Session, semester_id: int) -> None:
    if db.get(Semester, semester_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到学期")


def _domain(exc: svc.DomainError) -> HTTPException:
    return HTTPException(exc.status_code, exc.message)


# ── 走班群组 ──────────────────────────
@router.get("/scheduling-units", response_model=list[SchedulingUnitOut])
def list_groups(
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(viewer),
):
    """列出走班群组(single 单班单位为内部用,不在此列出)。"""
    units = db.scalars(
        select(SchedulingUnit).where(
            SchedulingUnit.semester_id == semester_id,
            SchedulingUnit.unit_type == SchedulingUnitType.group.value,
        ).order_by(SchedulingUnit.name)
    ).all()
    return [svc.serialize_unit(u) for u in units]


@router.post(
    "/scheduling-units", response_model=SchedulingUnitOut, status_code=status.HTTP_201_CREATED
)
def create_group(
    body: GroupIn,
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(editor),
):
    _require_semester(db, semester_id)
    try:
        unit = svc.create_group(db, semester_id, body.name, body.class_ids)
    except svc.DomainError as e:
        raise _domain(e) from e
    db.commit()
    db.refresh(unit)
    return svc.serialize_unit(unit)


@router.delete("/scheduling-units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    unit_id: int, db: Session = Depends(get_db), _: object = Depends(editor)
) -> None:
    unit = db.get(SchedulingUnit, unit_id)
    if unit is None or unit.unit_type != SchedulingUnitType.group.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到走班群组")
    db.delete(unit)  # 级联删除其教学任务
    db.commit()


# ── 统计(需在 /assignments/{id} 之前注册)────
@router.get("/assignments/teacher-load", response_model=list[TeacherLoad])
def teacher_load(
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(viewer),
):
    return svc.teacher_loads(db, semester_id)


@router.get("/assignments/class-load", response_model=list[ClassLoad])
def class_load(
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(viewer),
):
    return svc.class_loads(db, semester_id)


# ── 教学任务 CRUD ─────────────────────────
@router.get("/assignments", response_model=list[AssignmentOut])
def list_assignments(
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(viewer),
):
    items = db.scalars(
        select(CourseAssignment).where(CourseAssignment.semester_id == semester_id)
        .order_by(CourseAssignment.id)
    ).all()
    return [svc.serialize_assignment(a) for a in items]


def _resolve_unit(db: Session, semester_id: int, body: AssignmentIn) -> SchedulingUnit:
    if body.class_id is not None:
        cu = db.get(ClassUnit, body.class_id)
        if cu is None or cu.semester_id != semester_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "班级无效或不属于本学期")
        return svc.get_or_create_single_unit(db, cu)
    unit = db.get(SchedulingUnit, body.scheduling_unit_id or -1)
    if unit is None or unit.semester_id != semester_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "排课单位无效或不属于本学期")
    return unit


def _validate_refs(db: Session, semester_id: int, body: AssignmentIn) -> None:
    subject = db.get(Subject, body.subject_id)
    if subject is None or subject.semester_id != semester_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "科目无效或不属于本学期")
    if body.room_id is not None:
        room = db.get(Room, body.room_id)
        if room is None or room.semester_id != semester_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "教室/场地无效或不属于本学期")
    teacher_ids = [t.teacher_id for t in body.teachers]
    found = db.scalars(
        select(Teacher.id).where(
            Teacher.id.in_(teacher_ids), Teacher.semester_id == semester_id
        )
    ).all()
    if set(found) != set(teacher_ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "教师列表含无效或跨学期的教师")


def _apply(db: Session, assignment: CourseAssignment, body: AssignmentIn) -> None:
    assignment.subject_id = body.subject_id
    assignment.periods_per_week = body.periods_per_week
    assignment.required_room_type = (
        body.required_room_type.value if body.required_room_type else None
    )
    assignment.room_id = body.room_id
    assignment.lock_room = body.lock_room
    assignment.teachers.clear()
    assignment.block_rules.clear()
    db.flush()
    for t in body.teachers:
        assignment.teachers.append(
            AssignmentTeacher(teacher_id=t.teacher_id, is_lead=t.is_lead)
        )
    for b in body.block_rules:
        assignment.block_rules.append(
            BlockRule(block_size=b.block_size, count_per_week=b.count_per_week)
        )


@router.post("/assignments", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
def create_assignment(
    body: AssignmentIn,
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(editor),
):
    _require_semester(db, semester_id)
    _validate_refs(db, semester_id, body)
    unit = _resolve_unit(db, semester_id, body)
    assignment = CourseAssignment(
        semester_id=semester_id, scheduling_unit_id=unit.id, subject_id=body.subject_id,
        periods_per_week=body.periods_per_week,
    )
    db.add(assignment)
    db.flush()
    _apply(db, assignment, body)
    db.commit()
    db.refresh(assignment)
    return svc.serialize_assignment(assignment)


@router.get("/assignments/{assignment_id}", response_model=AssignmentOut)
def get_assignment(
    assignment_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
):
    a = db.get(CourseAssignment, assignment_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到教学任务")
    return svc.serialize_assignment(a)


@router.patch("/assignments/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: int,
    body: AssignmentIn,
    db: Session = Depends(get_db),
    _: object = Depends(editor),
):
    a = db.get(CourseAssignment, assignment_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到教学任务")
    _validate_refs(db, a.semester_id, body)
    unit = _resolve_unit(db, a.semester_id, body)
    a.scheduling_unit_id = unit.id
    _apply(db, a, body)
    db.commit()
    db.refresh(a)
    return svc.serialize_assignment(a)


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(
    assignment_id: int, db: Session = Depends(get_db), _: object = Depends(editor)
) -> None:
    a = db.get(CourseAssignment, assignment_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到教学任务")
    db.delete(a)
    db.commit()
