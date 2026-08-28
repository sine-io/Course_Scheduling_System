"""版本化排课规则 model。

同一学期只有一个规则集；编辑发生在唯一草稿修订上，激活后的修订不再原地修改。
规则以 JSON 保存模板参数，但只有受支持模板可以激活并进入求解器。
"""

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class RuleRevisionStatus(enum.StrEnum):
    draft = "draft"
    active = "active"
    superseded = "superseded"


class SchedulingRuleSet(Base):
    __tablename__ = "scheduling_rule_sets"
    __table_args__ = (UniqueConstraint("semester_id", name="uq_scheduling_rule_sets_semester"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), index=True
    )
    # 以修订号而非循环外键保存指针；(rule_set_id, revision_no) 在修订表内唯一。
    active_revision_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    revisions: Mapped[list["SchedulingRuleRevision"]] = relationship(
        back_populates="rule_set", cascade="all, delete-orphan"
    )


class SchedulingRuleRevision(Base):
    __tablename__ = "scheduling_rule_revisions"
    __table_args__ = (
        UniqueConstraint("rule_set_id", "revision_no", name="uq_scheduling_rule_revisions_number"),
        CheckConstraint(
            "status IN ('draft', 'active', 'superseded')",
            name="valid_scheduling_rule_revision_status",
        ),
        Index(
            "uq_scheduling_rule_revisions_one_draft",
            "rule_set_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
            sqlite_where=text("status = 'draft'"),
        ),
        Index(
            "uq_scheduling_rule_revisions_one_active",
            "rule_set_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_set_id: Mapped[int] = mapped_column(
        ForeignKey("scheduling_rule_sets.id", ondelete="CASCADE"), index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(20), default=RuleRevisionStatus.draft.value, index=True
    )
    note: Mapped[str] = mapped_column(String(240), default="")
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_name: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rule_set: Mapped[SchedulingRuleSet] = relationship(back_populates="revisions")
    rules: Mapped[list["SchedulingRule"]] = relationship(
        back_populates="revision", cascade="all, delete-orphan"
    )


class SchedulingRule(Base):
    __tablename__ = "scheduling_rules"
    __table_args__ = (
        UniqueConstraint("revision_id", "rule_key", name="uq_scheduling_rules_revision_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    revision_id: Mapped[int] = mapped_column(
        ForeignKey("scheduling_rule_revisions.id", ondelete="CASCADE"), index=True
    )
    # 跨修订保持稳定，用于在新草稿中定位“同一条业务规则”。
    rule_key: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(100))
    template: Mapped[str] = mapped_column(String(40))
    target: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    timing: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    operator: Mapped[str] = mapped_column(String(24))
    strength: Mapped[str] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(12), default="medium")
    source_kind: Mapped[str] = mapped_column(String(20), default="custom")
    source_text: Mapped[str] = mapped_column(String(500), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    compiler_version: Mapped[str] = mapped_column(String(24), default="rules-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    revision: Mapped[SchedulingRuleRevision] = relationship(back_populates="rules")
