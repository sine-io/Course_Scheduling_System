"""数据库备份与恢复(M5-2)。系统管理员专用。

列表/下载/上传由 api 直接读写共挂的备份 volume;实际 pg_dump/pg_restore 派到 worker。
恢复统一**先自动备份现状**(可反悔),完成后强制全员重新登录。
"""

import logging
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api import high_risk_http
from app.core.auth import get_active_user, require_roles
from app.core.db import get_db
from app.models.audit import AuditLog
from app.models.user import Role, User
from app.schemas.backup import BackupOut, RestoreResult
from app.schemas.high_risk import HighRiskConfirmation
from app.services import backup as backup_service
from app.services import high_risk
from app.workers import queue as job_queue

logger = logging.getLogger(__name__)

router = APIRouter(tags=["backups"])

admin_only = require_roles(Role.admin)


def _out(info: backup_service.BackupInfo) -> BackupOut:
    return BackupOut.of(info.name, info.size_bytes, info.created_at, info.reason)


@router.get("/backups", response_model=list[BackupOut])
def list_backups(_: User = Depends(admin_only)):
    return [_out(i) for i in backup_service.list_backups()]


@router.post("/backups", response_model=BackupOut, status_code=status.HTTP_201_CREATED)
def create_backup(
    confirmation: HighRiskConfirmation | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    """立即备份(pg_dump 于 worker)。"""
    attempt = high_risk_http.begin(
        db,
        user,
        confirmation,
        action="create_backup",
        target_type="backup",
        target_id=None,
        semester_id=None,
        target_version="新建手动备份",
        expected_target="backup:create",
        impact="创建一份包含当前全部系统数据的手动备份",
    )
    try:
        data = job_queue.run_backup("manual")
    except job_queue.BackupJobError as e:
        db.rollback()
        high_risk.finish(
            db,
            attempt.id,
            result="failed",
            reason="backup_job_failed",
            detail=f"备份失败：{e}",
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"备份失败:{e}") from e
    high_risk.update_target(db, attempt.id, target_version=data["name"])
    high_risk.finish(
        db,
        attempt.id,
        result="success",
        detail=f"已创建手动备份 {data['name']}",
    )
    return BackupOut.of(**{k: data[k] for k in ("name", "size_bytes", "created_at", "reason")})


def _get_backup(name: str) -> backup_service.BackupInfo:
    info = next((i for i in backup_service.list_backups() if i.name == name), None)
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到备份")
    return info


@router.get("/backups/{name}/download")
def download_backup(name: str, _: User = Depends(admin_only)):
    info = _get_backup(name)
    from app.core.config import settings
    return FileResponse(
        path=f"{settings.backup_dir}/{info.name}",
        media_type="application/octet-stream", filename=info.name,
    )


@router.delete("/backups/{name}", status_code=status.HTTP_200_OK)
def delete_backup(
    name: str,
    confirmation: HighRiskConfirmation | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    attempt = high_risk_http.begin(
        db,
        user,
        confirmation,
        action="delete_backup",
        target_type="backup",
        target_id=None,
        semester_id=None,
        target_version=name,
        expected_target=f"backup:{name}",
        impact=f"永久删除备份 {name}，删除后无法用于恢复",
    )
    try:
        info = _get_backup(name)
    except HTTPException as exc:
        high_risk_http.reject_detail(
            db,
            attempt.id,
            reason="backup_not_found",
            detail=str(exc.detail),
            status_code=exc.status_code,
        )
    from app.core.config import settings
    try:
        os.remove(f"{settings.backup_dir}/{info.name}")
    except OSError as e:
        db.rollback()
        high_risk.finish(
            db,
            attempt.id,
            result="failed",
            reason="backup_delete_failed",
            detail=f"删除备份 {info.name} 失败",
        )
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "删除失败") from e
    high_risk.finish(
        db,
        attempt.id,
        result="success",
        detail=f"已永久删除备份 {info.name}",
    )
    return {"deleted": info.name}


def _restore(
    db: Session,
    user: User,
    target_name: str,
    attempt: AuditLog,
    spec: high_risk.AttemptSpec,
) -> RestoreResult:
    """先备份现状,再恢复;完成后强制全员重新登录。"""
    # 排课进行中不可恢复:pg_restore --clean 覆盖整个数据库,而排课中的 worker 正要把
    # 结果写回同一个库;写回的草稿会落进一个刚被抹掉的世界(Fable 5 M5 复审 A)。
    if job_queue.solver_busy():
        high_risk_http.reject_detail(
            db,
            attempt.id,
            reason="solver_busy",
            detail="排课进行中,请待排课完成后再恢复",
            status_code=status.HTTP_409_CONFLICT,
        )

    # 恢复前先关掉本请求的 session。pg_restore --clean 会中止数据库上的所有连接,包含
    # 验证身份时建立的连接;而 FastAPI 的 yield 依赖是在**响应发送后**才收尾,届时
    # db.close() 会通过已经失效的连接发送 ROLLBACK,在日志中输出一段 AdminShutdown
    # traceback——响应与数据都是对的,但刚按下「恢复」的排课管理员看到那段红字,只会以为
    # 恢复失败了。恢复期间本来就用不到这个数据库会话(审计记录通过新连接写入)。
    # 关闭前先把后续要用的字段取成标量值,避免 user 成为 detached instance。
    actor_id, actor_name = user.id, user.username
    actor_roles = sorted(user.role_names)
    operation_id = attempt.operation_id
    if operation_id is None:
        raise RuntimeError("高风险恢复操作缺少 operation_id")
    db.close()

    try:
        presafe = job_queue.run_backup("presafe")
        warnings = job_queue.run_restore(target_name)
    except job_queue.BackupJobError as e:
        db.rollback()
        high_risk.finish(
            db,
            attempt.id,
            result="failed",
            reason="backup_job_failed",
            detail=f"恢复 {target_name} 失败：{e}",
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"恢复失败:{e}") from e
    # 恢复已覆盖整个数据库并中止旧连接,且原本的数据已被取代;审计要以**新连接**写进
    # **恢复后**的数据库,否则不是连接已死就是记录被覆盖掉。
    from app.core.db import engine
    engine.dispose()
    audit_detail = f"恢复自 {target_name};现状已备份为 {presafe['name']}"
    if warnings:
        audit_detail += f";可忽略警告 {len(warnings)} 则"
    try:
        high_risk.finish_after_database_restore(
            db,
            operation_id=operation_id,
            user_id=actor_id,
            username=actor_name,
            actor_roles=actor_roles,
            spec=spec,
            detail=audit_detail,
        )
    except Exception as exc:  # noqa: BLE001 - 已完成的恢复不能伪装成失败
        logger.critical("恢复完成但审计补写失败", exc_info=True)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "恢复已完成，但审计记录写入失败；请立即联系维护人员核验",
        ) from exc
    return RestoreResult(
        restored_from=target_name, presafe_backup=presafe["name"], warnings=warnings,
    )


