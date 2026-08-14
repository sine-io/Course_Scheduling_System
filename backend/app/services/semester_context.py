"""当前学期上下文的领域规则。

``Semester.status`` 描述学期生命周期，``SemesterContext`` 描述单校唯一的工作边界。
两者刻意分开：一个已发布的学期可以因为切换而成为历史数据，但不会因此改变它已经发生过的生命周期。
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.semester import Semester, SemesterContext, SemesterStatus

CONTEXT_ROW_ID = 1


@dataclass(frozen=True, slots=True)
class SemesterContextError(Exception):
    """可由 HTTP/API 层转换为稳定错误响应的领域错误。"""

    code: str
    message: str
    status_code: int = 409

    def __str__(self) -> str:
        return self.message


def _context_row(db: Session, lock: Literal["none", "share", "update"] = "none") -> SemesterContext:
    """读取单例行；锁由调用方事务持有到 commit。"""
    stmt = select(SemesterContext).where(SemesterContext.id == CONTEXT_ROW_ID)
    if lock == "share":
        stmt = stmt.with_for_update(read=True, of=SemesterContext)
    elif lock == "update":
        stmt = stmt.with_for_update(of=SemesterContext)
    row = db.scalar(stmt)
    if row is None:
        # 迁移会预置这一行；Base.metadata.create_all() 的轻量测试环境则按需补齐。
        row = SemesterContext(id=CONTEXT_ROW_ID)
        db.add(row)
        db.flush()
    return row


def read_context(db: Session) -> tuple[SemesterContext, Semester | None]:
    row = _context_row(db)
    semester = db.get(Semester, row.current_semester_id) if row.current_semester_id else None
    return row, semester


def require_writable(
    db: Session,
    semester_id: int,
    *,
    lock: Literal["share", "update"] = "share",
) -> Semester:
    """确认学期存在、未归档且仍是当前上下文，并锁住上下文边界。"""
    row = _context_row(db, lock=lock)
    semester = db.get(Semester, semester_id)
    if semester is None:
        raise SemesterContextError("semester_not_found", "找不到学期", status_code=404)
    if semester.status == SemesterStatus.archived.value:
        raise SemesterContextError(
            "semester_read_only", "已归档学期为只读，不能执行此操作"
        )
    if row.current_semester_id != semester_id:
        raise SemesterContextError(
            "semester_not_current",
            "当前工作学期已切换，历史学期为只读；请刷新后重试",
        )
    return semester


def set_initial_current(db: Session, semester: Semester) -> None:
    """首个学期自动成为当前；已有当前学期时新学期保持可查询但只读。"""
    row = _context_row(db, lock="update")
    if row.current_semester_id is None:
        row.current_semester_id = semester.id
        row.revision += 1


def switch_current(db: Session, semester_id: int, expected_revision: int) -> SemesterContext:
    """以乐观版本号切换当前学期，避免并发客户端静默覆盖彼此选择。"""
    row = _context_row(db, lock="update")
    if row.revision != expected_revision:
        raise SemesterContextError(
            "semester_context_changed",
            "当前学期已被其他操作切换，请刷新当前上下文后重试",
        )
    semester = db.get(Semester, semester_id)
    if semester is None:
        raise SemesterContextError("semester_not_found", "找不到学期", status_code=404)
    if semester.status == SemesterStatus.archived.value:
        raise SemesterContextError(
            "semester_read_only", "已归档学期为只读，不能设为当前学期"
        )
    if row.current_semester_id != semester.id:
        row.current_semester_id = semester.id
        row.revision += 1
        db.flush()
    return row


def clear_current_if_matches(db: Session, semester_id: int) -> None:
    """归档或删除当前学期时清空指针，避免上下文指向不可写数据。"""
    row = _context_row(db, lock="update")
    if row.current_semester_id == semester_id:
        row.current_semester_id = None
        row.revision += 1
