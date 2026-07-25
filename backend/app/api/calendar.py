"""學期校曆例外與就緒确认 API。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.db import get_db
from app.models.audit import AuditLog
from app.models.calendar import SemesterCalendarException
from app.models.semester import Semester, SemesterReadiness
from app.models.user import Role, User
from app.schemas.calendar import (
    CalendarExceptionCreate,
    CalendarExceptionOut,
    CalendarExceptionUpdate,
    SemesterReadinessOut,
)
from app.services import calendar as calendar_service
from app.services import deployment_profile

router = APIRouter(tags=["calendar"])

viewer = require_roles(Role.scheduler, Role.director)
editor = require_roles(Role.scheduler, Role.director)


def _semester(db: Session, semester_id: int) -> Semester:
    try:
        deployment_profile.assert_profile(db)
    except deployment_profile.ProfileMismatchError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "school_profile_locked",
                "message": str(exc),
                "locked_profile": exc.locked,
                "requested_profile": exc.requested,
            },
        ) from exc
    semester = db.get(Semester, semester_id)
    if semester is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到学期")
    return semester


def _out(row: SemesterCalendarException) -> CalendarExceptionOut:
    return CalendarExceptionOut.model_validate(row)


def _readiness(db: Session, semester: Semester) -> SemesterReadinessOut:
    issues = calendar_service.readiness_issues(db, semester)
    count = int(
        db.scalar(
            select(func.count()).select_from(SemesterCalendarException).where(
                SemesterCalendarException.semester_id == semester.id
            )
        )
        or 0
    )
    return SemesterReadinessOut(
        semester_id=semester.id,
        readiness=semester.readiness,
        ready=semester.readiness == SemesterReadiness.ready.value and not issues,
        issues=issues,
        calendar_exception_count=count,
    )


@router.get(
    "/semesters/{semester_id}/calendar-exceptions",
    response_model=list[CalendarExceptionOut],
)
def list_exceptions(
    semester_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
) -> list[CalendarExceptionOut]:
    _semester(db, semester_id)
    rows = db.scalars(
        select(SemesterCalendarException)
        .where(SemesterCalendarException.semester_id == semester_id)
        .order_by(SemesterCalendarException.date)
    )
    return [_out(row) for row in rows]


@router.post(
    "/semesters/{semester_id}/calendar-exceptions",
    response_model=CalendarExceptionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_exception(
    semester_id: int,
    body: CalendarExceptionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(editor),
) -> CalendarExceptionOut:
    semester = _semester(db, semester_id)
    try:
        calendar_service.validate_exception_date(semester, body.date)
        calendar_service.validate_exception_fields(body.kind.value, body.makeup_weekday)
        row = SemesterCalendarException(
            semester_id=semester_id,
            date=body.date,
            kind=body.kind.value,
            makeup_weekday=body.makeup_weekday,
            note=body.note.strip(),
            created_by_user_id=user.id,
            created_by_name=user.username,
        )
        db.add(row)
        db.flush()
        semester.readiness = SemesterReadiness.draft.value
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "该日期已经存在校历例外") from exc
    db.add(AuditLog(
        user_id=user.id, username=user.username, action="create_calendar_exception",
        target_type="semester_calendar_exception", target_id=row.id,
        detail=f"{semester.label} {row.date} {row.kind}"[:500],
    ))
    db.commit()
    db.refresh(row)
    return _out(row)


@router.patch("/calendar-exceptions/{exception_id}", response_model=CalendarExceptionOut)
def update_exception(
    exception_id: int,
    body: CalendarExceptionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(editor),
) -> CalendarExceptionOut:
    row = db.get(SemesterCalendarException, exception_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到校历例外")
    semester = _semester(db, row.semester_id)
    data = body.model_dump(exclude_unset=True)
    kind = data.get("kind", row.kind)
    if hasattr(kind, "value"):
        kind = kind.value
    makeup = data["makeup_weekday"] if "makeup_weekday" in data else row.makeup_weekday
    # Changing a makeup day back to a closure must not leave an invalid weekday
    # value behind when the client omits the now-hidden field.
    if kind == "no_instruction" and "makeup_weekday" not in data:
        makeup = None
    day = data.get("date", row.date)
    try:
        calendar_service.validate_exception_date(semester, day)
        calendar_service.validate_exception_fields(kind, makeup)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    row.date, row.kind, row.makeup_weekday = day, kind, makeup
    semester.readiness = SemesterReadiness.draft.value
    if "note" in data and data["note"] is not None:
        row.note = data["note"].strip()
    db.add(AuditLog(
        user_id=user.id, username=user.username, action="update_calendar_exception",
        target_type="semester_calendar_exception", target_id=row.id,
        detail=f"{semester.label} {row.date} {row.kind}"[:500],
    ))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "该日期已经存在校历例外") from exc
    db.refresh(row)
    return _out(row)


@router.delete("/calendar-exceptions/{exception_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exception(
    exception_id: int, db: Session = Depends(get_db), user: User = Depends(editor)
) -> None:
    row = db.get(SemesterCalendarException, exception_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到校历例外")
    semester = _semester(db, row.semester_id)
    db.add(AuditLog(
        user_id=user.id, username=user.username, action="delete_calendar_exception",
        target_type="semester_calendar_exception", target_id=row.id,
        detail=f"删除校历例外 {row.date}"[:500],
    ))
    db.delete(row)
    semester.readiness = SemesterReadiness.draft.value
    db.commit()


@router.get("/semesters/{semester_id}/readiness", response_model=SemesterReadinessOut)
def get_readiness(
    semester_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
) -> SemesterReadinessOut:
    return _readiness(db, _semester(db, semester_id))


@router.post("/semesters/{semester_id}/readiness", response_model=SemesterReadinessOut)
def confirm_readiness(
    semester_id: int, db: Session = Depends(get_db), user: User = Depends(editor)
) -> SemesterReadinessOut:
    semester = _semester(db, semester_id)
    issues = calendar_service.readiness_issues(db, semester)
    if issues:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "semester_not_ready",
                "message": "学期资料尚未准备完成",
                "issues": issues,
            },
        )
    semester.readiness = SemesterReadiness.ready.value
    db.add(AuditLog(
        user_id=user.id, username=user.username, action="confirm_semester_readiness",
        target_type="semester", target_id=semester.id,
        detail=f"确认 {semester.label} 资料就绪"[:500],
    ))
    db.commit()
    db.refresh(semester)
    return _readiness(db, semester)


@router.post("/semesters/{semester_id}/ready", response_model=SemesterReadinessOut)
def confirm_ready_alias(
    semester_id: int, db: Session = Depends(get_db), user: User = Depends(editor)
) -> SemesterReadinessOut:
    return confirm_readiness(semester_id, db, user)


@router.delete("/semesters/{semester_id}/readiness", response_model=SemesterReadinessOut)
def revoke_readiness(
    semester_id: int, db: Session = Depends(get_db), user: User = Depends(editor)
) -> SemesterReadinessOut:
    semester = _semester(db, semester_id)
    semester.readiness = SemesterReadiness.draft.value
    db.add(AuditLog(
        user_id=user.id, username=user.username, action="revoke_semester_readiness",
        target_type="semester", target_id=semester.id,
        detail=f"撤回 {semester.label} 资料就绪确认"[:500],
    ))
    db.commit()
    db.refresh(semester)
    return _readiness(db, semester)
