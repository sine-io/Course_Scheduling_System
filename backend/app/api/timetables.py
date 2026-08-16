"""课表 API:草稿 CRUD、单元格放入/移动/删除、锁定、实时冲突检查。

放入或移动课程时通过 conflict_checker 验证硬约束；违反约束时返回 409 和易懂的冲突说明。
走班群组:放入/移动/删除/锁定均连动同群组全部教学任务(H7 同时段)。
"""

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import high_risk_http
from app.core.auth import get_active_user
from app.core.db import get_db
from app.core.permissions import can_publish_timetable, core_editor, core_viewer
from app.models.assignment import CourseAssignment
from app.models.basedata import ClassUnit, Room, Teacher
from app.models.period import PeriodTable
from app.models.semester import Semester
from app.models.timetable import ScheduleEntry, Timetable, TimetableStatus
from app.models.user import User
from app.schemas.high_risk import HighRiskConfirmation
from app.schemas.timetable import (
    CheckRequest,
    CheckResponse,
    CompletenessOut,
    MoveRequest,
    NamedBrief,
    PlaceRequest,
    PublicationCheckOut,
    PublicationConfirmation,
    PublicationSemesterOut,
    PublicationTargetOut,
    PublicClass,
    PublicPeriodTable,
    PublicSemester,
    PublishedTimetableOut,
    ScheduleEntryOut,
    TimetableBrief,
    TimetableCreate,
    TimetableOut,
    TimetableRename,
)
from app.services import conflict_checker as cc
from app.services import semester_context
from app.services import timetable_publish as pub
from app.services.school_rules import (
    SemesterNotReadyError,
    assert_semester_ready,
)
from app.services.teachers import current_teacher

router = APIRouter(tags=["timetables"])

viewer = core_viewer
editor = core_editor


def _get_timetable(db: Session, timetable_id: int) -> Timetable:
    tt = db.get(Timetable, timetable_id)
    if tt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到课表")
    return tt


def _require_writable(db: Session, semester_id: int) -> Semester:
    try:
        return semester_context.require_writable(db, semester_id)
    except semester_context.SemesterContextError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": exc.message}) from exc


def _require_draft(tt: Timetable) -> Timetable:
    """已发布/已归档的课表是快照,不得再改单元格(architecture.md D4)。"""
    if tt.status != TimetableStatus.draft.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "此课表已发布或已归档,不可编辑;请复制为新草稿后修改",
        )
    return tt


def _get_assignment(db: Session, semester_id: int, assignment_id: int) -> CourseAssignment:
    a = db.get(CourseAssignment, assignment_id)
    if a is None or a.semester_id != semester_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "教学任务无效或不属于本课表学期")
    return a


def _serialize_entry(e: ScheduleEntry) -> ScheduleEntryOut:
    a = e.assignment
    su = a.scheduling_unit
    # 单元格教室/场地优先于教学任务教室/场地(引擎逐格指派、调课与代课教室变更均写在单元格上)
    room = e.room if e.room is not None else a.room
    return ScheduleEntryOut(
        id=e.id, course_assignment_id=e.course_assignment_id,
        weekday=e.weekday, period_no=e.period_no, span=e.span, locked=e.locked,
        subject=a.subject.name,
        teachers=[at.teacher.name for at in a.teachers],
        classes=[m.class_unit.name for m in su.members],
        unit_type=su.unit_type, unit_name=su.name,
        room=room.name if room else None,
        teacher_ids=[at.teacher_id for at in a.teachers],
        class_ids=[m.class_unit_id for m in su.members],
        room_id=e.effective_room_id,
    )


def _conflict_409(conflicts: list[cc.Conflict]) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={
            "message": "与硬约束冲突,无法排入",
            "conflicts": [{"code": c.code, "message": c.message} for c in conflicts],
        },
    )


def _completeness(report: dict) -> dict:
    return report


def _reject_publication(
    db: Session,
    user: User,
    timetable: Timetable | None,
    timetable_id: int,
    *,
    status_code: int,
    code: str,
    message: str,
    extra: dict | None = None,
) -> NoReturn:
    pub.record_publication_attempt(
        db,
        user,
        timetable,
        target_id=timetable_id,
        result="rejected",
        reason=code,
        detail=message,
    )
    db.commit()
    detail = {"code": code, "message": message}
    if extra:
        detail.update(extra)
    raise HTTPException(status_code, detail=detail)


