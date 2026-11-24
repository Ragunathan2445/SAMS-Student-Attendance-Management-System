"""School and academic structure: schools, academic years, classes, sections, subjects,
periods, timetable and the school working calendar."""
from __future__ import annotations

from datetime import date, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

DAY_TYPES = (
    "working",
    "school_holiday",
    "festival_holiday",
    "management_holiday",
    "weekly_holiday",
)


class School(Base, TimestampMixin):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    tagline: Mapped[str | None] = mapped_column(String(255))
    about: Mapped[str | None] = mapped_column(Text)
    highlights: Mapped[str | None] = mapped_column(Text)  # newline separated
    address: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(255))
    established_year: Mapped[int | None] = mapped_column(Integer)
    affiliation: Mapped[str | None] = mapped_column(String(255))
    principal_name: Mapped[str | None] = mapped_column(String(150))


class AcademicYear(Base, TimestampMixin):
    __tablename__ = "academic_years"
    __table_args__ = (
        UniqueConstraint("school_id", "name"),
        CheckConstraint("end_date > start_date", name="valid_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(20))  # e.g. 2026-27
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    # Default rule for Saturdays when the calendar has no explicit entry.
    saturday_is_working: Mapped[bool] = mapped_column(Boolean, default=True)


class SchoolClass(Base, TimestampMixin):
    __tablename__ = "classes"
    __table_args__ = (UniqueConstraint("school_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(50))  # e.g. Grade 6
    grade_level: Mapped[int] = mapped_column(Integer)

    sections: Mapped[list[Section]] = relationship(back_populates="school_class", order_by="Section.name")


class Section(Base, TimestampMixin):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("class_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(10))
    room: Mapped[str | None] = mapped_column(String(30))

    school_class: Mapped[SchoolClass] = relationship(back_populates="sections")

    @property
    def label(self) -> str:
        return f"{self.school_class.name} – {self.name}"


class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("school_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))


class Period(Base, TimestampMixin):
    __tablename__ = "periods"
    __table_args__ = (
        UniqueConstraint("school_id", "period_number"),
        CheckConstraint("end_time > start_time", name="valid_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), index=True)
    period_number: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class Timetable(Base, TimestampMixin):
    """One row = one teaching slot (section, weekday, period) for an academic year."""

    __tablename__ = "timetable"
    __table_args__ = (
        UniqueConstraint("academic_year_id", "section_id", "day_of_week", "period_id", name="uq_timetable_slot"),
        UniqueConstraint(
            "academic_year_id", "teacher_id", "day_of_week", "period_id", name="uq_timetable_teacher_slot"
        ),
        CheckConstraint("day_of_week BETWEEN 1 AND 7", name="valid_dow"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"), index=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id", ondelete="RESTRICT"), index=True)
    day_of_week: Mapped[int] = mapped_column(Integer)  # ISO: 1=Monday … 7=Sunday
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id", ondelete="RESTRICT"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"), index=True)

    section: Mapped[Section] = relationship()
    period: Mapped[Period] = relationship()
    subject: Mapped[Subject] = relationship()
    teacher: Mapped["Teacher"] = relationship()  # noqa: F821


class SchoolCalendar(Base, TimestampMixin):
    """Explicit calendar entries. Dates without an entry fall back to the weekday rules
    of the academic year (Sunday = weekly holiday, Saturday = configurable)."""

    __tablename__ = "school_calendar"
    __table_args__ = (
        UniqueConstraint("academic_year_id", "date"),
        CheckConstraint(
            "day_type IN ('working','school_holiday','festival_holiday','management_holiday','weekly_holiday')",
            name="valid_day_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    day_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str | None] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
