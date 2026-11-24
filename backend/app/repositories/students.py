"""Reusable student / parent queries shared by several services."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Parent, ParentStudent, Section, Student


def primary_parent(db: Session, student_id: int) -> Parent | None:
    return db.scalar(
        select(Parent).join(ParentStudent).where(ParentStudent.student_id == student_id)
        .order_by(ParentStudent.is_primary.desc()).limit(1)
    )


def active_in_section(db: Session, section_id: int, on_date: date | None = None) -> list[Student]:
    """Active students of a section, optionally only those admitted on/before ``on_date``."""
    students = db.scalars(
        select(Student).where(Student.section_id == section_id, Student.status == "active")
    ).all()
    if on_date:
        students = [s for s in students if not s.admission_date or s.admission_date <= on_date]
    return sorted(students, key=lambda s: s.roll_number)


def with_section(db: Session, student_id: int) -> Student | None:
    return db.scalar(
        select(Student).options(joinedload(Student.section).joinedload(Section.school_class)).where(Student.id == student_id)
    )