def _slot_siblings(
    db: Session, timetable_id: int, unit_id: int, weekday: int, period_no: int
) -> list[ScheduleEntry]:
    """同一排课单位在「同一单元格」的全部单元格。

    走班群组:该时段开的多门课(H7 须同进同出);单班:即该格本身。
    以单元格为范围而非整个排课单位,否则同班其他科目的单元格会被误连动。
    """
    return list(
        db.scalars(
            select(ScheduleEntry)
            .join(CourseAssignment, ScheduleEntry.course_assignment_id == CourseAssignment.id)
            .where(
                ScheduleEntry.timetable_id == timetable_id,
                CourseAssignment.scheduling_unit_id == unit_id,
                ScheduleEntry.weekday == weekday,
                ScheduleEntry.period_no == period_no,
            )
        )
    )


def _placed_periods(db: Session, timetable_id: int, assignment_id: int) -> int:
    """该教学任务在此课表已排入的节数(连堂以 span 计)。"""
    total = db.scalar(
        select(func.coalesce(func.sum(ScheduleEntry.span), 0)).where(
            ScheduleEntry.timetable_id == timetable_id,
            ScheduleEntry.course_assignment_id == assignment_id,
        )
    )
    return int(total or 0)


# ── 课表草稿 ──────────────────────────
@router.get("/timetables", response_model=list[TimetableBrief])
def list_timetables(
    semester_id: int = Query(...), db: Session = Depends(get_db), _: object = Depends(viewer)
):
    tts = db.scalars(
        select(Timetable).where(Timetable.semester_id == semester_id).order_by(Timetable.id)
    ).all()
    out = []
    for tt in tts:
        n = db.scalar(
            select(func.count()).select_from(ScheduleEntry).where(
                ScheduleEntry.timetable_id == tt.id
            )
        )
        out.append(TimetableBrief(
            id=tt.id, semester_id=tt.semester_id, name=tt.name, status=tt.status,
            publication_state=pub.publication_state(db, tt), entry_count=n or 0,
        ))
    return out


@router.post("/timetables", response_model=TimetableOut, status_code=status.HTTP_201_CREATED)
def create_timetable(
    body: TimetableCreate,
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(editor),
):
    _require_writable(db, semester_id)
    tt = Timetable(semester_id=semester_id, name=body.name)
    db.add(tt)
    db.commit()
    db.refresh(tt)
    return TimetableOut(
        id=tt.id, semester_id=tt.semester_id, name=tt.name, status=tt.status, entries=[]
    )


@router.get("/timetables/{timetable_id}", response_model=TimetableOut)
def get_timetable(
    timetable_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
):
    tt = _get_timetable(db, timetable_id)
    rows = db.scalars(
        select(ScheduleEntry).where(ScheduleEntry.timetable_id == tt.id)
    ).all()
    entries = sorted(rows, key=lambda e: (e.weekday, e.period_no))
    return TimetableOut(
        id=tt.id, semester_id=tt.semester_id, name=tt.name, status=tt.status,
        entries=[_serialize_entry(e) for e in entries],
    )


@router.patch("/timetables/{timetable_id}", response_model=TimetableOut)
def rename_timetable(
    timetable_id: int,
    body: TimetableRename,
    db: Session = Depends(get_db),
    _: object = Depends(editor),
):
    tt = _get_timetable(db, timetable_id)
    _require_writable(db, tt.semester_id)
    tt.name = body.name
    db.commit()
    return get_timetable(timetable_id, db, None)


