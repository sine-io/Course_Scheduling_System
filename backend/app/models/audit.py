"""操作轨迹 model(architecture.md §2.2 audit_log)。

谁在何时改了什么。排课发布、调课与代课指派等关键变更必记;账号被删除时保留记录
(user_id 设为 NULL),避免轨迹消失。
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_at_id", "created_at", "id"),
        Index("ix_audit_logs_action_created_at_id", "action", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    operation_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, unique=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    username: Mapped[str] = mapped_column(String(64), default="")  # 快照,账号删除后仍可识别
    actor_roles: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    action: Mapped[str] = mapped_column(String(64), index=True)    # 如 publish_timetable
    target_type: Mapped[str] = mapped_column(String(32), default="")
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    semester_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_version: Mapped[str] = mapped_column(String(128), default="", server_default="")
    result: Mapped[str] = mapped_column(String(20), default="", server_default="")
    reason: Mapped[str] = mapped_column(String(64), default="", server_default="")
    detail: Mapped[str] = mapped_column(String(500), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
