"""学期与作息时间表 API。

权限:读取 = 排课管理员/教务主任;写入 = 排课管理员(admin 统一通过)。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import high_risk_http
from app.core.auth import get_active_user
from app.core.db import get_db
from app.core.permissions import core_editor, core_viewer
from app.models.basedata import ClassUnit, Room, Subject, Teacher
from app.models.period import Period, PeriodTable
from app.models.semester import Semester
from app.models.user import Role, User
from app.schemas.high_risk import HighRiskConfirmation
from app.schemas.semester import (
    AvailableSlot,
    PeriodIn,
    PeriodSetupApply,
    PeriodTableCreate,
    PeriodTableOut,
    PeriodTableUpdate,
    SemesterContextOut,
    SemesterContextSwitch,
    SemesterCopyRequest,
    SemesterCreate,
    SemesterListItem,
    SemesterOut,
    SemesterUpdate,
)
from app.schemas.wizard import SemesterSummary
from app.services import high_risk, period_setup, semester_context
from app.services import period_tables as pt_service
from app.services.calendar import readiness_issues
from app.services.school_rules import validate_academic_year
from app.services.semester_copy import CopyOptions, copy_semester

router = APIRouter(tags=["semesters"])

viewer = core_viewer
editor = core_editor


# ── 内部工具 ──────────────────────────
def _get_semester(db: Session, semester_id: int) -> Semester:
    semester = db.get(Semester, semester_id)
    if semester is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到学期")
    return semester


def _require_writable(db: Session, semester_id: int, *, lock: str = "share") -> Semester:
    try:
        return semester_context.require_writable(db, semester_id, lock=lock)  # type: ignore[arg-type]
    except semester_context.SemesterContextError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": exc.message}) from exc


def _semester_list_item(
    db: Session, semester: Semester, current_id: int | None = None
) -> SemesterListItem:
    if current_id is None:
        current_id = semester_context.read_context(db)[0].current_semester_id
    return SemesterListItem.model_validate(semester).model_copy(
        update={"is_current": semester.id == current_id}
    )


def _semester_out(db: Session, semester: Semester, current_id: int | None = None) -> SemesterOut:
    item = _semester_list_item(db, semester, current_id)
    return SemesterOut.model_validate(semester).model_copy(
        update={"is_current": item.is_current}
    )


def _context_out(db: Session, user: User) -> SemesterContextOut:
    row, current = semester_context.read_context(db)
    return SemesterContextOut(
        current_semester=(
            _semester_list_item(db, current, row.current_semester_id) if current else None
        ),
        revision=row.revision,
        can_switch=bool(user.role_names & {Role.admin.value, Role.scheduler.value}),
    )


def _context_http_error(exc: semester_context.SemesterContextError) -> HTTPException:
    return HTTPException(exc.status_code, {"code": exc.code, "message": exc.message})


def _get_period_table(db: Session, table_id: int) -> PeriodTable:
    table = db.get(PeriodTable, table_id)
    if table is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到作息时间表")
    return table


def _unset_other_defaults(db: Session, semester_id: int, keep_id: int | None) -> None:
    others = db.scalars(
        select(PeriodTable).where(
            PeriodTable.semester_id == semester_id, PeriodTable.is_default.is_(True)
        )
    )
    for t in others:
        if t.id != keep_id:
            t.is_default = False


# ── 学期 ──────────────────────────────
@router.get("/semester-context", response_model=SemesterContextOut)
def get_semester_context(user: User = Depends(get_active_user), db: Session = Depends(get_db)):
    """读取所有登录角色共享的当前学期工作边界。"""
    return _context_out(db, user)


@router.put("/semester-context", response_model=SemesterContextOut)
def put_semester_context(
    body: SemesterContextSwitch,
    db: Session = Depends(get_db),
    user: User = Depends(editor),
):
    """以版本号切换当前学期，防止并发页面静默覆盖选择。"""
    try:
        semester_context.switch_current(db, body.semester_id, body.expected_revision)
    except semester_context.SemesterContextError as exc:
        raise _context_http_error(exc) from exc
    db.commit()
    return _context_out(db, user)


@router.get("/semesters", response_model=list[SemesterListItem])
def list_semesters(db: Session = Depends(get_db), _: object = Depends(viewer)):
    current_id = semester_context.read_context(db)[0].current_semester_id
    return [
        _semester_list_item(db, semester, current_id)
        for semester in db.scalars(
        select(Semester).order_by(Semester.academic_year.desc(), Semester.term.desc())
        ).all()
    ]


@router.post("/semesters", response_model=SemesterOut, status_code=status.HTTP_201_CREATED)
def create_semester(
    body: SemesterCreate, db: Session = Depends(get_db), _: object = Depends(editor)
) -> SemesterOut:
    try:
        validate_academic_year(body.academic_year)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    exists = db.scalar(
        select(Semester).where(
            Semester.academic_year == body.academic_year,
            Semester.term == body.term,
        )
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "该学年学期已存在")

    semester = Semester(
        academic_year=body.academic_year,
        term=body.term,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    db.add(semester)
    db.flush()
    semester_context.set_initial_current(db, semester)
    db.commit()
    db.refresh(semester)
    return _semester_out(db, semester)


@router.post(
    "/semesters/{source_id}/copy", response_model=SemesterOut, status_code=status.HTTP_201_CREATED
)
def copy_to_new_semester(
    source_id: int,
    body: SemesterCopyRequest,
    db: Session = Depends(get_db),
    _: object = Depends(editor),
) -> SemesterOut:
    try:
        validate_academic_year(body.academic_year)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    source = _get_semester(db, source_id)
    exists = db.scalar(
        select(Semester).where(
            Semester.academic_year == body.academic_year,
            Semester.term == body.term,
        )
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "目标学年学期已存在")
    opts = CopyOptions(
        period_tables=body.period_tables,
        subjects=body.subjects,
        teachers=body.teachers,
        rooms=body.rooms,
        classes=body.classes,
        grade_promotion=body.grade_promotion,
        constraint_config=body.constraint_config,
    )
    new = copy_semester(
        db, source, body.academic_year, body.term, opts,
        start_date=body.start_date, end_date=body.end_date,
    )
    semester_context.set_initial_current(db, new)
    db.commit()
    db.refresh(new)
    return _semester_out(db, new)


@router.get("/semesters/{semester_id}", response_model=SemesterOut)
def get_semester(
    semester_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
) -> SemesterOut:
    return _semester_out(db, _get_semester(db, semester_id))


@router.get("/semesters/{semester_id}/summary", response_model=SemesterSummary)
def semester_summary(
    semester_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
) -> SemesterSummary:
    _get_semester(db, semester_id)

    def _count(model) -> int:
        return db.scalar(
            select(func.count()).select_from(model).where(model.semester_id == semester_id)
        ) or 0

    return SemesterSummary(
        subjects=_count(Subject), teachers=_count(Teacher),
        classes=_count(ClassUnit), rooms=_count(Room),
    )


@router.get("/semesters/{semester_id}/period-setup")
def get_period_setup(
    semester_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(viewer),
) -> dict:
    """读取现有作息分组；尚未配置时仅返回按班级学制生成的建议。"""
    _get_semester(db, semester_id)
    return period_setup.build_draft(db, semester_id)


@router.put("/semesters/{semester_id}/period-setup")
def put_period_setup(
    semester_id: int,
    body: PeriodSetupApply,
    db: Session = Depends(get_db),
    _: object = Depends(editor),
) -> dict:
    """以单一事务应用全部作息表、节次与班级分配。"""
    _require_writable(db, semester_id)
    try:
        return period_setup.apply_setup(db, semester_id, body)
    except period_setup.PeriodSetupStaleError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "period_setup_stale", "message": str(exc)},
        ) from exc
    except period_setup.PeriodSetupValidationError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "period_setup_invalid", "message": str(exc)},
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "period_setup_write_conflict",
                "message": "应用作息时发生写入冲突，所有分组均未保存",
            },
        ) from exc


@router.patch("/semesters/{semester_id}", response_model=SemesterOut)
def update_semester(
    semester_id: int,
    body: SemesterUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(editor),
) -> SemesterOut:
    semester = _require_writable(db, semester_id, lock="update")
    data = body.model_dump(exclude_unset=True)
    dates_changed = "start_date" in data or "end_date" in data
    if "status" in data and data["status"] is not None:
        semester.status = data["status"].value
    if "start_date" in data:
        semester.start_date = data["start_date"]
    if "end_date" in data:
        semester.end_date = data["end_date"]
    if "readiness" in data and data["readiness"] is not None:
        if data["readiness"].value == "ready":
            issues = readiness_issues(db, semester)
            if issues:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail={
                        "code": "semester_not_ready",
                        "message": "学期数据尚未准备完成",
                        "issues": issues,
                    },
                )
        semester.readiness = data["readiness"].value
    elif dates_changed and semester.readiness == "ready":
        semester.readiness = "draft"
    if semester.status == "archived":
        semester_context.clear_current_if_matches(db, semester.id)
    db.commit()
    db.refresh(semester)
    return _semester_out(db, semester)


@router.delete("/semesters/{semester_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_semester(
    semester_id: int,
    confirmation: HighRiskConfirmation | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
) -> None:
    attempt = high_risk_http.begin(
        db,
        user,
        confirmation,
        action="delete_semester",
        target_type="semester",
        target_id=semester_id,
        semester_id=None,
        target_version=f"学期 #{semester_id}",
        expected_target=f"semester:{semester_id}",
        impact=f"永久删除学期 #{semester_id} 及其全部排课、基础数据和运行记录",
    )
    try:
        semester = _get_semester(db, semester_id)
    except HTTPException as exc:
        high_risk_http.reject(db, attempt.id, exc)
    high_risk.update_target(
        db,
        attempt.id,
        target_version=semester.label,
        semester_id=semester.id,
    )
    try:
        semester = _require_writable(db, semester_id, lock="update")
        semester_context.clear_current_if_matches(db, semester.id)
    except HTTPException as exc:
        high_risk_http.reject(db, attempt.id, exc)
    db.delete(semester)
    high_risk_http.complete_delete(
        db, attempt.id, detail=f"已永久删除学期「{semester.label}」"
    )


# ── 作息时间表 ────────────────────────────
@router.post(
    "/semesters/{semester_id}/period-tables",
    response_model=PeriodTableOut,
    status_code=status.HTTP_201_CREATED,
)
def create_period_table(
    semester_id: int,
    body: PeriodTableCreate,
    db: Session = Depends(get_db),
    _: object = Depends(editor),
) -> PeriodTable:
    _require_writable(db, semester_id)

    table = PeriodTable(
        name=body.name, num_weekdays=body.num_weekdays, is_default=body.is_default
    )
    table.semester_id = semester_id
    db.add(table)
    db.flush()
    if table.is_default:
        _unset_other_defaults(db, semester_id, table.id)
    semester = db.get(Semester, semester_id)
    if semester is not None:
        semester.readiness = "draft"
    db.commit()
    db.refresh(table)
    return table


@router.get("/period-tables/{table_id}", response_model=PeriodTableOut)
def get_period_table(
    table_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
) -> PeriodTable:
    return _get_period_table(db, table_id)


@router.patch("/period-tables/{table_id}", response_model=PeriodTableOut)
def update_period_table(
    table_id: int,
    body: PeriodTableUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(editor),
) -> PeriodTable:
    table = _get_period_table(db, table_id)
    semester = _require_writable(db, table.semester_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("name") is not None:
        table.name = data["name"]
    if data.get("is_default") is not None:
        table.is_default = data["is_default"]
        if data["is_default"]:
            _unset_other_defaults(db, table.semester_id, table.id)
    if semester is not None and semester.readiness == "ready":
        semester.readiness = "draft"
    db.commit()
    db.refresh(table)
    return table


@router.delete("/period-tables/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_period_table(
    table_id: int,
    confirmation: HighRiskConfirmation | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
) -> None:
    attempt = high_risk_http.begin(
        db,
        user,
        confirmation,
        action="delete_period_table",
        target_type="period_table",
        target_id=table_id,
        semester_id=None,
        target_version=f"作息时间表 #{table_id}",
        expected_target=f"period-table:{table_id}",
        impact=f"永久删除作息时间表 #{table_id} 及其中全部节次",
    )
    try:
        table = _get_period_table(db, table_id)
    except HTTPException as exc:
        high_risk_http.reject(db, attempt.id, exc)
    high_risk.update_target(
        db,
        attempt.id,
        target_version=table.name,
        semester_id=table.semester_id,
    )
    try:
        semester = _require_writable(db, table.semester_id)
        ref_count = db.scalar(
            select(func.count())
            .select_from(ClassUnit)
            .where(ClassUnit.period_table_id == table_id)
        )
        if ref_count:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"此作息时间表已被 {ref_count} 个班级指定使用,请先改用其他作息时间表再删除",
            )
    except HTTPException as exc:
        high_risk_http.reject(db, attempt.id, exc)
    db.delete(table)
    if semester is not None:
        semester.readiness = "draft"
    high_risk_http.complete_delete(
        db, attempt.id, detail=f"已永久删除作息时间表「{table.name}」"
    )


@router.put("/period-tables/{table_id}/periods", response_model=PeriodTableOut)
def replace_periods(
    table_id: int,
    periods: list[PeriodIn],
    db: Session = Depends(get_db),
    _: object = Depends(editor),
) -> PeriodTable:
    """整批取代作息时间表的所有单元格(视觉化编辑器存储用)。"""
    table = _get_period_table(db, table_id)
    semester = _require_writable(db, table.semester_id)

    seen: set[tuple[int, int]] = set()
    for p in periods:
        key = (p.weekday, p.period_no)
        if key in seen:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"重复的单元格:星期 {p.weekday} 第 {p.period_no} 节",
            )
        seen.add(key)

    table.periods.clear()
    db.flush()
    for p in periods:
        table.periods.append(
            Period(
                weekday=p.weekday,
                period_no=p.period_no,
                name=p.name,
                start_time=p.start_time,
                end_time=p.end_time,
                type=p.type.value,
            )
        )
    if semester is not None and semester.readiness == "ready":
        semester.readiness = "draft"
    db.commit()
    db.refresh(table)
    return table


def _slots_out(rows: list[Period]) -> list[AvailableSlot]:
    return [
        AvailableSlot(
            weekday=p.weekday,
            period_no=p.period_no,
            name=p.name,
            start_time=p.start_time,
            end_time=p.end_time,
        )
        for p in rows
    ]


@router.get("/period-tables/{table_id}/available-slots", response_model=list[AvailableSlot])
def available_slots(
    table_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
) -> list[AvailableSlot]:
    """返回可排课时段(type=regular),供排课时段检查使用。"""
    _get_period_table(db, table_id)
    return _slots_out(pt_service.regular_slots(db, table_id))