@router.post(
    "/timetables/{timetable_id}/duplicate",
    response_model=TimetableOut,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_timetable(
    timetable_id: int,
    body: TimetableRename,
    db: Session = Depends(get_db),
    _: object = Depends(editor),
):
    """复制为新草稿(含全部单元格);两份草稿互不影响。"""
    src = _get_timetable(db, timetable_id)
    _require_writable(db, src.semester_id)
    new = pub.duplicate(db, src, body.name)
    db.commit()
    return get_timetable(new.id, db, None)


@router.get("/timetables/{timetable_id}/completeness", response_model=CompletenessOut)
def timetable_completeness(
    timetable_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
):
    """发布前完整性检查:列出尚未排完的教学任务。"""
    tt = _get_timetable(db, timetable_id)
    return _completeness(pub.completeness(db, tt))


@router.post(
    "/timetables/{timetable_id}/publication-check",
    response_model=PublicationCheckOut,
)
def check_timetable_publication(
    timetable_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(editor),
):
    """Check the current draft and persist the exact snapshot eligible for confirmation."""
    tt = _get_timetable(db, timetable_id)
    try:
        semester = semester_context.require_writable(db, tt.semester_id, lock="update")
    except semester_context.SemesterContextError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": exc.message}) from exc
    _require_draft(tt)
    try:
        assert_semester_ready(db, semester)
    except SemesterNotReadyError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "semester_not_ready",
                "message": str(exc),
                "semester_id": exc.semester_id,
                "issues": exc.issues,
            },
        ) from exc
    report = _completeness(pub.completeness(db, tt))
    fingerprint, checked_at = pub.record_publication_check(
        db, tt, passed=report["complete"]
    )
    db.commit()
    return PublicationCheckOut(
        semester=PublicationSemesterOut(id=semester.id, label=semester.label),
        version=PublicationTargetOut(id=tt.id, name=tt.name),
        passed=report["complete"],
        requires_force=not report["complete"],
        completeness=CompletenessOut(**report),
        issues=[],
        fingerprint=fingerprint,
        checked_at=checked_at,
    )


