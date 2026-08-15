"""当前账号的导航偏好。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_active_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.navigation import NavigationPreference

router = APIRouter(tags=["navigation"])


@router.get("/navigation-preference", response_model=NavigationPreference | None)
def get_navigation_preference(
    user: User = Depends(get_active_user),
) -> NavigationPreference | None:
    if user.navigation_preference is None:
        return None
    return NavigationPreference.model_validate(user.navigation_preference)


@router.put("/navigation-preference", response_model=NavigationPreference)
def update_navigation_preference(
    body: NavigationPreference,
    user: User = Depends(get_active_user),
    db: Session = Depends(get_db),
) -> NavigationPreference:
    user.navigation_preference = body.model_dump()
    db.commit()
    return body
