"""公开的部署配置档信息，不包含密钥、数据库连接或其他机密。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.app_config import AppConfigOut
from app.services.deployment_profile import ProfileMismatchError, app_config

router = APIRouter(tags=["app-config"])


@router.get("/app-config", response_model=AppConfigOut)
def get_app_config(db: Session = Depends(get_db)) -> AppConfigOut:
    try:
        result = app_config(db)
        db.commit()
        return AppConfigOut.model_validate(result)
    except ProfileMismatchError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "school_profile_locked",
                "message": str(exc),
                "locked_profile": exc.locked,
                "requested_profile": exc.requested,
            },
        ) from exc
