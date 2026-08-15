"""设置向导 API:进度状态读写、重新启动。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.permissions import core_editor, core_viewer
from app.models.semester import Semester
from app.models.wizard import SINGLETON_ID, TOTAL_STEPS, WizardState
from app.schemas.wizard import WizardStateOut, WizardStateUpdate
from app.services import onboarding_route, semester_context

router = APIRouter(tags=["wizard"])

viewer = core_viewer
editor = core_editor


def _get_or_create(db: Session) -> WizardState:
    state = db.get(WizardState, SINGLETON_ID)
    if state is None:
        state = onboarding_route.get_or_create_state(db)
        db.commit()
        db.refresh(state)
    return state


def _to_out(db: Session, state: WizardState) -> WizardStateOut:
    has_semesters = bool(db.scalar(select(func.count()).select_from(Semester)))
    route = onboarding_route.effective_route(db, state)
    state_matches_route = state.route is None or state.route == route
    return WizardStateOut(
        current_step=state.current_step if state_matches_route else 0,
        completed=state.completed if state_matches_route else False,
        semester_id=state.semester_id if state_matches_route else None,
        total_steps=TOTAL_STEPS,
        has_semesters=has_semesters,
        route=route,
    )


@router.get("/wizard/state", response_model=WizardStateOut)
def get_state(db: Session = Depends(get_db), _: object = Depends(viewer)) -> WizardStateOut:
    return _to_out(db, _get_or_create(db))


@router.patch("/wizard/state", response_model=WizardStateOut)
def update_state(
    body: WizardStateUpdate, db: Session = Depends(get_db), _: object = Depends(editor)
) -> WizardStateOut:
    state = _get_or_create(db)
    data = body.model_dump(exclude_unset=True)
    requested_route = data.get("route") or onboarding_route.effective_route(db, state)
    requested_semester_id = data.get("semester_id")
    if requested_semester_id is not None:
        requested_semester = db.get(Semester, requested_semester_id)
        if requested_semester is not None and requested_route is not None:
            route_is_demo = requested_route == "demo"
            if requested_semester.is_demo != route_is_demo:
                raise HTTPException(
                    409,
                    {
                        "code": "wizard_route_semester_mismatch",
                        "message": "向导路线与学期类型不一致，不能把示例学期写入正式路线",
                    },
                )
    if "route" in data and data["route"] is not None:
        try:
            onboarding_route.choose_route(db, data.pop("route"))
        except onboarding_route.OnboardingRouteError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc
    if "current_step" in data and data["current_step"] is not None:
        state.current_step = max(0, min(data["current_step"], TOTAL_STEPS - 1))
    if "completed" in data and data["completed"] is not None:
        state.completed = data["completed"]
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


@router.post("/wizard/reset", response_model=WizardStateOut)
def reset_state(db: Session = Depends(get_db), _: object = Depends(editor)) -> WizardStateOut:
    state = _get_or_create(db)
    state.current_step = 0
    state.completed = False
    state.semester_id = None
    state.route = None
    db.commit()
    db.refresh(state)
    return _to_out(db, state)
