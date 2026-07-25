"""校历特殊日期解析与排课准备检查。"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.calendar import CalendarExceptionKind, SemesterCalendarException
from app.models.period import Period, PeriodTable, PeriodType
from app.models.semester import Semester


def exception_for(db: Session, semester_id: int, day: date) -> SemesterCalendarException | None:
    return db.scalar(
        select(SemesterCalendarException).where(
            SemesterCalendarException.semester_id == semester_id,
            SemesterCalendarException.date == day,
        )
    )


def effective_weekday(db: Session, semester_id: int, day: date) -> int | None:
    """把实际日期解析成该日使用的周课表星期。

    普通日返回自然星期；停课日返回 None；周末补课返回设置的星期一至六。
    """
    exception = exception_for(db, semester_id, day)
    if exception is None:
        return day.isoweekday()
    if exception.kind == CalendarExceptionKind.no_instruction.value:
        return None
    return exception.makeup_weekday


def is_instruction_day(
    db: Session, semester_id: int, day: date, period_table_id: int | None = None
) -> bool:
    weekday = effective_weekday(db, semester_id, day)
    if weekday is None:
        return False
    if period_table_id is None:
        return True
    return bool(
        db.scalar(
            select(func.count())
            .select_from(Period)
            .where(
                Period.period_table_id == period_table_id,
                Period.weekday == weekday,
                Period.type == PeriodType.regular.value,
            )
        )
    )


def readiness_issues(db: Session, semester: Semester) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if semester.start_date is None or semester.end_date is None:
        issues.append({"code": "semester_dates_missing", "message": "请先设置学期起止日期"})
    elif semester.end_date < semester.start_date:
        issues.append({"code": "semester_dates_invalid", "message": "学期结束日期不能早于开始日期"})

    tables = list(
        db.scalars(select(PeriodTable).where(PeriodTable.semester_id == semester.id))
    )
    if not tables:
        issues.append({"code": "period_table_missing", "message": "请先创建至少一套作息时间表"})
    elif not any(
        db.scalar(
            select(func.count())
            .select_from(Period)
            .where(
                Period.period_table_id == table.id,
                Period.type == PeriodType.regular.value,
            )
        )
        for table in tables
    ):
        issues.append(
            {"code": "regular_period_missing", "message": "作息时间表至少需要一个可排课节次"}
        )
    return issues


def validate_exception_date(semester: Semester, day: date) -> None:
    if semester.start_date is not None and day < semester.start_date:
        raise ValueError("特殊日期不能早于学期开始日期")
    if semester.end_date is not None and day > semester.end_date:
        raise ValueError("特殊日期不能晚于学期结束日期")


def validate_exception_fields(kind: str, makeup_weekday: int | None) -> None:
    if kind not in {x.value for x in CalendarExceptionKind}:
        raise ValueError("未知的特殊日期类型")
    if kind == CalendarExceptionKind.makeup_instruction.value and makeup_weekday is None:
        raise ValueError("补课日必须指定使用周一至周六中的课表")
    if kind == CalendarExceptionKind.no_instruction.value and makeup_weekday is not None:
        raise ValueError("停课日不能指定补课课表星期")
