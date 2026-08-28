"""标准化教师安排导入的批次、逐行溯源与非排课来源记录。"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class TeacherArrangementImportBatch(Base):
    __tablename__ = "teacher_arrangement_import_batches"
    __table_args__ = (
        UniqueConstraint(
            "semester_id",
            "fingerprint",
            name="uq_teacher_arrangement_batches_fingerprint",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), index=True
    )
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    workbook_sha256: Mapped[str] = mapped_column(String(64), index=True)
    template_version: Mapped[str] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(255))
    summary: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    records: Mapped[list["TeacherArrangementImportRecord"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", lazy="selectin"
    )


class TeacherArrangementImportRecord(Base):
    __tablename__ = "teacher_arrangement_import_records"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "entity_type",
            "source_key",
            name="uq_teacher_arrangement_records_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("teacher_arrangement_import_batches.id", ondelete="CASCADE"),
        index=True,
    )
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(32))
    source_key: Mapped[str] = mapped_column(String(160))
    sheet_name: Mapped[str] = mapped_column(String(31))
    row_number: Mapped[int] = mapped_column(Integer)
    target_id: Mapped[int] = mapped_column(Integer)
    applied_values: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    raw_values: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    batch: Mapped[TeacherArrangementImportBatch] = relationship(back_populates="records")


class TeacherArrangementSourceRecord(Base):
    __tablename__ = "teacher_arrangement_source_records"
    __table_args__ = (
        UniqueConstraint(
            "semester_id",
            "record_code",
            name="uq_teacher_arrangement_source_record_code",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), index=True
    )
    record_code: Mapped[str] = mapped_column(String(96))
    category: Mapped[str] = mapped_column(String(64))
    task_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    content: Mapped[str] = mapped_column(String(1000))
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
