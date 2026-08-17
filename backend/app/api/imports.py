"""Excel 导入 API:模板下载、上传导入。"""

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import high_risk_http
from app.core.auth import get_active_user
from app.core.db import get_db
from app.core.permissions import can_edit_core, core_editor, core_viewer
from app.models.user import User
from app.schemas.high_risk import HighRiskConfirmation
from app.services import combined_import, high_risk, importer, semester_context

router = APIRouter(tags=["import"])

viewer = core_viewer

VALID_ENTITIES = {"subjects", "teachers", "classes", "assignments"}
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_FILENAMES = {
    "subjects": "subjects", "teachers": "teachers",
    "classes": "classes", "assignments": "assignments",
}


def _check_entity(entity: str) -> None:
    if entity not in VALID_ENTITIES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "未知的导入类型")


@router.get("/import/templates/{entity}")
def download_template(entity: str, _: object = Depends(viewer)) -> Response:
    _check_entity(entity)
    data = importer.build_template(entity)
    filename = f"{_FILENAMES[entity]}_template.xlsx"
    return Response(
        content=data,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/import/setup/template")
def download_setup_template(_: object = Depends(viewer)) -> Response:
    """下载科目、教师、班级、教室四表合一的初始数据模板。"""
    return Response(
        content=combined_import.build_template(),
        media_type=XLSX_MIME,
        headers={
            "Content-Disposition": 'attachment; filename="school_setup_template.xlsx"'
        },
    )


def _require_setup_semester(db: Session, semester_id: int) -> None:
    try:
        semester_context.require_writable(db, semester_id)
    except semester_context.SemesterContextError as exc:
        raise HTTPException(
            exc.status_code, {"code": exc.code, "message": exc.message}
        ) from exc


async def _read_setup_workbook(file: UploadFile) -> bytes:
    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "上传文件不能为空")
    return content


@router.post("/import/setup/preview")
async def preview_setup_import(
    semester_id: int = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: object = Depends(viewer),
) -> dict:
    """解析组合工作簿并返回零写入的逐行预览。"""
    _require_setup_semester(db, semester_id)
    content = await _read_setup_workbook(file)
    try:
        return combined_import.build_plan(db, semester_id, content).as_dict()
    except combined_import.InvalidWorkbookError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/import/setup/commit")
async def commit_setup_import(
    semester_id: int = Query(...),
    file: UploadFile = File(...),
    fingerprint: str = Form(...),
    confirm_changes: bool = Form(False),
    db: Session = Depends(get_db),
    _: object = Depends(core_editor),
) -> dict:
    """重新校验工作簿，并在预览仍有效时以一个事务写入。"""
    _require_setup_semester(db, semester_id)
    content = await _read_setup_workbook(file)
    try:
        plan = combined_import.build_plan(db, semester_id, content)
    except combined_import.InvalidWorkbookError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if plan.fingerprint != fingerprint:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "combined_import_preview_stale",
                "message": "基础数据已发生变化，请重新预览后再提交",
            },
        )
    if plan.errors:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "combined_import_conflicts",
                "message": "工作簿仍有冲突，请修正后重新预览",
            },
        )
    if any(row.status == "changed" for rows in plan.rows.values() for row in rows):
        if not confirm_changes:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {
                    "code": "combined_import_changes_unconfirmed",
                    "message": "工作簿包含对现有数据的修改，请确认变更后再提交",
                },
            )
    try:
        return combined_import.apply_plan(db, plan)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "combined_import_write_conflict",
                "message": "提交时数据发生冲突，请重新预览后再试",
            },
        ) from exc


@router.post("/import/{entity}")
async def upload_import(
    entity: str,
    semester_id: int = Query(...),
    create_accounts: bool = Query(False),
    file: UploadFile = File(...),
    operation_id: str | None = Form(None),
    confirmed: bool = Form(False),
    target: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_active_user),
) -> dict:
    _check_entity(entity)
    if not can_edit_core(user):
        if not create_accounts:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "权限不足")
    attempt = None
    if create_accounts:
        if entity != "teachers":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "只有教师导入支持创建账号")
        confirmation = None
        if operation_id is not None:
            try:
                confirmation = HighRiskConfirmation(
                    operation_id=operation_id,
                    confirmed=confirmed,
                    target=target,
                )
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "确认信息格式不正确",
                ) from exc
        spec = high_risk.AttemptSpec(
            action="bulk_create_accounts",
            target_type="semester",
            target_id=semester_id,
            semester_id=semester_id,
            target_version=f"学期 #{semester_id} 教师导入",
            expected_target=f"semester:{semester_id}:teacher-accounts",
            impact=f"导入教师并为学期 #{semester_id} 批量创建登录账号",
        )
        attempt = high_risk_http.begin_spec(db, user, confirmation, spec)
    try:
        semester_context.require_writable(db, semester_id)
    except semester_context.SemesterContextError as exc:
        if attempt is not None:
            high_risk_http.reject_code(
                db,
                attempt.id,
                code=exc.code,
                message=exc.message,
                status_code=exc.status_code,
            )
        raise HTTPException(exc.status_code, {"code": exc.code, "message": exc.message}) from exc
    content = await file.read()
    try:
        result = importer.run_import(db, entity, semester_id, content, create_accounts)
    except Exception:
        db.rollback()
        if attempt is not None:
            high_risk.finish(
                db,
                attempt.id,
                result="failed",
                reason="import_file_invalid",
                detail="无法读取文件,请确认为有效的 Excel 文件",
            )
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "无法读取文件,请确认为有效的 Excel 文件"
        ) from None
    if attempt is not None:
        if result.errors:
            high_risk.finish(
                db,
                attempt.id,
                result="rejected",
                reason="import_validation_failed",
                detail=f"教师导入校验失败，共 {len(result.errors)} 项错误",
            )
        else:
            high_risk.finish(
                db,
                attempt.id,
                result="success",
                detail=(
                    f"已导入 {result.imported} 位教师并创建 "
                    f"{result.accounts_created} 个登录账号"
                ),
            )
    response = {
        "imported": result.imported,
        "errors": result.errors,
    }
    if create_accounts:
        response["accounts_created"] = result.accounts_created
    return response
