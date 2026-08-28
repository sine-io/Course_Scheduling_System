"""排课规则编辑器 API：模板目录、版本草稿、校验与激活。"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.permissions import core_editor, core_viewer
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.scheduling_rule import (
    ActivateRulesRequest,
    RuleTemplateOut,
    RuleValidationOut,
    SchedulingRuleOut,
    SchedulingRuleUpsert,
    SchedulingRuleWorkspaceOut,
)
from app.services import scheduling_rules as rules_service
from app.services import semester_context

router = APIRouter(tags=["scheduling-rules"])


def _writable(db: Session, semester_id: int) -> None:
    try:
        semester_context.require_writable(db, semester_id)
    except semester_context.SemesterContextError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": exc.message}) from exc


def _rule_error(exc: rules_service.SchedulingRuleError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND
        if exc.code in {"semester_not_found", "rule_not_found"}
        else status.HTTP_409_CONFLICT
        if exc.code in {"rule_revision_invalid", "no_draft"}
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code, {"code": exc.code, "message": exc.message})


def _revision_conflict() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        {"code": "rule_revision_conflict", "message": "规则草稿刚被其他用户修改，请重新读取后再试"},
    )


@router.get("/scheduling-rules/templates", response_model=list[RuleTemplateOut])
def list_rule_templates(_: object = Depends(core_viewer)) -> list[RuleTemplateOut]:
    return [
        RuleTemplateOut(
            key=item.key,
            label=item.label,
            description=item.description,
            supported=item.supported,
            target_types=list(item.target_types),
            operators=list(item.operators),
            strengths=list(item.strengths),
            operator_strengths={
                operator: list(rules_service.allowed_strengths(item, operator))
                for operator in item.operators
            },
            unavailable_reason=item.unavailable_reason,
        )
        for item in rules_service.template_catalog()
    ]


@router.get("/scheduling-rules", response_model=SchedulingRuleWorkspaceOut)
def get_rule_workspace(
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(core_viewer),
) -> SchedulingRuleWorkspaceOut:
    try:
        return SchedulingRuleWorkspaceOut.model_validate(rules_service.workspace(db, semester_id))
    except rules_service.SchedulingRuleError as exc:
        raise _rule_error(exc) from exc


@router.post(
    "/scheduling-rules",
    response_model=SchedulingRuleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_scheduling_rule(
    body: SchedulingRuleUpsert,
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(core_editor),
) -> SchedulingRuleOut:
    _writable(db, semester_id)
    try:
        row = rules_service.create_rule(
            db,
            semester_id,
            body.model_dump(),
            user_id=user.id,
            username=user.username,
        )
        db.add(
            AuditLog(
                user_id=user.id,
                username=user.username,
                action="create_scheduling_rule",
                target_type="scheduling_rule",
                target_id=row.id,
                detail=f"新增排课规则「{row.name}」",
            )
        )
        db.commit()
        db.refresh(row)
        return SchedulingRuleOut.model_validate(rules_service.rule_out(db, semester_id, row))
    except rules_service.SchedulingRuleError as exc:
        db.rollback()
        raise _rule_error(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise _revision_conflict() from exc


@router.put("/scheduling-rules/{rule_key}", response_model=SchedulingRuleOut)
def update_scheduling_rule(
    rule_key: str,
    body: SchedulingRuleUpsert,
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(core_editor),
) -> SchedulingRuleOut:
    _writable(db, semester_id)
    try:
        row = rules_service.create_rule(
            db,
            semester_id,
            body.model_dump(),
            user_id=user.id,
            username=user.username,
            rule_key=rule_key,
        )
        db.add(
            AuditLog(
                user_id=user.id,
                username=user.username,
                action="update_scheduling_rule",
                target_type="scheduling_rule",
                target_id=row.id,
                detail=f"修改排课规则「{row.name}」",
            )
        )
        db.commit()
        db.refresh(row)
        return SchedulingRuleOut.model_validate(rules_service.rule_out(db, semester_id, row))
    except rules_service.SchedulingRuleError as exc:
        db.rollback()
        raise _rule_error(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise _revision_conflict() from exc


@router.delete("/scheduling-rules/{rule_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scheduling_rule(
    rule_key: str,
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(core_editor),
) -> Response:
    _writable(db, semester_id)
    try:
        rules_service.delete_rule(
            db,
            semester_id,
            rule_key,
            user_id=user.id,
            username=user.username,
        )
        db.add(
            AuditLog(
                user_id=user.id,
                username=user.username,
                action="delete_scheduling_rule",
                target_type="scheduling_rule",
                detail=f"从规则草稿停用规则 {rule_key}",
            )
        )
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except rules_service.SchedulingRuleError as exc:
        db.rollback()
        raise _rule_error(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise _revision_conflict() from exc


@router.post("/scheduling-rules/validate", response_model=RuleValidationOut)
def validate_scheduling_rules(
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(core_viewer),
) -> RuleValidationOut:
    try:
        return RuleValidationOut.model_validate(rules_service.validate_rules(db, semester_id))
    except rules_service.SchedulingRuleError as exc:
        raise _rule_error(exc) from exc


@router.post("/scheduling-rules/activate", response_model=SchedulingRuleWorkspaceOut)
def activate_scheduling_rules(
    body: ActivateRulesRequest,
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(core_editor),
) -> SchedulingRuleWorkspaceOut:
    _writable(db, semester_id)
    try:
        revision = rules_service.activate(
            db,
            semester_id,
            user_id=user.id,
            username=user.username,
            note=body.note,
        )
        db.add(
            AuditLog(
                user_id=user.id,
                username=user.username,
                action="activate_scheduling_rules",
                target_type="scheduling_rule_revision",
                target_id=revision.id,
                detail=f"激活排课规则 v{revision.revision_no}",
            )
        )
        db.commit()
        return SchedulingRuleWorkspaceOut.model_validate(rules_service.workspace(db, semester_id))
    except rules_service.SchedulingRuleError as exc:
        db.rollback()
        raise _rule_error(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise _revision_conflict() from exc
