"""首次成功与 P0 待办读接口。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.db import get_db
from app.core.permissions import core_editor, core_viewer
from app.models.user import Role
from app.schemas.onboarding import OnboardingStatusOut
from app.schemas.wizard import OnboardingRouteOut, OnboardingRouteRequest
from app.services import onboarding_route
from app.services.onboarding import build_status

router = APIRouter(tags=["onboarding"])

viewer = require_roles(Role.scheduler, Role.director)
route_viewer = core_viewer
route_editor = core_editor


@router.get("/onboarding/status", response_model=OnboardingStatusOut)
def onboarding_status(
    db: Session = Depends(get_db), _: object = Depends(viewer)
) -> OnboardingStatusOut:
    return build_status(db)


def _route_out(db: Session) -> OnboardingRouteOut:
    return OnboardingRouteOut(**onboarding_route.route_snapshot(db))


@router.get("/onboarding/route", response_model=OnboardingRouteOut)
def onboarding_route_status(
    db: Session = Depends(get_db), _: object = Depends(route_viewer)
) -> OnboardingRouteOut:
    """读取首次入口路线和可恢复的正式向导进度。"""
    return _route_out(db)


def _choose_route(
    body: OnboardingRouteRequest, db: Session
) -> OnboardingRouteOut:
    try:
        onboarding_route.choose_route(db, body.route)
    except onboarding_route.OnboardingRouteError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    db.commit()
    return _route_out(db)


@router.put("/onboarding/route", response_model=OnboardingRouteOut)
def choose_onboarding_route(
    body: OnboardingRouteRequest,
    db: Session = Depends(get_db),
    _: object = Depends(route_editor),
) -> OnboardingRouteOut:
    return _choose_route(body, db)


@router.post("/onboarding/route", response_model=OnboardingRouteOut)
def choose_onboarding_route_alias(
    body: OnboardingRouteRequest,
    db: Session = Depends(get_db),
    _: object = Depends(route_editor),
) -> OnboardingRouteOut:
    """POST 兼容首次入口客户端，语义与 PUT 相同。"""
    return _choose_route(body, db)
