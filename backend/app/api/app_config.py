"""公开的应用配置，不包含密钥、数据库连接或其他机密。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.app_config import AppConfigOut
from app.services import settings as app_settings
from app.services.school_rules import ROLE_DISPLAY_NAMES, TIMEZONE, academic_year_config

router = APIRouter(tags=["app-config"])


@router.get("/app-config", response_model=AppConfigOut)
def get_app_config(db: Session = Depends(get_db)) -> AppConfigOut:
    return AppConfigOut(
        school_name=app_settings.school_name(db),
        timezone=TIMEZONE,
        role_display_names=ROLE_DISPLAY_NAMES,
        academic_year=academic_year_config(),
    )