@router.post("/backups/{name}/restore", response_model=RestoreResult)
def restore_backup(
    name: str,
    confirmation: HighRiskConfirmation | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    """从现有备份恢复(恢复前自动备份现状)。"""
    spec = high_risk.AttemptSpec(
        action="restore_backup",
        target_type="backup",
        target_id=None,
        semester_id=None,
        target_version=name,
        expected_target=f"backup:{name}",
        impact=f"使用 {name} 覆盖当前全部数据，恢复后所有用户需要重新登录",
    )
    attempt = high_risk_http.begin_spec(db, user, confirmation, spec)
    try:
        _get_backup(name)
    except HTTPException as exc:
        high_risk_http.reject_detail(
            db,
            attempt.id,
            reason="backup_not_found",
            detail=str(exc.detail),
            status_code=exc.status_code,
        )
    return _restore(db, user, name, attempt, spec)


@router.post("/backups/restore-upload", response_model=RestoreResult)
async def restore_from_upload(
    file: UploadFile = File(...),
    operation_id: str | None = Form(None),
    confirmed: bool = Form(False),
    target: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
):
    """上传备份文件并恢复。非法文件直接拒绝、不动数据库(验收②)。"""
    confirmation: HighRiskConfirmation | None = None
    if operation_id is not None:
        try:
            confirmation = HighRiskConfirmation(
                operation_id=operation_id,
                confirmed=confirmed,
                target=target,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "确认信息格式不正确") from exc
    filename = file.filename or "upload.dump"
    spec = high_risk.AttemptSpec(
        action="restore_backup",
        target_type="backup",
        target_id=None,
        semester_id=None,
        target_version=filename,
        expected_target=f"upload:{filename}",
        impact=f"上传 {filename} 并覆盖当前全部数据，恢复后所有用户需要重新登录",
    )
    attempt = high_risk_http.begin_spec(db, user, confirmation, spec)
    content = await file.read()
    try:
        name = backup_service.save_uploaded(filename, content)
    except backup_service.BackupError as e:
        db.rollback()
        high_risk.finish(
            db,
            attempt.id,
            result="rejected",
            reason="invalid_backup_file",
            detail=str(e),
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    high_risk.update_target(db, attempt.id, target_version=f"{filename} -> {name}")
    spec = high_risk.AttemptSpec(
        action=spec.action,
        target_type=spec.target_type,
        target_id=spec.target_id,
        semester_id=spec.semester_id,
        target_version=f"{filename} -> {name}",
        expected_target=spec.expected_target,
        impact=spec.impact,
    )
    try:
        return _restore(db, user, name, attempt, spec)
    except HTTPException:
        backup_service.discard(name)
        raise
