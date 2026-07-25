"""调课与代课处理工作台:代课推荐、指派处理方式、调课(M4-2)。

处理方式是行政决定,统一限排课管理员/教务主任。教师端不在这里处理(只在通知端「确认收到」)。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.db import get_db
from app.models.audit import AuditLog
from app.models.leave import AffectedPeriod
from app.models.substitution import Substitution, SubstitutionType
from app.models.user import Role, User
from app.schemas.substitution import (
    AssignRequest,
    CandidateOut,
    RecommendationOut,
    SubstitutionOut,
)
from app.services import school_rules
from app.services import substitution_recommender as recommender
from app.services import substitutions as sub_service

router = APIRouter(tags=["substitutions"])

editor = require_roles(Role.scheduler, Role.director)


def _get_affected(db: Session, affected_id: int) -> AffectedPeriod:
    ap = db.get(AffectedPeriod, affected_id)
    if ap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到受影响节次")
    return ap


def _sub_out(sub: Substitution) -> SubstitutionOut:
    return SubstitutionOut(
        id=sub.id,
        affected_period_id=sub.affected_period_id,
        type=sub.type,
        type_label=school_rules.substitution_type_label(sub.type),
        handler_teacher_id=sub.handler_teacher_id,
        handler_name=sub.handler.name if sub.handler else None,
        counts_toward_hours=sub.counts_toward_hours,
        funding_source=sub.funding_source,
        swap_date=sub.swap_date,
        swap_period_name=sub.swap_period_name,
        swap_class_names=sub.swap_class_names,
        swap_subject_name=sub.swap_subject_name,
        created_by_name=sub.created_by_name,
    )


@router.get("/affected-periods/{affected_id}/recommendations", response_model=RecommendationOut)
def get_recommendations(affected_id: int, db: Session = Depends(get_db), _: User = Depends(editor)):
    """这一节该找谁代:硬性过滤后排序,每位候选附理由。"""
    affected = _get_affected(db, affected_id)
    rec = recommender.recommend(db, affected)
    return RecommendationOut(
        affected_period_id=rec.affected_period_id,
        no_candidate_hint=rec.no_candidate_hint,
        candidates=[
            CandidateOut(
                teacher_id=c.teacher_id,
                teacher_name=c.teacher_name,
                same_subject=c.same_subject,
                at_school_that_day=c.at_school_that_day,
                sub_periods_this_month=c.sub_periods_this_month,
                reasons=list(c.reasons),
            )
            for c in rec.candidates
        ],
    )


@router.put("/affected-periods/{affected_id}/substitution", response_model=SubstitutionOut)
def assign_substitution(
    affected_id: int,
    body: AssignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(editor),
):
    """指派处理方式(代课/调课/合班/自习/不处理);指派即生效并通知处理教师。"""
    affected = _get_affected(db, affected_id)
    try:
        sub = sub_service.assign(
            db,
            affected,
            sub_type=body.type,
            handler_teacher_id=body.handler_teacher_id,
            counts_toward_hours=body.counts_toward_hours,
            funding_source=body.funding_source,
            swap_entry_id=body.swap_entry_id,
            swap_date=body.swap_date,
            created_by_user_id=user.id,
            created_by_name=user.username,
        )
    except sub_service.SubstitutionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    db.add(
        AuditLog(
            user_id=user.id,
            username=user.username,
            action="assign_substitution",
            target_type="affected_period",
            target_id=affected.id,
            detail=(
                f"{affected.leave_request.teacher.name} {affected.date} {affected.period_name}"
                f" → {school_rules.substitution_type_label(sub.type)}"
                + (f"({sub.handler.name})" if sub.handler else "")
            )[:500],
        )
    )
    db.commit()
    db.refresh(sub)
    return _sub_out(sub)


@router.delete("/affected-periods/{affected_id}/substitution", status_code=status.HTTP_200_OK)
def clear_substitution(
    affected_id: int, db: Session = Depends(get_db), user: User = Depends(editor)
):
    """撤回处理方式:退回待处理,已指派教师收到取消通知。"""
    affected = _get_affected(db, affected_id)
    try:
        sub_service.clear(db, affected, actor_name=user.username)
    except sub_service.SubstitutionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.commit()
    return {"affected_period_id": affected.id, "status": affected.status}


@router.get("/substitution-types", response_model=dict[str, str])
def substitution_types(_: User = Depends(editor)):
    return {t.value: school_rules.substitution_type_label(t.value) for t in SubstitutionType}


@router.get("/affected-periods/{affected_id}/substitution", response_model=SubstitutionOut | None)
def get_substitution(affected_id: int, db: Session = Depends(get_db), _: User = Depends(editor)):
    sub = db.scalar(select(Substitution).where(Substitution.affected_period_id == affected_id))
    return _sub_out(sub) if sub else None
