"""Leave requests submitted by parents and decided by authorised teachers."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.people import Parent, Student, StudentDocument, Teacher

LEAVE_REASONS = ("fever", "medical_appointment", "family_function", "personal", "other")


class LeaveRequest(Base, TimestampMixin):
    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="valid_range"),
        CheckConstraint("status IN ('pending','approved','rejected')", name="valid_status"),
        CheckConstraint(
            "reason IN ('fever','medical_appointment','family_function','personal','other')", name="valid_reason"
        ),
        Index("ix_leave_student_dates", "student_id", "start_date", "end_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    parent_id: Mapped[int] = mapped_column(ForeignKey("parents.id", ondelete="RESTRICT"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("student_documents.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(10), default="pending")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"))
    teacher_remarks: Mapped[str | None] = mapped_column(Text)

    student: Mapped[Student] = relationship()
    parent: Mapped[Parent] = relationship()
    document: Mapped[StudentDocument | None] = relationship()
    decided_by: Mapped[Teacher | None] = relationship()


class LeaveApproval(Base):
    __tablename__ = "leave_approvals"
    __table_args__ = (CheckConstraint("action IN ('approved','rejected')", name="valid_action"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    leave_request_id: Mapped[int] = mapped_column(ForeignKey("leave_requests.id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(String(10))
    acted_by_teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"))
    remarks: Mapped[str | None] = mapped_column(Text)
    attendance_rows_updated: Mapped[int] = mapped_column(default=0)
    acted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
