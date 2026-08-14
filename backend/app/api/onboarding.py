"""首次成功与 P0 待办读接口。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.db import get_db
from app.models.user import Role
from app.schemas.onboarding import OnboardingStatusOut
from app.services.onboarding import build_status

router = APIRouter(tags=["onboarding"])

viewer = require_roles(Role.scheduler, Role.director)


@router.get("/onboarding/status", response_model=OnboardingStatusOut)
@router.get("/onboarding", response_model=OnboardingStatusOut, include_in_schema=False)
def onboarding_status(
    db: Session = Depends(get_db), _: object = Depends(viewer)
) -> OnboardingStatusOut:
    return build_status(db)
