"""Audit trail tables (append-only)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StudentChangeHistory(Base):
    __tablename__ = "student_change_history"
    __table_args__ = (
        CheckConstraint("action IN ('create','update','deactivate','reactivate')", name="valid_action"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(String(15))
    changes: Mapped[dict] = mapped_column(JSONB, default=dict)  # {field: {"old": x, "new": y}}
    reason: Mapped[str] = mapped_column(Text)
    performed_by_teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"))
    performed_by_account_id: Mapped[int] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    totp_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("user_accounts.id", ondelete="SET NULL"), index=True)
    role: Mapped[str | None] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(60))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
