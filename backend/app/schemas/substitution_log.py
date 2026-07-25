"""今日看板与调课与代课日志 schema(M4-4)。"""

from datetime import date, time

from pydantic import BaseModel

# 字段名 date/start_time 会遮蔽同名类型,故以别名标注类型
_Date = date
_Time = time


class LogEntryOut(BaseModel):
    affected_period_id: int
    date: _Date
    weekday: int
    period_no: int
    period_name: str
    start_time: _Time | None = None
    end_time: _Time | None = None
    class_names: str
    subject_name: str
    room_name: str
    absent_teacher_id: int
    absent_teacher_name: str
    leave_type: str
    leave_type_label: str
    status: str
    status_label: str
    disposed: bool
    sub_type: str | None = None
    sub_type_label: str | None = None
    handler_teacher_id: int | None = None
    handler_name: str | None = None
    counts_toward_hours: bool | None = None
    swap_date: _Date | None = None
    swap_period_name: str = ""
    swap_class_names: str = ""
    swap_subject_name: str = ""
    note: str = ""


class DailyBoardOut(BaseModel):
    """今日看板:表头(校名/日期/学期)供打印通知单直接使用。"""

    date: _Date
    weekday: int
    school_name: str
    semester_label: str
    entries: list[LogEntryOut] = []
