"""今日调课与代课看板与调课与代课日志(M4-4)。

看板/日志是行政的当日排课与历史查询工具,限排课管理员/教务主任。
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.db import get_db
from app.models.semester import Semester
from app.models.user import Role, User
from app.schemas.substitution_log import DailyBoardOut, LogEntryOut
from app.services import calendar as calendar_service
from app.services import settings as app_settings
from app.services import substitution_log as log_service

router = APIRouter(tags=["substitution-log"])

viewer = require_roles(Role.scheduler, Role.director)


def _entry_out(e: log_service.LogEntry) -> LogEntryOut:
    return LogEntryOut(**{f: getattr(e, f) for f in LogEntryOut.model_fields})


def _get_semester(db: Session, semester_id: int) -> Semester:
    sem = db.get(Semester, semester_id)
    if sem is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到学期")
    return sem


@router.get("/daily-board", response_model=DailyBoardOut)
def daily_board(
    semester_id: int = Query(...),
    on: date | None = Query(default=None, description="看板日期,默认为学校时区的今天"),
    db: Session = Depends(get_db),
    _: User = Depends(viewer),
):
    """某一天全校的调课与代课变更(默认今天);无变更则 entries 为空。"""
    sem = _get_semester(db, semester_id)
    day = on or log_service.school_today()
    entries = log_service.daily_board(db, semester_id, day)
    return DailyBoardOut(
        date=day,
        weekday=calendar_service.effective_weekday(db, semester_id, day) or day.isoweekday(),
        school_name=app_settings.school_name(db),
        semester_label=sem.label,
        entries=[_entry_out(e) for e in entries],
    )


@router.get("/substitution-log", response_model=list[LogEntryOut])
def substitution_log(
    semester_id: int = Query(...),
    teacher_id: int | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    leave_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(viewer),
):
    """调课与代课历史查询:依教师(缺课或代课)、日期区间、请假类型筛选。"""
    _get_semester(db, semester_id)
    entries = log_service.query(
        db, semester_id,
        date_from=date_from, date_to=date_to,
        teacher_id=teacher_id, leave_type=leave_type,
    )
    return [_entry_out(e) for e in entries]
