"""高风险应用服务到 HTTP 路由的薄适配层。"""

from typing import NoReturn

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.high_risk import HighRiskConfirmation
from app.services import high_risk


def begin(
    db: Session,
    user: User,
    confirmation: HighRiskConfirmation | None,
    *,
    action: str,
    target_type: str,
    target_id: int | None,
    semester_id: int | None,
    target_version: str,
    expected_target: str,
    impact: str,
) -> AuditLog:
    spec = high_risk.AttemptSpec(
        action=action,
        target_type=target_type,
        target_id=target_id,
        semester_id=semester_id,
        target_version=target_version,
        expected_target=expected_target,
        impact=impact,
    )
    try:
        return high_risk.begin(db, user, spec, confirmation)
    except high_risk.HighRiskError as exc:
        raise HTTPException(exc.status_code, high_risk.error_detail(exc)) from exc


def reject(db: Session, attempt_id: int, exc: HTTPException) -> NoReturn:
    db.rollback()
    detail = exc.detail
    if isinstance(detail, dict):
        reason = str(detail.get("code", "business_rule_rejected"))
        message = str(detail.get("message", detail))
    else:
        reason = "business_rule_rejected"
        message = str(detail)
    high_risk.finish(
        db,
        attempt_id,
        result="rejected",
        reason=reason,
        detail=message,
    )
    raise exc


def complete_delete(
    db: Session,
    attempt_id: int,
    *,
    detail: str,
) -> None:
    """先 flush 业务删除，再与 success 审计同一事务提交。"""
    try:
        db.flush()
        high_risk.finish(db, attempt_id, result="success", detail=detail)
    except Exception:
        db.rollback()
        high_risk.finish(
            db,
            attempt_id,
            result="failed",
            reason="database_write_failed",
            detail="数据库未能完成删除，目标数据未被提交",
        )
        raise
