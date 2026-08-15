"""首次进入路线的领域规则。

路线选择是单校级的向导状态，不是用户权限或可随意覆盖的前端偏好。正式学期一旦
存在，示例路线就不能再写入；示例体验可以安全地转入正式建校，两个学期的数据仍
保持独立。
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.semester import Semester
from app.models.wizard import SINGLETON_ID, WizardRoute, WizardState
from app.services import demo_data


@dataclass(frozen=True, slots=True)
class OnboardingRouteError(Exception):
    code: str
    message: str
    status_code: int = 409

    def __str__(self) -> str:
        return self.message


def get_or_create_state(db: Session) -> WizardState:
    state = db.get(WizardState, SINGLETON_ID)
    if state is None:
        state = WizardState(id=SINGLETON_ID, current_step=0, completed=False)
        db.add(state)
        db.flush()
    return state


def _semesters(db: Session) -> list[Semester]:
    return list(db.scalars(select(Semester).order_by(Semester.id)))


def effective_route(db: Session, state: WizardState | None = None) -> str | None:
    """兼容迁移前已存在的数据，推导而不改变原始向导进度。"""
    state = state or db.get(WizardState, SINGLETON_ID)
    if state is not None and state.route in {route.value for route in WizardRoute}:
        return state.route
    semesters = _semesters(db)
    if semesters and all(semester.is_demo for semester in semesters):
        return WizardRoute.demo.value
    if semesters and any(not semester.is_demo for semester in semesters):
        return WizardRoute.formal.value
    return None


def choose_route(db: Session, route: str) -> WizardState:
    """选择或安全切换路线，返回已更新的单例向导状态。"""
    if route not in {item.value for item in WizardRoute}:
        raise OnboardingRouteError("invalid_route", "未知的首次进入路线", status_code=422)

    state = get_or_create_state(db)
    semesters = _semesters(db)
    has_formal = any(not semester.is_demo for semester in semesters)
    current = effective_route(db, state)

    if route == WizardRoute.demo.value and has_formal:
        raise OnboardingRouteError(
            "formal_data_exists",
            "已有正式学期数据，不能切换到示例路线；示例数据不会覆盖正式数据",
        )

    changed = current != route
    if changed:
        # 只有示例 -> 正式会保留示例学期并从正式向导第 0 步开始。
        state.route = route
        state.current_step = 0
        state.completed = False
        state.semester_id = None
    elif state.route is None:
        # 迁移前的数据库推导出路线后，把选择显式固化，保证刷新/重登一致。
        state.route = route

    # 没有正式数据时可以在两条空白路线之间重选；正式学期存在后锁定路线。
    if route == WizardRoute.formal.value and has_formal and state.route != route:
        state.route = route
    db.flush()
    return state


def route_snapshot(db: Session, state: WizardState | None = None) -> dict[str, object]:
    # 读取路线不应凭空写入向导单例；只有选择/更新路线才持久化状态。
    state = state or db.get(WizardState, SINGLETON_ID)
    semesters = _semesters(db)
    has_demo = any(semester.is_demo for semester in semesters)
    has_formal = any(not semester.is_demo for semester in semesters)
    route = effective_route(db, state)
    # 已有正式数据后不可反向切到示例；示例-only 数据仍可转正式。
    return {
        "route": route,
        "demo_available": not semesters,
        "demo_school_name": demo_data.load_spec()["school_name"],
        "has_demo_semester": has_demo,
        "has_formal_semester": has_formal,
        "can_reselect": not has_formal,
        "resume_step": (
            state.current_step if state is not None and route == WizardRoute.formal.value else 0
        ),
        "resume_semester_id": (
            state.semester_id
            if state is not None and route == WizardRoute.formal.value
            else None
        ),
    }
