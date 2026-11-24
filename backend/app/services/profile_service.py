from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AcademicYear,
    Parent,
    ParentStudent,
    Section,
    Student,
    StudentAcademicRecord,
    Teacher,
    TeacherAssignment,
    TeacherSubjectAssignment,
    Timetable,
)
from app.utils.files import student_photo_url, teacher_photo_url
from app.services import teacher_scope

ASSIGNMENT_LABELS = {
    "class_teacher": "Class Teacher",
    "co_class_teacher": "Co-Class Teacher",
    "coordinator": "Coordinator",
    "substitute_pool": "Substitute Teacher Pool",
}


def student_summary(s: Student) -> dict:
    return {
        "id": s.id, "full_name": s.full_name, "roll_number": s.roll_number,
        "class_label": f"{s.section.school_class.name} – {s.section.name}",
        "photo_url": student_photo_url(s), "status": s.status,
    }


def parent_students(db: Session, parent: Parent) -> list[dict]:
    rows = db.scalars(
        select(Student).join(ParentStudent).options(joinedload(Student.section).joinedload(Section.school_class))
        .where(ParentStudent.parent_id == parent.id).order_by(Student.full_name)
    ).unique().all()
    return [student_summary(s) for s in rows]


def student_profile(db: Session, s: Student) -> dict:
    section = db.scalar(select(Section).options(joinedload(Section.school_class)).where(Section.id == s.section_id))
    ay = db.get(AcademicYear, s.academic_year_id)
    class_teacher = db.scalar(
        select(Teacher).join(TeacherAssignment, TeacherAssignment.teacher_id == Teacher.id).where(
            TeacherAssignment.section_id == s.section_id, TeacherAssignment.academic_year_id == ay.id,
            TeacherAssignment.assignment_type == "class_teacher")
    )
    guardians = db.execute(
        select(Parent, ParentStudent).join(ParentStudent, ParentStudent.parent_id == Parent.id)
        .where(ParentStudent.student_id == s.id).order_by(ParentStudent.is_primary.desc())
    ).all()
    return {
        "id": s.id,
        "photo_url": student_photo_url(s),
        "full_name": s.full_name,
        "roll_number": s.roll_number,
        "admission_number": s.admission_number,
        "date_of_birth": s.date_of_birth.isoformat(),
        "gender": s.gender,
        "blood_group": s.blood_group,
        "class_name": section.school_class.name,
        "section_name": section.name,
        "room": section.room,
        "academic_year": ay.name,
        "address": s.address,
        "contact_number": s.contact_number,
        "uses_school_bus": s.uses_school_bus,
        "admission_date": s.admission_date.isoformat() if s.admission_date else None,
        "status": s.status,
        "class_teacher": class_teacher.full_name if class_teacher else None,
        "guardians": [
            {"name": p.full_name, "relation": p.relation_type, "mobile": p.mobile, "email": p.email,
             "address": p.address, "occupation": p.occupation, "is_primary": link.is_primary}
            for p, link in guardians
        ],
    }


def academic_records(db: Session, student_id: int) -> list[dict]:
    rows = db.scalars(select(StudentAcademicRecord).where(StudentAcademicRecord.student_id == student_id)
                      .order_by(StudentAcademicRecord.academic_year_name.desc())).all()
    return [{"academic_year": r.academic_year_name, "class_name": r.class_name, "section_name": r.section_name,
             "overall_grade": r.overall_grade, "percentage": str(r.percentage),
             "attendance_percentage": str(r.attendance_percentage), "result": r.result, "remarks": r.remarks}
            for r in rows]


def teacher_profile(db: Session, teacher: Teacher, ay: AcademicYear) -> dict:
    subjects = db.scalars(
        select(TeacherSubjectAssignment).options(joinedload(TeacherSubjectAssignment.subject))
        .where(TeacherSubjectAssignment.teacher_id == teacher.id, TeacherSubjectAssignment.academic_year_id == ay.id)
    ).all()
    responsibilities = db.scalars(
        select(TeacherAssignment).options(joinedload(TeacherAssignment.section).joinedload(Section.school_class))
        .where(TeacherAssignment.teacher_id == teacher.id, TeacherAssignment.academic_year_id == ay.id)
    ).all()
    ct_ids = teacher_scope.class_teacher_section_ids(db, teacher, ay)
    sections = teacher_scope.sections_payload(db, teacher_scope.authorised_section_ids(db, teacher, ay), ct_ids)
    weekly_periods = db.scalar(
        select(func.count(Timetable.id)).where(
            Timetable.teacher_id == teacher.id, Timetable.academic_year_id == ay.id)
    )
    return {
        "id": teacher.id,
        "photo_url": teacher_photo_url(teacher),
        "full_name": teacher.full_name,
        "employee_code": teacher.employee_code,
        "email": teacher.email,
        "mobile": teacher.mobile,
        "designation": teacher.designation,
        "qualification": teacher.qualification,
        "date_of_joining": teacher.date_of_joining.isoformat() if teacher.date_of_joining else None,
        "subjects": sorted({a.subject.name for a in subjects}),
        "classes": sorted({s["class_name"] for s in sections}),
        "sections": sections,
        "weekly_periods": weekly_periods,
        "responsibilities": [
            {"type": r.assignment_type, "label": ASSIGNMENT_LABELS.get(r.assignment_type, r.assignment_type),
             "section": f"{r.section.school_class.name} – {r.section.name}" if r.section else None,
             "description": r.description}
            for r in responsibilities
        ],
        "academic_year": ay.name,
    }


def weekly_timetable(db: Session, teacher: Teacher, ay: AcademicYear) -> list[dict]:
    rows = db.scalars(
        select(Timetable).options(joinedload(Timetable.period), joinedload(Timetable.subject),
                                  joinedload(Timetable.section).joinedload(Section.school_class))
        .where(Timetable.teacher_id == teacher.id, Timetable.academic_year_id == ay.id)
    ).unique().all()
    return sorted(
        [{"day_of_week": r.day_of_week, "period_number": r.period.period_number,
          "start_time": r.period.start_time.strftime("%H:%M"), "subject": r.subject.name,
          "label": f"{r.section.school_class.name} – {r.section.name}"} for r in rows],
        key=lambda x: (x["day_of_week"], x["period_number"]),
    )
