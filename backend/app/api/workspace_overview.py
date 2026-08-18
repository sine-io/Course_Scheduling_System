"""工作空间首页总览 API。"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.permissions import core_viewer
from app.models.semester import Semester
from app.schemas.workspace_overview import WorkspaceOverviewOut
from app.services.workspace_overview import build_overview

router = APIRouter(tags=["workspace"])


@router.get("/workspace-overview", response_model=WorkspaceOverviewOut)
def get_workspace_overview(
    semester_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    _: object = Depends(core_viewer),
):
    semester = db.get(Semester, semester_id)
    if semester is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到学期")
    return build_overview(db, semester)
