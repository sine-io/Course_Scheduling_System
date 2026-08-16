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
from sqlalchemy.orm import Session

from app.core.auth import get_active_user
from app.core.db import get_db
from app.core.permissions import can_edit_core, core_viewer
from app.models.user import User
from app.schemas.high_risk import HighRiskConfirmation
from app.services import high_risk, importer, semester_context

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
        try:
            attempt = high_risk.begin(db, user, spec, confirmation)
        except high_risk.HighRiskError as exc:
            raise HTTPException(exc.status_code, high_risk.error_detail(exc)) from exc
    try:
        semester_context.require_writable(db, semester_id)
    except semester_context.SemesterContextError as exc:
        if attempt is not None:
            db.rollback()
            high_risk.finish(
                db,
                attempt.id,
                result="rejected",
                reason=exc.code,
                detail=exc.message,
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
