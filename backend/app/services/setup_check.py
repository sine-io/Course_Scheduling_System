"""Derive setup completion from persisted semester data."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.basedata import ClassUnit, Room, Subject, Teacher
from app.models.calendar import SemesterCalendarException
from app.models.period import Period, PeriodTable, PeriodType
from app.models.semester import Semester
from app.schemas.wizard import SemesterSummary, SetupCheckItem, SetupCheckOut


def _count(db: Session, model, semester_id: int) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(model).where(model.semester_id == semester_id)
        )
        or 0
    )


def build_check(db: Session, semester: Semester) -> SetupCheckOut:
    """Return blockers and reminders without changing the semester."""
    semester_id = semester.id
    summary = SemesterSummary(
        subjects=_count(db, Subject, semester_id),
        teachers=_count(db, Teacher, semester_id),
        classes=_count(db, ClassUnit, semester_id),
        rooms=_count(db, Room, semester_id),
    )
    blockers: list[SetupCheckItem] = []
    warnings: list[SetupCheckItem] = []

    def block(code: str, message: str, step: int) -> None:
        blockers.append(SetupCheckItem(code=code, message=message, step=step))

    def warn(code: str, message: str, step: int) -> None:
        warnings.append(SetupCheckItem(code=code, message=message, step=step))

    if semester.start_date is None or semester.end_date is None:
        block("semester_dates_missing", "请填写学期开始日期和结束日期", 0)
    elif semester.end_date < semester.start_date:
        block("semester_dates_invalid", "学期结束日期不可早于开始日期", 0)

    if summary.subjects == 0:
        block("subjects_missing", "至少需要录入 1 个科目", 1)
    if summary.teachers == 0:
        block("teachers_missing", "至少需要录入 1 位教师", 1)
    if summary.classes == 0:
        block("classes_missing", "至少需要录入 1 个班级", 1)

    # Import conflicts never enter persisted state: preview is read-only and the
    # transactional commit rejects any conflict before writing these records.

    tables = list(
        db.scalars(
            select(PeriodTable).where(PeriodTable.semester_id == semester_id)
        ).all()
    )
    table_ids = {table.id for table in tables}
    default_ids = {table.id for table in tables if table.is_default}
    regular_table_ids = set(
        db.scalars(
            select(Period.period_table_id)
            .join(PeriodTable, PeriodTable.id == Period.period_table_id)
            .where(
                PeriodTable.semester_id == semester_id,
                Period.type == PeriodType.regular.value,
            )
            .distinct()
        ).all()
    )
    if not regular_table_ids:
        block("regular_period_missing", "至少需要配置 1 节常规课", 2)

    if len(default_ids) == 0:
        block("period_default_missing", "请指定一套学期默认作息", 2)
    elif len(default_ids) > 1:
        block("period_default_conflict", "存在多套默认作息，请只保留一套", 2)

    default_id = next(iter(default_ids)) if len(default_ids) == 1 else None
    classes = list(
        db.scalars(select(ClassUnit).where(ClassUnit.semester_id == semester_id)).all()
    )
    unresolved = []
    no_regular = []
    table_names = {table.id: table.name for table in tables}
    for class_unit in classes:
        resolved_id = class_unit.period_table_id or default_id
        if resolved_id is None or resolved_id not in table_ids:
            unresolved.append(class_unit.name)
        elif resolved_id not in regular_table_ids:
            no_regular.append(
                f"{class_unit.name}（{table_names.get(resolved_id, '未知作息')}）"
            )
    if unresolved:
        block(
            "period_assignment_unresolved",
            f"有 {len(unresolved)} 个班级没有可用的作息分组",
            2,
        )
    if no_regular:
        block(
            "assigned_period_without_regular",
            f"有 {len(no_regular)} 个班级使用的作息没有常规课节次",
            2,
        )

    if summary.rooms == 0:
        warn("rooms_missing", "尚未录入教室/场地，可稍后补充", 1)
    account_count = int(
        db.scalar(
            select(func.count())
            .select_from(Teacher)
            .where(Teacher.semester_id == semester_id, Teacher.user_id.is_not(None))
        )
        or 0
    )
    if account_count == 0:
        warn("teacher_accounts_missing", "尚未绑定教师账号，可稍后在账号管理中处理", 1)
    if _count(db, SemesterCalendarException, semester_id) == 0:
        warn("special_dates_missing", "尚未登记停课或补课等特殊日期", 0)
    missing_time_count = int(
        db.scalar(
            select(func.count())
            .select_from(Period)
            .join(PeriodTable, PeriodTable.id == Period.period_table_id)
            .where(
                PeriodTable.semester_id == semester_id,
                (Period.start_time.is_(None) | Period.end_time.is_(None)),
            )
        )
        or 0
    )
    if missing_time_count:
        warn(
            "bell_times_missing",
            f"有 {missing_time_count} 个课节尚未填写完整铃声时间",
            2,
        )

    first_incomplete_step = min((item.step for item in blockers), default=3)
    return SetupCheckOut(
        semester_id=semester_id,
        can_complete=not blockers,
        first_incomplete_step=first_incomplete_step,
        blockers=blockers,
        warnings=warnings,
        summary=summary,
    )
