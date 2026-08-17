"""操作轨迹查询(仅系统管理员)。"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Text, func, literal_column, or_, select
from sqlalchemy.orm import Session

from app.api.pagination import PaginationParams
from app.core.auth import require_roles
from app.core.db import get_db
from app.models.audit import AuditLog
from app.models.user import Role
from app.schemas.pagination import Page
from app.services.school_rules import ROLE_DISPLAY_NAMES

router = APIRouter(tags=["audit"])

admin_only = require_roles(Role.admin)


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    operation_id: str | None
    username: str
    actor_roles: list[str]
    action: str
    target_type: str
    target_id: int | None
    semester_id: int | None
    target_version: str
    result: str
    reason: str
    detail: str
    created_at: datetime


AUDIT_ACTION_LABELS: dict[str, str] = {
    "assign_substitution": "安排调课与代课",
    "auto_schedule": "自动排课",
    "bind_teacher_account": "绑定教师账号",
    "bulk_create_accounts": "批量创建教师账号",
    "cancel_leave": "撤销请假",
    "confirm_semester_readiness": "确认排课准备",
    "create_account": "创建账号",
    "create_backup": "创建备份",
    "create_calendar_exception": "新增特殊日期",
    "create_leave": "登记请假",
    "delete_assignment": "删除教学任务",
    "delete_backup": "删除备份",
    "delete_calendar_exception": "删除特殊日期",
    "delete_class_unit": "删除班级",
    "delete_period_table": "删除作息时间表",
    "delete_room": "删除教室/场地",
    "delete_scheduling_unit": "删除排课单元",
    "delete_semester": "删除学期",
    "delete_subject": "删除科目",
    "delete_teacher": "删除教师",
    "delete_timetable": "删除课表版本",
    "publish_timetable": "发布课表",
    "restore_backup": "恢复备份",
    "revoke_semester_readiness": "撤回排课准备确认",
    "update_account": "更新账号",
    "update_calendar_exception": "修改特殊日期",
    "update_school_name": "更新学校名称",
    "update_scheduling_settings": "更新排课设置",
    "update_smtp": "更新邮件设置",
}

AUDIT_TARGET_LABELS: dict[str, str] = {
    "account": "账号",
    "affected_period": "受影响节次",
    "app_setting": "系统设置",
    "assignment": "教学任务",
    "backup": "备份",
    "class_unit": "班级",
    "leave_request": "请假记录",
    "period_table": "作息时间表",
    "room": "教室/场地",
    "scheduling_unit": "排课单元",
    "semester": "学期",
    "semester_calendar_exception": "特殊日期",
    "subject": "科目",
    "teacher": "教师",
    "timetable": "课表版本",
}

AUDIT_RESULT_LABELS: dict[str, str] = {
    "success": "成功",
    "rejected": "已拒绝",
    "failed": "失败",
    "pending": "处理中",
}

# Keep this expression identical to the PostgreSQL trigram index in migration 0027.
# SQLite accepts it too, so the unit tests exercise the same search semantics.
AUDIT_SEARCH_DOCUMENT = literal_column(
    """
    lower(
        coalesce(audit_logs.username, '') || ' ' ||
        coalesce(CAST(audit_logs.actor_roles AS TEXT), '') || ' ' ||
        coalesce(audit_logs.action, '') || ' ' ||
        coalesce(audit_logs.target_type, '') || ' ' ||
        coalesce(CAST(audit_logs.target_id AS TEXT), '') || ' ' ||
        coalesce(audit_logs.target_version, '') || ' ' ||
        coalesce(audit_logs.result, '') || ' ' ||
        coalesce(audit_logs.reason, '') || ' ' ||
        coalesce(audit_logs.detail, '')
    )
    """,
    Text(),
)


def _matching_codes(token: str, labels: dict[str, str]) -> set[str]:
    return {code for code, label in labels.items() if token in label.casefold()}


def _token_filter(token: str):
    terms = {token}
    terms.update(_matching_codes(token, AUDIT_ACTION_LABELS))
    terms.update(_matching_codes(token, AUDIT_TARGET_LABELS))
    terms.update(_matching_codes(token, AUDIT_RESULT_LABELS))
    terms.update(_matching_codes(token, ROLE_DISPLAY_NAMES))

    conditions = [AUDIT_SEARCH_DOCUMENT.contains(term, autoescape=True) for term in terms]
    if token in "其他操作":
        conditions.append(AuditLog.action.not_in(AUDIT_ACTION_LABELS))
    if token in "其他对象":
        conditions.append(AuditLog.target_type.not_in(AUDIT_TARGET_LABELS))
    if token in "其他结果":
        conditions.append(AuditLog.result.not_in(AUDIT_RESULT_LABELS))
    return or_(*conditions)


def build_audit_filters(action: str | None, query: str | None):
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if query:
        filters.extend(_token_filter(token) for token in query.casefold().split())
    return filters


@router.get("/audit-logs", response_model=Page[AuditLogOut])
def list_audit_logs(
    pagination: PaginationParams,
    action: Annotated[str | None, Query(max_length=64)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    db: Session = Depends(get_db),
    _: object = Depends(admin_only),
) -> Page[AuditLogOut]:
    filters = build_audit_filters(action, q)

    total = db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    stmt = (
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return Page[AuditLogOut](
        items=list(db.scalars(stmt)),
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
