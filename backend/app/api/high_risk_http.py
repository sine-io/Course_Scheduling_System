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
    return begin_spec(db, user, confirmation, spec)


def begin_spec(
    db: Session,
    user: User,
    confirmation: HighRiskConfirmation | None,
    spec: high_risk.AttemptSpec,
) -> AuditLog:
    """校验一个已经由调用方组装好的高风险命令规格。"""
    try:
        return high_risk.begin(db, user, spec, confirmation)
    except high_risk.HighRiskError as exc:
        raise HTTPException(exc.status_code, high_risk.error_detail(exc)) from exc


def reject(db: Session, attempt_id: int, exc: HTTPException) -> NoReturn:
    # 业务校验可能发生在目标名称/学期补齐之后。回滚业务写入时保留这些审计快照，
    # 否则只读或引用规则拒绝会退回成难以查询的纯 ID。
    audit = db.get(AuditLog, attempt_id)
    target_version = audit.target_version if audit is not None else ""
    semester_id = audit.semester_id if audit is not None else None
    db.rollback()
    audit = db.get(AuditLog, attempt_id)
    if audit is not None:
        audit.target_version = target_version
        audit.semester_id = semester_id
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
