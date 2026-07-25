"""学校模板：加载 JSON，并创建作息时间表和节次数据。"""

import json
from datetime import time
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.basedata import Subject
from app.models.period import Period, PeriodTable, PeriodType
from app.models.semester import Semester

_TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "data" / "school_templates.json"


@lru_cache
def load_templates() -> list[dict]:
    with open(_TEMPLATES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def get_template(key: str) -> dict | None:
    return next((t for t in load_templates() if t["key"] == key), None)


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def build_period_table_from_template(
    template: dict, name: str | None = None, is_default: bool = False
) -> PeriodTable:
    """根据模板创建作息时间表；此时尚未关联学期，也未提交事务。"""
    pt_data = template["period_table"]
    num_weekdays = pt_data.get("num_weekdays", 5)

    # 模板可以把指定单元格设置为固定用途或不可排课。
    blocked: set[tuple[int, int]] = set()
    for b in pt_data.get("blocked", []):
        for pno in b["period_no"]:
            blocked.add((b["weekday"], pno))

    table = PeriodTable(
        name=name or pt_data["name"],
        num_weekdays=num_weekdays,
        is_default=is_default,
    )
    for weekday in range(1, num_weekdays + 1):
        for slot in pt_data["slots"]:
            cell_type = slot["type"]
            if (weekday, slot["period_no"]) in blocked:
                cell_type = PeriodType.reserved.value
            table.periods.append(
                Period(
                    weekday=weekday,
                    period_no=slot["period_no"],
                    name=slot["name"],
                    start_time=_parse_time(slot.get("start")),
                    end_time=_parse_time(slot.get("end")),
                    type=cell_type,
                )
            )
    return table


def create_semester_from_template(
    db: Session,
    academic_year: int,
    term: int,
    template_key: str,
    start_date=None,
    end_date=None,
) -> Semester:
    """创建学期，并根据模板添加作息时间表。调用方负责提交事务。"""
    template = get_template(template_key)
    if template is None:
        raise ValueError(f"未知的学校模板：{template_key}")

    semester = Semester(
        academic_year=academic_year,
        term=term,
        start_date=start_date,
        end_date=end_date,
    )
    table = build_period_table_from_template(template, is_default=True)
    semester.period_tables.append(table)
    db.add(semester)
    db.flush()

    # 添加模板中的科目参考项，供后续创建教学任务时编辑和选择。
    for name in template.get("subjects", []):
        db.add(Subject(semester_id=semester.id, name=name))
    db.flush()
    return semester
