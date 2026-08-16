"""管理员高风险命令的确认、幂等与结构化审计边界。"""

from dataclasses import dataclass
from typing import NoReturn

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import Role, User
from app.schemas.high_risk import HighRiskConfirmation


@dataclass(frozen=True, slots=True)
class HighRiskError(Exception):
    status_code: int
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class AttemptSpec:
    action: str
    target_type: str
    target_id: int | None
    semester_id: int | None
    target_version: str
    expected_target: str
    impact: str


def _operation_id(confirmation: HighRiskConfirmation | None) -> str | None:
    return str(confirmation.operation_id) if confirmation is not None else None


def _record(
    db: Session,
    user: User,
    spec: AttemptSpec,
    *,
    operation_id: str | None,
    result: str,
    reason: str,
    detail: str,
) -> AuditLog:
    audit = AuditLog(
        operation_id=operation_id,
        user_id=user.id,
        username=user.username,
        actor_roles=sorted(user.role_names),
        action=spec.action,
        target_type=spec.target_type,
        target_id=spec.target_id,
        semester_id=spec.semester_id,
        target_version=spec.target_version,
        result=result,
        reason=reason,
        detail=detail[:500],
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


def _reject(
    db: Session,
    user: User,
    spec: AttemptSpec,
    confirmation: HighRiskConfirmation | None,
    *,
    status_code: int,
    code: str,
    message: str,
    keep_operation_id: bool = True,
) -> NoReturn:
    operation_id = _operation_id(confirmation) if keep_operation_id else None
    if operation_id and db.scalar(
        select(AuditLog.id).where(AuditLog.operation_id == operation_id)
    ):
        operation_id = None
    _record(
        db,
        user,
        spec,
        operation_id=operation_id,
        result="rejected",
        reason=code,
        detail=message,
    )
    raise HighRiskError(status_code, code, message)


def begin(
    db: Session,
    user: User,
    spec: AttemptSpec,
    confirmation: HighRiskConfirmation | None,
) -> AuditLog:
    """校验角色、确认目标与操作 ID，并持久化 pending 尝试。"""
    if Role.admin.value not in user.role_names:
        _reject(
            db,
            user,
            spec,
            confirmation,
            status_code=403,
            code="high_risk_permission_denied",
            message="只有系统管理员可以执行此高风险操作",
        )
    if confirmation is None or not confirmation.confirmed:
        _reject(
            db,
            user,
            spec,
            confirmation,
            status_code=409,
            code="high_risk_confirmation_required",
            message=f"请确认目标与影响后再继续：{spec.impact}",
        )
    if confirmation.target != spec.expected_target:
        _reject(
            db,
            user,
            spec,
            confirmation,
            status_code=409,
            code="high_risk_target_mismatch",
            message="确认目标与当前操作不一致，请刷新后重新确认",
        )
    operation_id = str(confirmation.operation_id)
    if db.scalar(select(AuditLog.id).where(AuditLog.operation_id == operation_id)):
        _reject(
            db,
            user,
            spec,
            confirmation,
            status_code=409,
            code="high_risk_duplicate_operation",
            message="此操作已经提交，请勿重复执行",
            keep_operation_id=False,
        )
    try:
        return _record(
            db,
            user,
            spec,
            operation_id=operation_id,
            result="pending",
            reason="",
            detail=spec.impact,
        )
    except IntegrityError:
        # 并发提交可能同时通过上面的读取；唯一索引仍保证只有一个命令进入业务阶段。
        db.rollback()
        _reject(
            db,
            user,
            spec,
            confirmation,
            status_code=409,
            code="high_risk_duplicate_operation",
            message="此操作已经提交，请勿重复执行",
            keep_operation_id=False,
        )


def finish(
    db: Session,
    attempt_id: int,
    *,
    result: str,
    reason: str = "",
    detail: str,
) -> AuditLog:
    """在业务事务中完成审计；失败调用方应先 rollback。"""
    audit = db.get(AuditLog, attempt_id)
    if audit is None:
        raise RuntimeError("找不到高风险操作审计记录")
    audit.result = result
    audit.reason = reason
    audit.detail = detail[:500]
    db.commit()
    db.refresh(audit)
    return audit


def update_target(
    db: Session,
    attempt_id: int,
    *,
    target_version: str,
    semester_id: int | None = None,
) -> AuditLog:
    audit = db.get(AuditLog, attempt_id)
    if audit is None:
        raise RuntimeError("找不到高风险操作审计记录")
    audit.target_version = target_version[:128]
    audit.semester_id = semester_id
    db.flush()
    return audit


def finish_after_database_restore(
    db: Session,
    *,
    operation_id: str,
    user_id: int,
    username: str,
    actor_roles: list[str],
    spec: AttemptSpec,
    detail: str,
) -> AuditLog:
    """恢复会覆盖 pending 记录；在恢复后的数据库补写最终结果。"""
    from app.models.user import User

    audit = db.scalar(select(AuditLog).where(AuditLog.operation_id == operation_id))
    if audit is None:
        audit = AuditLog(operation_id=operation_id)
        db.add(audit)
    audit.user_id = user_id if db.get(User, user_id) is not None else None
    audit.username = username
    audit.actor_roles = actor_roles
    audit.action = spec.action
    audit.target_type = spec.target_type
    audit.target_id = spec.target_id
    audit.semester_id = spec.semester_id
    audit.target_version = spec.target_version
    audit.result = "success"
    audit.reason = ""
    audit.detail = detail[:500]
    db.commit()
    db.refresh(audit)
    return audit


def error_detail(exc: HighRiskError) -> dict[str, str]:
    return {"code": exc.code, "message": exc.message}
