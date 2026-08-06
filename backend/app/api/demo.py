"""示例数据：一键创建一所完整的虚构初中，仅限管理员。

全新系统没有业务数据，用户通常需要先创建大量班级、教师和教学任务才能体验
自动排课。本接口用于生成一组可直接排课的演示数据。

安全限制：仅在系统完全没有任何学期时允许执行，避免污染已开始配置的正式环境。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.db import get_db
from app.models.audit import AuditLog
from app.models.user import Role, User
from app.services import demo_data

router = APIRouter(tags=["demo"])

admin_only = require_roles(Role.admin)


class DemoDataOut(BaseModel):
    semester_id: int
    school_name: str
    classes: int
    teachers: int
    subjects: int
    rooms: int
    assignments: int
    total_periods: int
    max_overtime_used: int
    under_target: int


class DemoDataStatus(BaseModel):
    available: bool
    reason: str = ""
    school_name: str = ""


@router.get("/demo-data", response_model=DemoDataStatus)
def demo_status(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    """返回当前系统是否允许加载示例数据。"""
    spec_name = demo_data.load_spec()["school_name"]
    if demo_data.any_semester_exists(db):
        return DemoDataStatus(
            available=False,
            reason="系统已有学期数据。示例数据只能在全新系统中创建。",
            school_name=spec_name,
        )
    return DemoDataStatus(available=True, school_name=spec_name)


@router.post("/demo-data", response_model=DemoDataOut, status_code=status.HTTP_201_CREATED)
def create_demo_data(db: Session = Depends(get_db), user: User = Depends(admin_only)):
    if demo_data.any_semester_exists(db):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "系统已有学期数据，无法加载示例数据。"
            "如需重新体验，请先删除现有学期或使用一套全新部署。",
        )
    summary = demo_data.generate(db)
    db.add(AuditLog(
        user_id=user.id, username=user.username, action="create_demo_data",
        target_type="semester", target_id=summary.semester_id,
        detail=(
            f"加载示例数据：{summary.classes} 个班级、{summary.teachers} 名教师、"
            f"{summary.assignments} 条教学任务，共 {summary.total_periods} 课时"
        ),
    ))
    db.commit()
    return DemoDataOut(**summary.__dict__)
