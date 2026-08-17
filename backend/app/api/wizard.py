"""设置向导 API:进度状态、真实数据检查与安全补全。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.permissions import core_editor, core_viewer
from app.models.semester import Semester
from app.models.wizard import SINGLETON_ID, TOTAL_STEPS, WizardState
from app.schemas.wizard import (
    SetupCheckOut,
    WizardCompleteIn,
    WizardStateOut,
    WizardStateUpdate,
)
from app.services import semester_context, setup_check

router = APIRouter(tags=["wizard"])

viewer = core_viewer
editor = core_editor


def _get_or_create(db: Session) -> WizardState:
    state = db.get(WizardState, SINGLETON_ID)
    if state is None:
        state = WizardState(id=SINGLETON_ID)
        db.add(state)
        db.flush()
    return state


def _to_out(db: Session, state: WizardState) -> WizardStateOut:
    has_semesters = bool(db.scalar(select(func.count()).select_from(Semester)))
    semester = db.get(Semester, state.semester_id) if state.semester_id else None
    resume_step = setup_check.build_check(db, semester).first_incomplete_step if semester else 0
    return WizardStateOut(
        current_step=state.current_step,
        resume_step=resume_step,
        completed=state.completed,
        paused=state.paused,
        semester_id=state.semester_id,
        total_steps=TOTAL_STEPS,
        has_semesters=has_semesters,
    )


@router.get("/wizard/state", response_model=WizardStateOut)
def get_state(db: Session = Depends(get_db), _: object = Depends(viewer)) -> WizardStateOut:
    state = _get_or_create(db)
    db.commit()
    db.refresh(state)
    return _to_out(db, state)


@router.patch("/wizard/state", response_model=WizardStateOut)
def update_state(
    body: WizardStateUpdate, db: Session = Depends(get_db), _: object = Depends(editor)
) -> WizardStateOut:
    state = _get_or_create(db)
    data = body.model_dump(exclude_unset=True)
    if "current_step" in data and data["current_step"] is not None:
        state.current_step = max(0, min(data["current_step"], TOTAL_STEPS - 1))
    if "completed" in data and data["completed"] is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "wizard_completion_requires_check",
                "message": "请通过完成检查提交基础设置",
            },
        )
    if "paused" in data and data["paused"] is not None:
        state.paused = data["paused"]
    if "semester_id" in data:
        if data["semester_id"] is not None:
            try:
                semester_context.require_writable(db, data["semester_id"])
            except semester_context.SemesterContextError as exc:
                raise HTTPException(
                    exc.status_code, {"code": exc.code, "message": exc.message}
                ) from exc
        state.semester_id = data["semester_id"]
    db.commit()
    db.refresh(state)
    return _to_out(db, state)


@router.get("/semesters/{semester_id}/setup-check", response_model=SetupCheckOut)
def get_setup_check(
    semester_id: int, db: Session = Depends(get_db), _: object = Depends(viewer)
) -> SetupCheckOut:
    semester = db.get(Semester, semester_id)
    if semester is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到学期")
    return setup_check.build_check(db, semester)


@router.post("/wizard/complete", response_model=WizardStateOut)
def complete_setup(
    body: WizardCompleteIn,
    db: Session = Depends(get_db),
    _: object = Depends(editor),
) -> WizardStateOut:
    try:
        semester = semester_context.require_writable(db, body.semester_id, lock="update")
    except semester_context.SemesterContextError as exc:
        raise HTTPException(
            exc.status_code, {"code": exc.code, "message": exc.message}
        ) from exc
    check = setup_check.build_check(db, semester)
    if check.blockers:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "wizard_setup_blocked",
                "message": "请先处理完成检查中的阻断项",
                "check": check.model_dump(mode="json"),
            },
        )
    if check.warnings and not body.acknowledge_warnings:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "wizard_warnings_unacknowledged",
                "message": "请确认已了解尚未完成的建议项",
                "check": check.model_dump(mode="json"),
            },
        )

    state = _get_or_create(db)
    state.current_step = TOTAL_STEPS - 1
    state.completed = True
    state.paused = False
    state.semester_id = semester.id
    db.commit()
    db.refresh(state)
    return _to_out(db, state)


@router.post("/wizard/reopen", response_model=WizardStateOut)
def reopen_current_semester(
    db: Session = Depends(get_db), _: object = Depends(editor)
) -> WizardStateOut:
    context, current = semester_context.read_context(db)
    if current is None or context.current_semester_id is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "current_semester_missing",
                "message": "请先选择当前学期",
            },
        )
    try:
        semester = semester_context.require_writable(db, current.id, lock="update")
    except semester_context.SemesterContextError as exc:
        raise HTTPException(
            exc.status_code, {"code": exc.code, "message": exc.message}
        ) from exc
    check = setup_check.build_check(db, semester)
    state = _get_or_create(db)
    state.current_step = check.first_incomplete_step
    state.completed = False
    state.paused = False
    state.semester_id = semester.id
    db.commit()
    db.refresh(state)
    return _to_out(db, state)
