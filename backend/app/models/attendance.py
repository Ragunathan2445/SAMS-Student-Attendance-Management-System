"""Attendance: official records, substitute (temporary) submissions, approvals, corrections."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.people import Student, Teacher
from app.models.school import Period, Section, Subject

ATTENDANCE_STATUSES = ("present", "absent", "leave")
ABSENCE_REASONS = (
    "fever",
    "medical_appointment",
    "family_function",
    "personal",
    "informed_leave",
    "uninformed",
    "other",
)
_REASON_SQL = ",".join(f"'{r}'" for r in ABSENCE_REASONS)


class Attendance(Base, TimestampMixin):
    """Official, period-wise attendance. Exactly one row per student/date/period."""

    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("student_id", "date", "period_id", name="uq_attendance_student_date_period"),
        CheckConstraint("status IN ('present','absent','leave')", name="valid_status"),
        CheckConstraint(f"absence_reason IS NULL OR absence_reason IN ({_REASON_SQL})", name="valid_reason"),
        CheckConstraint("source IN ('regular','substitute','correction')", name="valid_source"),
        Index("ix_attendance_section_date", "section_id", "date"),
        Index("ix_attendance_student_date", "student_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id", ondelete="RESTRICT"))
    date: Mapped[date] = mapped_column(Date)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id", ondelete="RESTRICT"))
    timetable_id: Mapped[int | None] = mapped_column(ForeignKey("timetable.id", ondelete="SET NULL"))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(10))
    absence_reason: Mapped[str | None] = mapped_column(String(30))
    remarks: Mapped[str | None] = mapped_column(String(255))
    marked_by_teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"))
    source: Mapped[str] = mapped_column(String(20), default="regular")
    submission_id: Mapped[int | None] = mapped_column(ForeignKey("attendance_submissions.id", ondelete="SET NULL"))
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student: Mapped[Student] = relationship()
    period: Mapped[Period] = relationship()
    subject: Mapped[Subject | None] = relationship()
    marked_by: Mapped[Teacher] = relationship()


class SubstituteAssignment(Base, TimestampMixin):
    """Authorises a substitute teacher to take one timetable slot on one date.
    Created by the school (seeded for the demo; future management portal)."""

    __tablename__ = "substitute_assignments"
    __table_args__ = (
        UniqueConstraint("date", "timetable_id", name="uq_substitute_slot_date"),
        CheckConstraint("substitute_teacher_id <> regular_teacher_id", name="different_teacher"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    date: Mapped[date] = mapped_column(Date, index=True)
    timetable_id: Mapped[int] = mapped_column(ForeignKey("timetable.id", ondelete="RESTRICT"))
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id", ondelete="RESTRICT"))
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id", ondelete="RESTRICT"))
    regular_teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"))
    substitute_teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"), index=True)
    # Teacher who must approve the temporary attendance (regular teacher by default).
    responsible_teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"), index=True)
    reason: Mapped[str | None] = mapped_column(String(255))
    assigned_by: Mapped[str | None] = mapped_column(String(100))

    section: Mapped[Section] = relationship()
    period: Mapped[Period] = relationship()
    timetable: Mapped["Timetable"] = relationship()  # noqa: F821
    regular_teacher: Mapped[Teacher] = relationship(foreign_keys=[regular_teacher_id])
    substitute_teacher: Mapped[Teacher] = relationship(foreign_keys=[substitute_teacher_id])
    responsible_teacher: Mapped[Teacher] = relationship(foreign_keys=[responsible_teacher_id])


class AttendanceSubmission(Base):
    """Temporary attendance captured by a substitute teacher. Never official until approved."""

    __tablename__ = "attendance_submissions"
    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected')", name="valid_status"),
        # At most one pending and one approved submission per slot/date.
        Index(
            "uq_submission_open_per_slot",
            "section_id",
            "date",
            "period_id",
            unique=True,
            postgresql_where=text("status IN ('pending','approved')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    substitute_assignment_id: Mapped[int] = mapped_column(
        ForeignKey("substitute_assignments.id", ondelete="RESTRICT"), index=True
    )
    substitute_teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"), index=True)
    substitute_teacher_name: Mapped[str] = mapped_column(String(150))
    responsible_teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"), index=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id", ondelete="RESTRICT"))
    class_name: Mapped[str] = mapped_column(String(50))
    section_name: Mapped[str] = mapped_column(String(10))
    date: Mapped[date] = mapped_column(Date)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id", ondelete="RESTRICT"))
    timetable_id: Mapped[int | None] = mapped_column(ForeignKey("timetable.id", ondelete="SET NULL"))
    present_count: Mapped[int] = mapped_column(Integer)
    absent_count: Mapped[int] = mapped_column(Integer)
    leave_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"))
    decided_by_account_id: Mapped[int | None] = mapped_column(ForeignKey("user_accounts.id", ondelete="SET NULL"))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list[AttendanceSubmissionItem]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )
    period: Mapped[Period] = relationship()
    section: Mapped[Section] = relationship()
    responsible_teacher: Mapped[Teacher] = relationship(foreign_keys=[responsible_teacher_id])
    decided_by: Mapped[Teacher | None] = relationship(foreign_keys=[decided_by_teacher_id])


class AttendanceSubmissionItem(Base):
    __tablename__ = "attendance_submission_items"
    __table_args__ = (
        UniqueConstraint("submission_id", "student_id"),
        CheckConstraint("status IN ('present','absent','leave')", name="valid_status"),
        CheckConstraint(f"absence_reason IS NULL OR absence_reason IN ({_REASON_SQL})", name="valid_reason"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("attendance_submissions.id", ondelete="CASCADE"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(10))
    absence_reason: Mapped[str | None] = mapped_column(String(30))
    remarks: Mapped[str | None] = mapped_column(String(255))

    submission: Mapped[AttendanceSubmission] = relationship(back_populates="items")
    student: Mapped[Student] = relationship()


class AttendanceApproval(Base):
    """Immutable audit trail of every approve/reject decision on a submission."""

    __tablename__ = "attendance_approvals"
    __table_args__ = (CheckConstraint("action IN ('approved','rejected')", name="valid_action"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("attendance_submissions.id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(String(10))
    acted_by_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"))
    acted_by_account_id: Mapped[int] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    acted_by_role: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    records_finalized: Mapped[int] = mapped_column(Integer, default=0)
    acted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AttendanceCorrection(Base):
    """History of every change to an official attendance row (manual edits, leave approvals)."""

    __tablename__ = "attendance_corrections"
    __table_args__ = (
        CheckConstraint("trigger IN ('manual','leave_approval')", name="valid_trigger"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("attendance.id", ondelete="RESTRICT"), index=True)
    old_status: Mapped[str] = mapped_column(String(10))
    new_status: Mapped[str] = mapped_column(String(10))
    old_reason: Mapped[str | None] = mapped_column(String(30))
    new_reason: Mapped[str | None] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    trigger: Mapped[str] = mapped_column(String(20), default="manual")
    leave_request_id: Mapped[int | None] = mapped_column(ForeignKey("leave_requests.id", ondelete="SET NULL"))
    corrected_by_teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"))
    corrected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
