"""Teacher authorisation scopes – which sections/slots a teacher may act on.

No class is hard-coded to a teacher: scopes come from the timetable and the
teacher assignment tables of the current academic year.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import Forbidden, NotFound
from app.models import (
    AcademicYear,
    Section,
    Student,
    Teacher,
    TeacherAssignment,
    TeacherClassAssignment,
    Timetable,
)

CLASS_TEACHER_TYPES = ("class_teacher", "co_class_teacher")


def taught_section_ids(db: Session, teacher: Teacher, ay: AcademicYear) -> set[int]:
    from_timetable = db.scalars(
        select(Timetable.section_id).where(Timetable.teacher_id == teacher.id, Timetable.academic_year_id == ay.id)
    ).all()
    from_assignments = db.scalars(
        select(TeacherClassAssignment.section_id).where(
            TeacherClassAssignment.teacher_id == teacher.id, TeacherClassAssignment.academic_year_id == ay.id
        )
    ).all()
    return set(from_timetable) | set(from_assignments)


def class_teacher_section_ids(db: Session, teacher: Teacher, ay: AcademicYear) -> set[int]:
    return set(
        db.scalars(
            select(TeacherAssignment.section_id).where(
                TeacherAssignment.teacher_id == teacher.id,
                TeacherAssignment.academic_year_id == ay.id,
                TeacherAssignment.assignment_type.in_(CLASS_TEACHER_TYPES),
                TeacherAssignment.section_id.is_not(None),
            )
        ).all()
    )


def authorised_section_ids(db: Session, teacher: Teacher, ay: AcademicYear) -> set[int]:
    return taught_section_ids(db, teacher, ay) | class_teacher_section_ids(db, teacher, ay)


def sections_payload(db: Session, section_ids: set[int], class_teacher_ids: set[int] | None = None) -> list[dict]:
    if not section_ids:
        return []
    sections = db.scalars(
        select(Section).options(joinedload(Section.school_class)).where(Section.id.in_(section_ids))
    ).all()
    sections.sort(key=lambda s: (s.school_class.grade_level, s.name))
    ct = class_teacher_ids or set()
    return [
        {
            "id": s.id,
            "class_id": s.class_id,
            "class_name": s.school_class.name,
            "section_name": s.name,
            "label": f"{s.school_class.name} – {s.name}",
            "is_class_teacher": s.id in ct,
        }
        for s in sections
    ]


def require_section(db: Session, teacher: Teacher, ay: AcademicYear, section_id: int, *, class_teacher: bool = False) -> Section:
    allowed = class_teacher_section_ids(db, teacher, ay) if class_teacher else authorised_section_ids(db, teacher, ay)
    if section_id not in allowed:
        raise Forbidden(
            "Only the class teacher of this section can perform this action."
            if class_teacher
            else "You are not assigned to this class/section."
        )
    section = db.get(Section, section_id)
    if section is None:
        raise NotFound("Section not found.")
    return section


def require_student(db: Session, teacher: Teacher, ay: AcademicYear, student_id: int, *, class_teacher: bool = False) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise NotFound("Student not found.")
    require_section(db, teacher, ay, student.section_id, class_teacher=class_teacher)
    return student


def teacher_slots_for_date(db: Session, teacher: Teacher, ay: AcademicYear, day: date) -> list[Timetable]:
    return db.scalars(
        select(Timetable)
        .options(
            joinedload(Timetable.period),
            joinedload(Timetable.subject),
            joinedload(Timetable.section).joinedload(Section.school_class),
        )
        .where(
            Timetable.teacher_id == teacher.id,
            Timetable.academic_year_id == ay.id,
            Timetable.day_of_week == day.isoweekday(),
        )
    ).all()


def can_view_student_photo(db: Session, teacher: Teacher, ay: AcademicYear, student: Student) -> bool:
    if student.section_id in authorised_section_ids(db, teacher, ay):
        return True
    # Substitute teachers may see photos of classes they are assigned to cover.
    from app.models import SubstituteAssignment

    return (
        db.scalar(
            select(SubstituteAssignment.id).where(
                SubstituteAssignment.substitute_teacher_id == teacher.id,
                SubstituteAssignment.section_id == student.section_id,
            ).limit(1)
        )
        is not None
    )