@router.post("/timetables/{timetable_id}/publish", response_model=TimetableOut)
def publish_timetable(
    timetable_id: int,
    confirmation: PublicationConfirmation | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    """Confirm a checked draft, then atomically replace the published timetable."""
    tt = db.get(Timetable, timetable_id)
    if not can_publish_timetable(user):
        _reject_publication(
            db,
            user,
            tt,
            timetable_id,
            status_code=status.HTTP_403_FORBIDDEN,
            code="publication_permission_denied",
            message="当前角色没有课表发布权限",
        )
    if tt is None:
        _reject_publication(
            db,
            user,
            None,
            timetable_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="timetable_not_found",
            message="找不到课表",
        )
    # Semester writes take the context lock before target rows; publication keeps that order.
    try:
        semester = semester_context.require_writable(db, tt.semester_id, lock="update")
    except semester_context.SemesterContextError as exc:
        _reject_publication(
            db,
            user,
            tt,
            timetable_id,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
        )
    locked_tt = db.scalar(
        select(Timetable)
        .where(Timetable.id == timetable_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_tt is None:
        _reject_publication(
            db,
            user,
            tt,
            timetable_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="timetable_not_found",
            message="找不到课表",
        )
    tt = locked_tt
    if tt.status != TimetableStatus.draft.value:
        _reject_publication(
            db,
            user,
            tt,
            timetable_id,
            status_code=status.HTTP_409_CONFLICT,
            code="publication_already_submitted",
            message="此课表已经发布或归档，请刷新版本列表",
        )
    try:
        assert_semester_ready(db, semester)
    except SemesterNotReadyError as exc:
        _reject_publication(
            db,
            user,
            tt,
            timetable_id,
            status_code=status.HTTP_409_CONFLICT,
            code="semester_not_ready",
            message=str(exc),
            extra={"semester_id": exc.semester_id, "issues": exc.issues},
        )
    confirmation_error = pub.publication_confirmation_error(
        db, tt, confirmation.fingerprint if confirmation else ""
    )
    if confirmation_error:
        code, message = confirmation_error
        _reject_publication(
            db,
            user,
            tt,
            timetable_id,
            status_code=status.HTTP_409_CONFLICT,
            code=code,
            message=message,
        )
    report = _completeness(pub.completeness(db, tt))
    force = confirmation.force if confirmation else False
    if not report["complete"] and not force:
        _reject_publication(
            db,
            user,
            tt,
            timetable_id,
            status_code=status.HTTP_409_CONFLICT,
            code="publication_check_failed",
            message="尚有教学任务未排完，确认后可强制发布",
            extra={"completeness": report},
        )
    pub.publish(db, tt, user, forced=not report["complete"])
    db.commit()
    # 条件 D:重新发布后,提醒仍有多少「今日之后」的调课与代课是依旧课表展开的
    out = get_timetable(timetable_id, db, None)
    out.stale_affected = pub.stale_future_affected_count(db, tt.semester_id)
    return out


@router.delete("/timetables/{timetable_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_timetable(
    timetable_id: int,
    confirmation: HighRiskConfirmation | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
) -> None:
    tt = _get_timetable(db, timetable_id)
    attempt = high_risk_http.begin(
        db,
        user,
        confirmation,
        action="delete_timetable",
        target_type="timetable",
        target_id=tt.id,
        semester_id=tt.semester_id,
        target_version=tt.name,
        expected_target=f"timetable:{tt.id}",
        impact=f"永久删除课表「{tt.name}」及其中全部排课条目",
    )
    try:
        _require_writable(db, tt.semester_id)
    except HTTPException as exc:
        high_risk_http.reject(db, attempt.id, exc)
    db.delete(tt)
    high_risk_http.complete_delete(
        db, attempt.id, detail=f"已永久删除课表「{tt.name}」"
    )


# ── 全员只读课表查询(含 teacher 角色)────
@router.get("/published/semesters", response_model=list[PublicSemester])
def published_semesters(db: Session = Depends(get_db), _: User = Depends(get_active_user)):
    """有已发布课表的学期。"""
    rows = db.scalars(
        select(Semester)
        .join(Timetable, Timetable.semester_id == Semester.id)
        .where(Timetable.status == TimetableStatus.published.value)
        .order_by(Semester.academic_year.desc(), Semester.term.desc())
    ).all()
    return [PublicSemester(id=s.id, label=s.label) for s in rows]


@router.get("/published/my-teacher", response_model=NamedBrief | None)
def published_my_teacher(
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    """登录者在该学期绑定的教师基础信息(无绑定回 null),供教师端默认显示本人课表。"""
    t = current_teacher(db, user, semester_id)
    return NamedBrief(id=t.id, name=t.name) if t else None


@router.get("/published/timetable", response_model=PublishedTimetableOut | None)
def published_timetable(
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_active_user),
):
    """该学期的已发布课表 + 查询页所需选项与作息时间表(教师端只需这一支)。"""
    tt = db.scalar(
        select(Timetable).where(
            Timetable.semester_id == semester_id,
            Timetable.status == TimetableStatus.published.value,
        )
    )
    if tt is None:
        return None
    sem = db.get(Semester, semester_id)
    rows = db.scalars(select(ScheduleEntry).where(ScheduleEntry.timetable_id == tt.id)).all()
    classes = db.scalars(
        select(ClassUnit).where(ClassUnit.semester_id == semester_id)
        .order_by(ClassUnit.grade, ClassUnit.name)
    ).all()
    teachers = db.scalars(
        select(Teacher).where(Teacher.semester_id == semester_id).order_by(Teacher.name)
    ).all()
    rooms = db.scalars(
        select(Room).where(Room.semester_id == semester_id).order_by(Room.name)
    ).all()
    tables = db.scalars(
        select(PeriodTable).where(PeriodTable.semester_id == semester_id)
    ).all()
    return PublishedTimetableOut(
        id=tt.id, semester_id=semester_id, semester_label=sem.label if sem else "",
        name=tt.name, status=tt.status,
        entries=[_serialize_entry(e) for e in sorted(rows, key=lambda x: (x.weekday, x.period_no))],
        classes=[
            PublicClass(id=c.id, name=c.name, grade=c.grade, period_table_id=c.period_table_id)
            for c in classes
        ],
        teachers=[NamedBrief(id=t.id, name=t.name) for t in teachers],
        rooms=[NamedBrief(id=r.id, name=r.name) for r in rooms],
        period_tables=[
            PublicPeriodTable(
                id=p.id, name=p.name, num_weekdays=p.num_weekdays, is_default=p.is_default,
                periods=list(p.periods),
            )
            for p in tables
        ],
    )


# ── 冲突检查(不写入)────────────────
@router.post("/timetables/{timetable_id}/check-conflict", response_model=CheckResponse)
def check_conflict(
    timetable_id: int,
    body: CheckRequest,
    db: Session = Depends(get_db),
    _: object = Depends(viewer),
):
    tt = _get_timetable(db, timetable_id)
    a = _get_assignment(db, tt.semester_id, body.course_assignment_id)
    ignore_ids: set[int] = set()
    if body.ignore_entry_id is not None:
        e = db.get(ScheduleEntry, body.ignore_entry_id)
        if e is not None and e.timetable_id == tt.id:
            # 移动:忽略被搬动的那一格(群组则含同格的兄弟课)
            ignore_ids = {
                s.id for s in _slot_siblings(
                    db, tt.id, e.assignment.scheduling_unit_id, e.weekday, e.period_no
                )
            }
    conflicts = cc.check_conflict(
        db, tt, a, body.weekday, body.period_no, body.span, ignore_ids, body.room_id
    )
    return CheckResponse(
        ok=not conflicts,
        conflicts=[
            {"code": conflict.code, "message": conflict.message}
            for conflict in conflicts
        ],
    )


# ── 单元格放入/移动/删除/锁定 ──────────
@router.post("/timetables/{timetable_id}/entries", response_model=TimetableOut,
             status_code=status.HTTP_201_CREATED)
def place_entry(
    timetable_id: int,
    body: PlaceRequest,
    db: Session = Depends(get_db),
    _: object = Depends(editor),
):
    tt = _get_timetable(db, timetable_id)
    _require_writable(db, tt.semester_id)
    _require_draft(tt)
    a = _get_assignment(db, tt.semester_id, body.course_assignment_id)
    if body.room_id is not None:
        room = db.get(Room, body.room_id)
        if room is None or room.semester_id != tt.semester_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "教室/场地无效或不属于本课表学期")
    placements = cc.placements_for(db, a, body.weekday, body.period_no, body.span, body.room_id)
    # H8 守恒(放入面):不得超过该教学任务的每周节数
    for pl in placements:
        placed = _placed_periods(db, tt.id, pl.assignment.id)
        if placed + pl.span > pl.assignment.periods_per_week:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"「{pl.assignment.subject.name}」已排 {placed} 节,"
                f"再排 {pl.span} 节将超过每周 {pl.assignment.periods_per_week} 节",
            )
    conflicts = cc.check_conflict(
        db, tt, a, body.weekday, body.period_no, body.span, room_id=body.room_id
    )
    if conflicts:
        raise _conflict_409(conflicts)
    for pl in placements:
        db.add(ScheduleEntry(
            timetable_id=tt.id, course_assignment_id=pl.assignment.id,
            weekday=pl.weekday, period_no=pl.period_no, span=pl.span,
            room_id=pl.room_id,
        ))
    db.commit()
    return get_timetable(timetable_id, db, None)


@router.patch("/timetables/{timetable_id}/entries/{entry_id}", response_model=TimetableOut)
def move_entry(
    timetable_id: int, entry_id: int, body: MoveRequest,
    db: Session = Depends(get_db), _: object = Depends(editor),
):
    tt = _get_timetable(db, timetable_id)
    _require_writable(db, tt.semester_id)
    _require_draft(tt)
    e = db.get(ScheduleEntry, entry_id)
    if e is None or e.timetable_id != tt.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到单元格")
    if e.locked:
        raise HTTPException(status.HTTP_409_CONFLICT, "单元格已锁定,请先解锁再移动")
    a = e.assignment
    # 同格兄弟(群组同时段的多门课)一起搬;检查时忽略自己这几格
    moving = _slot_siblings(db, tt.id, a.scheduling_unit_id, e.weekday, e.period_no)
    conflicts = cc.check_conflict(
        db, tt, a, body.weekday, body.period_no, e.span,
        ignore_entry_ids={s.id for s in moving},
        room_id=e.room_id,  # 搬动时沿用单元格现有的教室/场地
    )
    if conflicts:
        raise _conflict_409(conflicts)
    for sib in moving:
        sib.weekday = body.weekday
        sib.period_no = body.period_no
    db.commit()
    return get_timetable(timetable_id, db, None)


@router.post("/timetables/{timetable_id}/entries/{entry_id}/lock", response_model=TimetableOut)
def lock_entry(
    timetable_id: int, entry_id: int, locked: bool = Query(True),
    db: Session = Depends(get_db), _: object = Depends(editor),
):
    tt = _get_timetable(db, timetable_id)
    _require_writable(db, tt.semester_id)
    _require_draft(tt)
    e = db.get(ScheduleEntry, entry_id)
    if e is None or e.timetable_id != tt.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到单元格")
    for sib in _slot_siblings(db, tt.id, e.assignment.scheduling_unit_id, e.weekday, e.period_no):
        sib.locked = locked
    db.commit()
    return get_timetable(timetable_id, db, None)


@router.delete(
    "/timetables/{timetable_id}/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_entry(
    timetable_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(editor),
) -> None:
    tt = _get_timetable(db, timetable_id)
    _require_writable(db, tt.semester_id)
    _require_draft(tt)
    e = db.get(ScheduleEntry, entry_id)
    if e is None or e.timetable_id != tt.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到单元格")
    if e.locked:
        raise HTTPException(status.HTTP_409_CONFLICT, "单元格已锁定,请先解锁再移除")
    for sib in _slot_siblings(db, tt.id, e.assignment.scheduling_unit_id, e.weekday, e.period_no):
        db.delete(sib)
    db.commit()
