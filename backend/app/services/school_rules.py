"""学校统一使用的展示规则与排课准备检查。

数据库中的枚举值保持英文稳定标识；本模块只负责面向用户的简体中文标签、
公历学年格式以及全系统统一的学校时区。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.semester import Semester

TIMEZONE = "Asia/Shanghai"
ACADEMIC_YEAR_MIN = 1900
ACADEMIC_YEAR_MAX = 2100

ROLE_DISPLAY_NAMES: dict[str, str] = {
    "admin": "系统管理员",
    "director": "教务主任",
    "scheduler": "排课管理员",
    "teacher": "教师",
}

TERM_LABELS: dict[int, str] = {
    1: "第一学期",
    2: "第二学期",
}

DISPLAY_LABELS: dict[str, dict[str, str]] = {
    "leave_type": {
        "official": "公假",
        "personal": "事假",
        "sick": "病假",
        "marriage": "婚假",
        "bereavement": "丧假",
        "maternity": "产假",
        "training": "培训",
    },
    "affected_status": {
        "pending": "待处理",
        "resolved": "已处理",
        "completed": "已完成",
        "cancelled": "已取消",
    },
    "substitution_type": {
        "substitute": "代课",
        "swap": "调课",
        "merge": "合班",
        "self_study": "自习",
        "cancel": "不处理",
    },
    "export": {
        "timetable": "课表",
        "period": "节次",
        "printed_on": "打印日期",
        "school_timetable": "全校课表总表",
        "class_timetables": "全校班级课表",
        "summary": "汇总",
        "detail": "明细",
        "teacher": "教师",
        "date": "日期",
        "class": "班级",
        "subject": "科目",
        "absent_teacher": "原授课教师",
        "leave_type": "请假类型",
        "disposition": "处理方式",
        "billable": "计费",
        "funding_source": "经费来源",
        "substitution_periods": "代课课时",
        "billable_periods": "计费课时",
        "yes": "是",
        "no": "否",
    },
}

WEEKDAY_NAMES = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def display_label(group: str, key: str) -> str:
    """返回稳定枚举值对应的中文标签，未知值按原值显示。"""
    return DISPLAY_LABELS.get(group, {}).get(key, key)


def leave_type_label(value: str) -> str:
    return display_label("leave_type", value)


def affected_status_label(value: str) -> str:
    return display_label("affected_status", value)


def substitution_type_label(value: str) -> str:
    return display_label("substitution_type", value)


def export_label(key: str) -> str:
    return display_label("export", key)


def weekday_name(weekday: int) -> str:
    return WEEKDAY_NAMES[weekday - 1] if 1 <= weekday <= len(WEEKDAY_NAMES) else f"星期{weekday}"


def weekday_names() -> tuple[str, ...]:
    return WEEKDAY_NAMES


def format_semester_label(academic_year: int, term: int) -> str:
    term_label = TERM_LABELS.get(term, f"第{term}学期")
    return f"{academic_year}-{academic_year + 1}学年{term_label}"


def validate_academic_year(value: int) -> None:
    if not ACADEMIC_YEAR_MIN <= value <= ACADEMIC_YEAR_MAX:
        raise ValueError(
            f"学年起始年必须在 {ACADEMIC_YEAR_MIN} 至 {ACADEMIC_YEAR_MAX} 之间"
        )


def academic_year_config() -> dict[str, object]:
    return {
        "storage": "start_year",
        "min": ACADEMIC_YEAR_MIN,
        "max": ACADEMIC_YEAR_MAX,
        "label_format": "{year}-{next_year}学年{term_label}",
        "term_labels": TERM_LABELS,
    }


class SemesterNotReadyError(RuntimeError):
    def __init__(self, semester_id: int, issues: list[dict[str, str]] | None = None) -> None:
        self.semester_id = semester_id
        self.issues = issues or []
        super().__init__("学期排课准备尚未确认，暂不能自动排课或发布课表")


def assert_semester_ready(db: Session, semester: Semester) -> None:
    """所有学期在自动排课和发布前都必须通过准备检查。"""
    from app.services.calendar import readiness_issues

    issues = readiness_issues(db, semester)
    if semester.readiness != "ready" or issues:
        raise SemesterNotReadyError(semester.id, issues)
