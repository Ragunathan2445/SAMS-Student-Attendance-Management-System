"""Official attendance marking by the timetabled teacher."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.models import (
    AcademicYear,
    Attendance,
    AttendanceCorrection,
    AttendanceSubmission,
    LeaveRequest,
    Period,
    Section,
    Student,
    SubstituteAssignment,
    Teacher,
    Timetable,
)
from app.repositories import students as student_repo
from app.utils.files import student_photo_url
from app.services import audit_service, teacher_scope
from app.services.calendar_service import get_day
from app.utils.timeutils import today_local

BACKDATE_LIMIT_DAYS = 7


# --------------------------------------------------------------------------- helpers
def validate_marking_date(db: Session, ay: AcademicYear, day: date) -> None:
    today = today_local()
    if day > today:
        raise AppError("Attendance cannot be marked for a future date.", code="future_date")
    if day < today - timedelta(days=BACKDATE_LIMIT_DAYS):
        raise AppError(f"Attendance can only be marked for the last {BACKDATE_LIMIT_DAYS} days.", code="too_old")
    if not (ay.start_date <= day <= ay.end_date):
        raise AppError("Date is outside the current academic year.", code="outside_year")
    info = get_day(db, ay, day)
    if not info.is_working:
        label = info.title or info.day_type.replace("_", " ").title()
        raise AppError(f"{day.strftime('%d %b %Y')} is not a working day ({label}).", code="holiday")


def get_slot(db: Session, ay: AcademicYear, section_id: int, day: date, period_id: int) -> Timetable:
    slot = db.scalar(
        select(Timetable)
        .options(joinedload(Timetable.period), joinedload(Timetable.subject),
                 joinedload(Timetable.section).joinedload(Section.school_class), joinedload(Timetable.teacher))
        .where(
            Timetable.academic_year_id == ay.id,
            Timetable.section_id == section_id,
            Timetable.day_of_week == day.isoweekday(),
            Timetable.period_id == period_id,
        )
    )
    if slot is None:
        raise AppError("This period is not scheduled for the selected class on that day.", code="slot_not_scheduled")
    return slot


def section_students(db: Session, section_id: int, day: date) -> list[Student]:
    return student_repo.active_in_section(db, section_id, day)


def leave_map(db: Session, student_ids: list[int], day: date) -> dict[int, str]:
    """student_id -> 'approved' | 'pending' for leave covering ``day``."""
    result: dict[int, str] = {}
    if not student_ids:
        return result
    for lv in db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.student_id.in_(student_ids),
            LeaveRequest.status.in_(("approved", "pending")),
            LeaveRequest.start_date <= day,
            LeaveRequest.end_date >= day,
        )
    ):
        if result.get(lv.student_id) != "approved":
            result[lv.student_id] = lv.status
    return result


def student_row(student: Student, leave_status: str | None, existing: Attendance | None = None) -> dict:
    return {
        "student_id": student.id,
        "full_name": student.full_name,
        "roll_number": student.roll_number,
        "photo_url": student_photo_url(student),
        "leave_status": leave_status,
        "suggested_status": "leave" if leave_status == "approved" else "present",
        "attendance_id": existing.id if existing else None,
        "status": existing.status if existing else None,
        "absence_reason": existing.absence_reason if existing else None,
        "remarks": existing.remarks if existing else None,
    }


def validate_records(records: list, students: list[Student], leaves: dict[int, str]) -> None:
    expected = {s.id for s in students}
    submitted = [r.student_id for r in records]
    if len(submitted) != len(set(submitted)):
        raise AppError("A student appears more than once in the submission.", code="duplicate_student")
    if set(submitted) != expected:
        raise AppError("Attendance must be submitted for every student in the class (and only them).", code="student_mismatch")
    for r in records:
        if r.status == "leave" and leaves.get(r.student_id) != "approved":
            raise AppError("'Leave' can only be marked for students with an approved leave request.", code="leave_not_approved")
        if r.status != "absent" and r.absence_reason:
            raise AppError("An absence reason can only be given for absent students.", code="reason_not_allowed")


def slot_label(slot: Timetable) -> dict:
    return {
        "timetable_id": slot.id,
        "section_id": slot.section_id,
        "class_name": slot.section.school_class.name,
        "section_name": slot.section.name,
        "label": f"{slot.section.school_class.name} – {slot.section.name}",
        "period_id": slot.period_id,
        "period_number": slot.period.period_number,
        "start_time": slot.period.start_time.strftime("%H:%M"),
        "end_time": slot.period.end_time.strftime("%H:%M"),
        "subject": slot.subject.name,
    }


# --------------------------------------------------------------------------- API logic
def slots_for_date(db: Session, teacher: Teacher, ay: AcademicYear, day: date) -> dict:
    info = get_day(db, ay, day)
    result = {"date": day.isoformat(), "is_working": info.is_working, "day_type": info.day_type,
              "title": info.title, "weekday": day.strftime("%A"), "slots": []}
    if not info.is_working:
        return result
    for slot in sorted(teacher_scope.teacher_slots_for_date(db, teacher, ay, day), key=lambda s: s.period.period_number):
        marked = db.scalar(
            select(func.count(Attendance.id)).where(
                Attendance.section_id == slot.section_id, Attendance.date == day, Attendance.period_id == slot.period_id
            )
        )
        sub = db.scalar(
            select(SubstituteAssignment).options(joinedload(SubstituteAssignment.substitute_teacher))
            .where(SubstituteAssignment.timetable_id == slot.id, SubstituteAssignment.date == day)
        )
        result["slots"].append({
            **slot_label(slot),
            "marked_count": marked,
            "is_marked": marked > 0,
            "substitute_teacher": sub.substitute_teacher.full_name if sub else None,
        })
    return result


def get_sheet(db: Session, teacher: Teacher, ay: AcademicYear, day: date, section_id: int, period_id: int) -> dict:
    validate_marking_date(db, ay, day)
    slot = get_slot(db, ay, section_id, day, period_id)
    if slot.teacher_id != teacher.id:
        raise Forbidden(f"Period {slot.period.period_number} of this class on {day.strftime('%A')} is not assigned to you.")
    students = section_students(db, section_id, day)
    leaves = leave_map(db, [s.id for s in students], day)
    existing = {
        a.student_id: a
        for a in db.scalars(
            select(Attendance).where(Attendance.section_id == section_id, Attendance.date == day, Attendance.period_id == period_id)
        )
    }
    pending_sub = db.scalar(
        select(AttendanceSubmission.id).where(
            AttendanceSubmission.section_id == section_id, AttendanceSubmission.date == day,
            AttendanceSubmission.period_id == period_id, AttendanceSubmission.status == "pending",
        )
    )
    return {
        "date": day.isoformat(),
        "slot": slot_label(slot),
        "already_submitted": bool(existing),
        "pending_substitute_submission_id": pending_sub,
        "students": [student_row(s, leaves.get(s.id), existing.get(s.id)) for s in students],
    }


def submit(db: Session, teacher: Teacher, account_id: int, ay: AcademicYear, payload, ip: str | None) -> dict:
    day = payload.date
    validate_marking_date(db, ay, day)
    slot = get_slot(db, ay, payload.section_id, day, payload.period_id)
    if slot.teacher_id != teacher.id:
        raise Forbidden("You are not the timetabled teacher for this period.")
    existing = db.scalar(
        select(func.count(Attendance.id)).where(
            Attendance.section_id == payload.section_id, Attendance.date == day, Attendance.period_id == payload.period_id
        )
    )
    if existing:
        raise Conflict("Attendance for this period has already been submitted. Use correction to change a record.")

    students = section_students(db, payload.section_id, day)
    leaves = leave_map(db, [s.id for s in students], day)
    validate_records(payload.records, students, leaves)

    counts = {"present": 0, "absent": 0, "leave": 0}
    try:
        for r in payload.records:
            counts[r.status] += 1
            db.add(Attendance(
                student_id=r.student_id, section_id=payload.section_id, date=day, period_id=payload.period_id,
                timetable_id=slot.id, subject_id=slot.subject_id, status=r.status,
                absence_reason=(r.absence_reason or "uninformed") if r.status == "absent" else None,
                remarks=r.remarks, marked_by_teacher_id=teacher.id, source="regular",
            ))
        audit_service.record(
            db, account_id=account_id, role="teacher", action="attendance.submitted",
            entity_type="timetable", entity_id=slot.id,
            details={"date": day, "section_id": payload.section_id, "period": slot.period.period_number, **counts}, ip=ip,
        )
        db.commit()  # single transaction for the whole class
    except IntegrityError:
        db.rollback()
        raise Conflict("Attendance for this period was submitted by someone else just now.") from None
    audit_service.activity(
        account_id=account_id, role="teacher", activity_type="attendance_marked",
        description=f"Marked period {slot.period.period_number} attendance for {slot_label(slot)['label']}",
        entity_type="timetable", entity_id=slot.id, metadata={"date": day, **counts},
    )
    return {"message": "Attendance saved successfully.", "counts": counts, "total": len(payload.records)}


def correct(db: Session, teacher: Teacher, account_id: int, ay: AcademicYear, attendance_id: int, payload, ip: str | None) -> dict:
    record = db.get(Attendance, attendance_id, with_for_update=True)
    if record is None:
        raise NotFound("Attendance record not found.")
    slot = db.get(Timetable, record.timetable_id) if record.timetable_id else None
    is_slot_teacher = slot is not None and slot.teacher_id == teacher.id
    is_class_teacher = record.section_id in teacher_scope.class_teacher_section_ids(db, teacher, ay)
    if not (is_slot_teacher or is_class_teacher):
        raise Forbidden("Only the period teacher or class teacher can correct this record.")
    if record.date < today_local() - timedelta(days=BACKDATE_LIMIT_DAYS):
        raise AppError(f"Records older than {BACKDATE_LIMIT_DAYS} days cannot be corrected.", code="too_old")
    if payload.status == "leave" and leave_map(db, [record.student_id], record.date).get(record.student_id) != "approved":
        raise AppError("'Leave' requires an approved leave request.", code="leave_not_approved")
    new_reason = (payload.absence_reason or "uninformed") if payload.status == "absent" else None
    if record.status == payload.status and record.absence_reason == new_reason:
        raise AppError("No change to save.", code="no_change")

    db.add(AttendanceCorrection(
        attendance_id=record.id, old_status=record.status, new_status=payload.status,
        old_reason=record.absence_reason, new_reason=new_reason, reason=payload.reason,
        trigger="manual", corrected_by_teacher_id=teacher.id,
    ))
    old = record.status
    record.status, record.absence_reason, record.source = payload.status, new_reason, "correction"
    audit_service.record(
        db, account_id=account_id, role="teacher", action="attendance.corrected", entity_type="attendance",
        entity_id=record.id, details={"old": old, "new": payload.status, "reason": payload.reason}, ip=ip,
    )
    db.commit()
    return {"message": "Attendance record corrected.", "attendance_id": record.id, "status": record.status}


def periods(db: Session) -> list[dict]:
    return [
        {"id": p.id, "period_number": p.period_number, "start_time": p.start_time.strftime("%H:%M"),
         "end_time": p.end_time.strftime("%H:%M")}
        for p in db.scalars(select(Period).order_by(Period.period_number))
    ]
