"""部署配置檔的首次寫入與鎖定。

部署檔不是可在 UI 中切換的偏好。寫入資料庫後，環境變數若改成另一個地區，
系統會明確拒絕，避免把既有學期的日期、術語和學年標籤悄悄混用。
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.app_setting import AppSetting
from app.models.semester import Semester
from app.services.localization import public_profile

PROFILE_SETTING_KEY = "school_profile"


class ProfileMismatchError(RuntimeError):
    def __init__(self, locked: str, requested: str) -> None:
        self.locked = locked
        self.requested = requested
        super().__init__(
            f"部署配置档已锁定为 {locked}，不能切换为 {requested}；请建立新的部署或先迁移数据"
        )


class SemesterNotReadyError(RuntimeError):
    def __init__(self, semester_id: int, issues: list[dict[str, str]] | None = None) -> None:
        self.semester_id = semester_id
        self.issues = issues or []
        super().__init__("大陆草稿学期尚未确认就绪，暂不能自动排课或发布课表")


def locked_profile(db: Session) -> str | None:
    row = db.get(AppSetting, PROFILE_SETTING_KEY)
    return row.value if row and row.value else None


def ensure_locked_profile(db: Session) -> str:
    """首次部署写入配置档；旧库有学期时默认视为台湾档。

    旧版本没有该 key。为保持兼容，空库采用当前环境变量，已有学期则锁定为
    台湾档；后者在请求大陆环境时抛出冲突而不是自动转换数据。
    """
    row = db.get(AppSetting, PROFILE_SETTING_KEY)
    if row is None or not row.value:
        semester_count = int(db.scalar(select(func.count()).select_from(Semester)) or 0)
        value = "tw_k12" if semester_count else settings.school_profile
        if row is None:
            row = AppSetting(key=PROFILE_SETTING_KEY, value=value)
            db.add(row)
        else:
            row.value = value
        db.flush()
    locked = row.value
    if locked != settings.school_profile:
        raise ProfileMismatchError(locked, settings.school_profile)
    return locked


def app_config(db: Session) -> dict:
    profile = ensure_locked_profile(db)
    return {"school_name": settings.school_name, **public_profile(profile)}


def assert_profile(db: Session) -> str:
    """供需要地区语义的写入/求解端点调用。"""
    return ensure_locked_profile(db)


def assert_semester_ready(db: Session, semester: Semester) -> str:
    profile = ensure_locked_profile(db)
    if profile == "cn_mainland":
        # Readiness is a gate, not a permanent approval. Editing dates or the
        # period table after confirmation must invalidate the gate as well.
        from app.services.calendar import readiness_issues

        issues = readiness_issues(db, semester)
        if semester.readiness != "ready" or issues:
            raise SemesterNotReadyError(semester.id, issues)
    return profile
