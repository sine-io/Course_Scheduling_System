"""设置向导的作息分组建议与原子应用服务。"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.basedata import ClassTrack, ClassUnit
from app.models.period import Period, PeriodTable, PeriodType
from app.models.semester import Semester
from app.schemas.semester import PeriodSetupApply, PeriodSetupGroupIn

TRACK_LABELS = {
    ClassTrack.elementary.value: "小学",
    ClassTrack.junior_high.value: "初中",
    ClassTrack.senior_high.value: "普通高中",
    ClassTrack.comprehensive.value: "综合高中",
    ClassTrack.vocational.value: "中职",
}
TRACK_ORDER = tuple(TRACK_LABELS)


class PeriodSetupValidationError(ValueError):
    """用户可修正的作息分组冲突。"""


class PeriodSetupStaleError(PeriodSetupValidationError):
    """读取草稿后，学期数据已经发生变化。"""


def _time_value(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _period_signature(period: Period) -> tuple[Any, ...]:
    return (
        period.period_no,
        period.name,
        period.type,
        _time_value(period.start_time),
        _time_value(period.end_time),
    )


def _patterns_from_table(table: PeriodTable) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    for period in table.periods:
        grouped[_period_signature(period)].append(period.weekday)
    patterns = []
    for signature, weekdays in grouped.items():
        period_no, name, period_type, start_time, end_time = signature
        patterns.append(
            {
                "period_no": period_no,
                "weekdays": sorted(weekdays),
                "name": name,
                "type": period_type,
                "start_time": start_time,
                "end_time": end_time,
            }
        )
    return sorted(patterns, key=lambda item: (item["period_no"], item["weekdays"]))


def _neutral_pattern(num_weekdays: int) -> dict[str, Any]:
    return {
        "period_no": 1,
        "weekdays": list(range(1, num_weekdays + 1)),
        "name": "第一节",
        "type": PeriodType.regular.value,
        "start_time": None,
        "end_time": None,
    }


def _snapshot(db: Session, semester_id: int) -> dict[str, Any]:
    classes = list(
        db.scalars(
            select(ClassUnit).where(ClassUnit.semester_id == semester_id).order_by(ClassUnit.id)
        ).all()
    )
    tables = list(
        db.scalars(
            select(PeriodTable)
            .where(PeriodTable.semester_id == semester_id)
            .order_by(PeriodTable.id)
        ).all()
    )
    return {
        "classes": [
            [item.id, item.name, item.grade, item.track, item.period_table_id]
            for item in classes
        ],
        "tables": [
            [
                table.id,
                table.name,
                table.num_weekdays,
                table.is_default,
                [
                    [
                        period.weekday,
                        period.period_no,
                        period.name,
                        period.type,
                        _time_value(period.start_time),
                        _time_value(period.end_time),
                    ]
                    for period in sorted(
                        table.periods,
                        key=lambda value: (value.weekday, value.period_no),
                    )
                ],
            ]
            for table in tables
        ],
    }


def _fingerprint(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(b"period-setup:1:" + payload).hexdigest()


def _class_output(item: ClassUnit) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "grade": item.grade,
        "track": item.track,
        "track_label": TRACK_LABELS.get(item.track, item.track),
        "period_table_id": item.period_table_id,
    }


def _group_status(
    classes: list[ClassUnit], groups: list[dict[str, Any]], default_key: str | None
) -> tuple[list[str], list[str], list[int]]:
    blockers: list[str] = []
    warnings: list[str] = []
    assigned: list[int] = [class_id for group in groups for class_id in group["class_ids"]]
    all_ids = {item.id for item in classes}
    assigned_set = set(assigned)
    if len(assigned) != len(assigned_set):
        blockers.append("同一个班级被分配到了多个作息分组")
    missing = sorted(all_ids - assigned_set)
    if missing:
        blockers.append(f"仍有 {len(missing)} 个班级没有分配作息分组")
    if classes and default_key is None:
        blockers.append("请指定一套学期默认作息")
    if not classes:
        warnings.append("当前学期还没有班级，作息分组建议会随基础数据补充")
    has_regular = False
    for group in groups:
        regular_count = sum(
            1
            for period in group["periods"]
            if period["type"] == PeriodType.regular.value
        )
        has_regular = has_regular or regular_count > 0
        if group["class_ids"] and regular_count == 0:
            blockers.append(f"「{group['name']}」至少需要一个常规课节次")
        if any(
            period["start_time"] is None or period["end_time"] is None
            for period in group["periods"]
        ):
            warnings.append("有节次尚未填写完整的开始和结束时间")
    if not has_regular:
        blockers.append("至少需要一个常规课节次")
    return blockers, list(dict.fromkeys(warnings)), missing


def build_draft(db: Session, semester_id: int) -> dict[str, Any]:
    semester = db.get(Semester, semester_id)
    if semester is None:
        raise PeriodSetupValidationError("找不到学期")
    classes = list(
        db.scalars(
            select(ClassUnit).where(ClassUnit.semester_id == semester_id).order_by(
                ClassUnit.grade, ClassUnit.name, ClassUnit.id
            )
        ).all()
    )
    tables = list(
        db.scalars(
            select(PeriodTable)
            .where(PeriodTable.semester_id == semester_id)
            .order_by(PeriodTable.id)
        ).all()
    )
    snapshot = _snapshot(db, semester_id)
    groups: list[dict[str, Any]] = []
    if tables:
        default_table = next((table for table in tables if table.is_default), tables[0])
        table_ids = {table.id for table in tables}
        for table in tables:
            class_ids = [
                item.id
                for item in classes
                if (item.period_table_id or default_table.id) == table.id
            ]
            groups.append(
                {
                    "key": f"table-{table.id}",
                    "table_id": table.id,
                    "name": table.name,
                    "num_weekdays": table.num_weekdays,
                    "is_default": table.id == default_table.id,
                    "class_ids": class_ids,
                    "periods": _patterns_from_table(table),
                }
            )
        # Keep a corrupt foreign reference visible instead of dropping it from the draft.
        if any(
            item.period_table_id not in table_ids and item.period_table_id is not None
            for item in classes
        ):
            groups.append(
                {
                    "key": "unresolved",
                    "table_id": None,
                    "name": "未解析作息",
                    "num_weekdays": 5,
                    "is_default": False,
                    "class_ids": [
                        item.id
                        for item in classes
                        if item.period_table_id not in table_ids
                        and item.period_table_id is not None
                    ],
                    "periods": [],
                }
            )
        source = "existing"
    else:
        by_track: dict[str, list[int]] = defaultdict(list)
        for item in classes:
            by_track[item.track].append(item.id)
        tracks = [track for track in TRACK_ORDER if track in by_track]
        if not tracks:
            tracks = [ClassTrack.junior_high.value]
        for index, track in enumerate(tracks):
            groups.append(
                {
                    "key": f"track-{track}",
                    "table_id": None,
                    "name": f"{TRACK_LABELS.get(track, track)}作息",
                    "num_weekdays": 5,
                    "is_default": index == 0,
                    "class_ids": by_track.get(track, []),
                    "periods": [_neutral_pattern(5)],
                }
            )
        source = "suggested"
    default_key = next((group["key"] for group in groups if group["is_default"]), None)
    blockers, warnings, missing = _group_status(classes, groups, default_key)
    return {
        "fingerprint": _fingerprint(snapshot),
        "source": source,
        "classes": [_class_output(item) for item in classes],
        "groups": groups,
        "unresolved_class_ids": missing,
        "ready": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }


def _replace_periods(db: Session, table: PeriodTable, group: PeriodSetupGroupIn) -> None:
    table.periods.clear()
    db.flush()
    for pattern in group.periods:
        for weekday in pattern.weekdays:
            table.periods.append(
                Period(
                    weekday=weekday,
                    period_no=pattern.period_no,
                    name=pattern.name,
                    start_time=pattern.start_time,
                    end_time=pattern.end_time,
                    type=pattern.type.value,
                )
            )


def apply_setup(db: Session, semester_id: int, body: PeriodSetupApply) -> dict[str, Any]:
    current = build_draft(db, semester_id)
    if current["fingerprint"] != body.fingerprint:
        raise PeriodSetupStaleError("作息数据已发生变化，请重新读取建议后再应用")
    names = [group.name for group in body.groups]
    if len(set(names)) != len(names):
        raise PeriodSetupValidationError("作息分组名称不可重复")
    defaults = [group for group in body.groups if group.is_default]
    if len(defaults) != 1:
        raise PeriodSetupValidationError("必须且只能有一套学期默认作息")
    if not any(
        period.type == PeriodType.regular
        for group in body.groups
        for period in group.periods
    ):
        raise PeriodSetupValidationError("至少需要一个常规课节次")
    for group in body.groups:
        if group.class_ids and not any(
            period.type == PeriodType.regular for period in group.periods
        ):
            raise PeriodSetupValidationError(f"「{group.name}」至少需要一个常规课节次")

    classes = list(
        db.scalars(select(ClassUnit).where(ClassUnit.semester_id == semester_id)).all()
    )
    class_by_id = {item.id: item for item in classes}
    all_class_ids = [class_id for group in body.groups for class_id in group.class_ids]
    if len(all_class_ids) != len(set(all_class_ids)):
        raise PeriodSetupValidationError("同一个班级不可分配到多个作息分组")
    if set(all_class_ids) != set(class_by_id):
        missing = sorted(set(class_by_id) - set(all_class_ids))
        unknown = sorted(set(all_class_ids) - set(class_by_id))
        details = []
        if missing:
            details.append(f"未分配班级 ID：{','.join(map(str, missing))}")
        if unknown:
            details.append(f"不属于当前学期的班级 ID：{','.join(map(str, unknown))}")
        raise PeriodSetupValidationError("；".join(details))

    existing_tables = {
        table.id: table
        for table in db.scalars(
            select(PeriodTable).where(PeriodTable.semester_id == semester_id)
        ).all()
    }
    table_ids = [group.table_id for group in body.groups if group.table_id is not None]
    if len(table_ids) != len(set(table_ids)):
        raise PeriodSetupValidationError("同一套作息不可在多个分组中重复")
    if any(table_id not in existing_tables for table_id in table_ids):
        raise PeriodSetupValidationError("作息分组引用了不属于当前学期的时间表")

    applied_tables: dict[str, PeriodTable] = {}
    for group in body.groups:
        table = existing_tables.get(group.table_id) if group.table_id is not None else None
        if table is None:
            table = PeriodTable(
                semester_id=semester_id,
                name=group.name,
                num_weekdays=group.num_weekdays,
                is_default=group.is_default,
            )
            db.add(table)
            db.flush()
        table.name = group.name
        table.num_weekdays = group.num_weekdays
        table.is_default = group.is_default
        _replace_periods(db, table, group)
        applied_tables[group.key] = table

    default_group = defaults[0]
    default_table = applied_tables[default_group.key]
    for group in body.groups:
        table = applied_tables[group.key]
        for class_id in group.class_ids:
            class_by_id[class_id].period_table_id = table.id
    db.flush()
    applied_ids = {table.id for table in applied_tables.values()}
    for table in existing_tables.values():
        if table.id not in applied_ids:
            db.delete(table)
    for table in applied_tables.values():
        table.is_default = table.id == default_table.id
    semester = db.get(Semester, semester_id)
    if semester is not None:
        semester.readiness = "draft"
    db.commit()
    return build_draft(db, semester_id)
