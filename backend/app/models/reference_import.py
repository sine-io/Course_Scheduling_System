"""参考文件导入的来源快照与规则。

参考文件不是系统的主数据格式，因此单独保存其来源、哈希和归一化规则，
让导入可预览、可重复执行，也让人工调整和后续审计有明确边界。
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ReferenceImportBatch(Base):
    __tablename__ = "reference_import_batches"
    __table_args__ = (
        UniqueConstraint("semester_id", "fingerprint", name="uq_reference_import_batch_fingerprint"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), index=True
    )
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    adapter_version: Mapped[str] = mapped_column(String(32))
    word_filename: Mapped[str] = mapped_column(String(255))
    xlsx_filename: Mapped[str] = mapped_column(String(255))
    word_sha256: Mapped[str] = mapped_column(String(64))
    xlsx_sha256: Mapped[str] = mapped_column(String(64))
    decisions: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    summary: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReferenceSchedulingRule(Base):
    __tablename__ = "reference_scheduling_rules"
    __table_args__ = (
        UniqueConstraint("semester_id", "source_key", name="uq_reference_rule_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[str] = mapped_column(String(32))
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_type: Mapped[str] = mapped_column(String(20))
    source_key: Mapped[str] = mapped_column(String(160))
    source_text: Mapped[str] = mapped_column(String(500))
    enforced: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
