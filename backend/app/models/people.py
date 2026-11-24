"""Students, parents and teachers."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.school import AcademicYear, Section


class Parent(Base, TimestampMixin):
    __tablename__ = "parents"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), index=True)
    user_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), unique=True
    )
    full_name: Mapped[str] = mapped_column(String(150))
    relation_type: Mapped[str] = mapped_column(String(30), default="Guardian")  # Father / Mother / Guardian
    mobile: Mapped[str] = mapped_column(String(15), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)  # always stored lowercase
    address: Mapped[str | None] = mapped_column(Text)
    occupation: Mapped[str | None] = mapped_column(String(100))

    student_links: Mapped[list[ParentStudent]] = relationship(back_populates="parent")


class Student(Base, TimestampMixin):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("school_id", "academic_year_id", "roll_number", name="uq_student_roll"),
        CheckConstraint("status IN ('active','inactive')", name="valid_status"),
        CheckConstraint("gender IN ('Male','Female','Other')", name="valid_gender"),
        Index("ix_students_section_status", "section_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), index=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id", ondelete="RESTRICT"))
    roll_number: Mapped[str] = mapped_column(String(20))
    admission_number: Mapped[str] = mapped_column(String(30), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    date_of_birth: Mapped[date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(10))
    blood_group: Mapped[str | None] = mapped_column(String(5))
    address: Mapped[str | None] = mapped_column(Text)
    contact_number: Mapped[str | None] = mapped_column(String(15))
    photo_path: Mapped[str | None] = mapped_column(String(255))  # relative path in upload dir
    uses_school_bus: Mapped[bool] = mapped_column(Boolean, default=False)
    admission_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="active")
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivation_reason: Mapped[str | None] = mapped_column(Text)
    deactivated_by_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id", ondelete="SET NULL"))

    section: Mapped[Section] = relationship()
    academic_year: Mapped[AcademicYear] = relationship()
    parent_links: Mapped[list[ParentStudent]] = relationship(back_populates="student")


class ParentStudent(Base):
    __tablename__ = "parent_students"

    parent_id: Mapped[int] = mapped_column(ForeignKey("parents.id", ondelete="CASCADE"), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), primary_key=True, index=True)
    relationship_label: Mapped[str] = mapped_column(String(30), default="Parent")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    parent: Mapped[Parent] = relationship(back_populates="student_links")
    student: Mapped[Student] = relationship(back_populates="parent_links")


class StudentDocument(Base):
    __tablename__ = "student_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"), index=True)
    doc_type: Mapped[str] = mapped_column(String(40))  # leave_support / photo / certificate
    file_path: Mapped[str] = mapped_column(String(255))
    original_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_by_account_id: Mapped[int | None] = mapped_column(ForeignKey("user_accounts.id", ondelete="SET NULL"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentAcademicRecord(Base, TimestampMixin):
    """Previous academic year results shown in the parent history section."""

    __tablename__ = "student_academic_records"
    __table_args__ = (UniqueConstraint("student_id", "academic_year_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"), index=True)
    academic_year_name: Mapped[str] = mapped_column(String(20))
    class_name: Mapped[str] = mapped_column(String(50))
    section_name: Mapped[str] = mapped_column(String(10))
    overall_grade: Mapped[str] = mapped_column(String(5))
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    attendance_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    result: Mapped[str] = mapped_column(String(30))
    remarks: Mapped[str | None] = mapped_column(Text)


class Teacher(Base, TimestampMixin):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), index=True)
    user_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), unique=True
    )
    employee_code: Mapped[str] = mapped_column(String(20), unique=True)  # Teacher ID e.g. T1001
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    mobile: Mapped[str] = mapped_column(String(15))
    designation: Mapped[str] = mapped_column(String(100))
    qualification: Mapped[str | None] = mapped_column(String(150))
    date_of_joining: Mapped[date | None] = mapped_column(Date)
    photo_path: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TeacherAssignment(Base, TimestampMixin):
    """Responsibilities such as class teacher of a section."""

    __tablename__ = "teacher_assignments"
    __table_args__ = (
        CheckConstraint(
            "assignment_type IN ('class_teacher','co_class_teacher','coordinator','substitute_pool')",
            name="valid_type",
        ),
        # Only one class teacher per section per academic year.
        Index(
            "uq_one_class_teacher_per_section",
            "academic_year_id",
            "section_id",
            unique=True,
            postgresql_where=text("assignment_type = 'class_teacher'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"), index=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    assignment_type: Mapped[str] = mapped_column(String(30))
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id", ondelete="RESTRICT"))
    description: Mapped[str | None] = mapped_column(String(255))

    section: Mapped[Section | None] = relationship()


class TeacherClassAssignment(Base, TimestampMixin):
    """Sections a teacher is authorised to teach in an academic year."""

    __tablename__ = "teacher_class_assignments"
    __table_args__ = (UniqueConstraint("teacher_id", "academic_year_id", "section_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"), index=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id", ondelete="RESTRICT"))

    section: Mapped[Section] = relationship()


class TeacherSubjectAssignment(Base, TimestampMixin):
    __tablename__ = "teacher_subject_assignments"
    __table_args__ = (UniqueConstraint("teacher_id", "academic_year_id", "subject_id", "section_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"), index=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"))
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id", ondelete="RESTRICT"))

    subject: Mapped["Subject"] = relationship()  # noqa: F821
    section: Mapped[Section | None] = relationship()
