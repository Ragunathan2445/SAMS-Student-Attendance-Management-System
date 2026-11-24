"""Substitute (temporary) attendance.

Flow: substitute marks → ``attendance_submissions`` (pending, NOT official) →
responsible teacher approves (rows copied into official ``attendance``) or rejects
(kept in history with reason). Every decision is written to ``attendance_approvals``.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.errors import Conflict, Forbidden, NotFound
from app.db import mongo
from app.models import (
    AcademicYear,
    Attendance,
    AttendanceApproval,
    AttendanceSubmission,
    AttendanceSubmissionItem,
    Section,
    Student,
    SubstituteAssignment,
    Teacher,
    Timetable,
)
from app.utils.files import student_photo_url
from app.services import audit_service
from app.services.attendance_marking import (
    leave_map,
    section_students,
    student_row,
    validate_marking_date,
    validate_records,
)
from app.utils.timeutils import today_local, utcnow


def _assignment_query():
    return select(SubstituteAssignment).options(
        joinedload(SubstituteAssignment.section).joinedload(Section.school_class),
        joinedload(SubstituteAssignment.period),
        joinedload(SubstituteAssignment.timetable).joinedload(Timetable.subject),
        joinedload(SubstituteAssignment.regular_teacher),
        joinedload(SubstituteAssignment.responsible_teacher),
        joinedload(SubstituteAssignment.substitute_teacher),
    )


def _assignment_dict(db: Session, a: SubstituteAssignment) -> dict:
    latest = db.scalar(
        select(AttendanceSubmission)
        .where(AttendanceSubmission.substitute_assignment_id == a.id)
        .order_by(AttendanceSubmission.submitted_at.desc())
        .limit(1)
    )
    official = db.scalar(
        select(func.count(Attendance.id)).where(
            Attendance.section_id == a.section_id, Attendance.date == a.date, Attendance.period_id == a.period_id
        )
    )
    return {
        "assignment_id": a.id,
        "date": a.date.isoformat(),
        "weekday": a.date.strftime("%A"),
        "section_id": a.section_id,
        "class_name": a.section.school_class.name,
        "section_name": a.section.name,
        "label": f"{a.section.school_class.name} – {a.section.name}",
        "period_id": a.period_id,
        "period_number": a.period.period_number,
        "start_time": a.period.start_time.strftime("%H:%M"),
        "end_time": a.period.end_time.strftime("%H:%M"),
        "subject": a.timetable.subject.name,
        "regular_teacher": a.regular_teacher.full_name,
        "responsible_teacher": a.responsible_teacher.full_name,
        "reason": a.reason,
        "submission_status": latest.status if latest else None,
        "submission_id": latest.id if latest else None,
        "official_attendance_exists": official > 0,
        "can_submit": (latest is None or latest.status == "rejected") and official == 0 and a.date <= today_local(),
    }


def my_assignments(db: Session, teacher: Teacher, start: date, end: date) -> list[dict]:
    rows = db.scalars(
        _assignment_query()
        .where(SubstituteAssignment.substitute_teacher_id == teacher.id,
               SubstituteAssignment.date >= start, SubstituteAssignment.date <= end)
        .order_by(SubstituteAssignment.date.desc(), SubstituteAssignment.period_id)
    ).unique().all()
    return [_assignment_dict(db, a) for a in rows]


def _own_assignment(db: Session, teacher: Teacher, assignment_id: int) -> SubstituteAssignment:
    a = db.scalars(_assignment_query().where(SubstituteAssignment.id == assignment_id)).unique().first()
    if a is None:
        raise NotFound("Substitute assignment not found.")
    if a.substitute_teacher_id != teacher.id:
        raise Forbidden("This substitute duty is not assigned to you.")
    return a


def get_sheet(db: Session, teacher: Teacher, ay: AcademicYear, assignment_id: int) -> dict:
    a = _own_assignment(db, teacher, assignment_id)
    validate_marking_date(db, ay, a.date)
    students = section_students(db, a.section_id, a.date)
    leaves = leave_map(db, [s.id for s in students], a.date)
    return {"assignment": _assignment_dict(db, a), "students": [student_row(s, leaves.get(s.id)) for s in students]}


def submit(db: Session, teacher: Teacher, account_id: int, ay: AcademicYear, assignment_id: int, records: list, ip: str | None) -> dict:
    a = _own_assignment(db, teacher, assignment_id)
    validate_marking_date(db, ay, a.date)
    info = _assignment_dict(db, a)
    if info["official_attendance_exists"]:
        raise Conflict("Official attendance has already been recorded for this period.")
    if info["submission_status"] in ("pending", "approved"):
        raise Conflict(f"A temporary attendance submission is already {info['submission_status']} for this period.")

    students = section_students(db, a.section_id, a.date)
    leaves = leave_map(db, [s.id for s in students], a.date)
    validate_records(records, students, leaves)
    counts = {"present": 0, "absent": 0, "leave": 0}
    for r in records:
        counts[r.status] += 1

    submission = AttendanceSubmission(
        substitute_assignment_id=a.id, substitute_teacher_id=teacher.id, substitute_teacher_name=teacher.full_name,
        responsible_teacher_id=a.responsible_teacher_id, section_id=a.section_id,
        class_name=a.section.school_class.name, section_name=a.section.name, date=a.date,
        period_id=a.period_id, timetable_id=a.timetable_id, present_count=counts["present"],
        absent_count=counts["absent"], leave_count=counts["leave"], status="pending",
        items=[
            AttendanceSubmissionItem(
                student_id=r.student_id, status=r.status,
                absence_reason=(r.absence_reason or "uninformed") if r.status == "absent" else None,
                remarks=r.remarks,
            )
            for r in records
        ],
    )
    db.add(submission)
    try:
        db.flush()
        audit_service.record(
            db, account_id=account_id, role="teacher", action="substitute_attendance.submitted",
            entity_type="attendance_submission", entity_id=submission.id,
            details={"assignment_id": a.id, "date": a.date, **counts}, ip=ip,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict("A submission for this period already exists.") from None

    mongo.log_notification(
        recipient_id=a.responsible_teacher_id, recipient_role="teacher", channel="in_app",
        destination=a.responsible_teacher.full_name, subject="Temporary attendance awaiting approval",
        body=f"{teacher.full_name} submitted attendance for {info['label']} period {info['period_number']} on {a.date}.",
    )
    audit_service.activity(account_id=account_id, role="teacher", activity_type="substitute_submitted",
                           description=f"Submitted temporary attendance for {info['label']}",
                           entity_type="attendance_submission", entity_id=submission.id)
    return {"message": "Temporary attendance submitted for approval.", "submission_id": submission.id, "counts": counts}


# --------------------------------------------------------------------------- review
def _submission_query():
    return select(AttendanceSubmission).options(
        selectinload(AttendanceSubmission.items).joinedload(AttendanceSubmissionItem.student),
        joinedload(AttendanceSubmission.period),
        joinedload(AttendanceSubmission.responsible_teacher),
        joinedload(AttendanceSubmission.decided_by),
    )


def _submission_dict(db: Session, s: AttendanceSubmission, *, with_items: bool = False) -> dict:
    out = {
        "submission_id": s.id,
        "substitute_teacher_id": s.substitute_teacher_id,
        "substitute_teacher_name": s.substitute_teacher_name,
        "responsible_teacher_id": s.responsible_teacher_id,
        "responsible_teacher_name": s.responsible_teacher.full_name,
        "class_name": s.class_name,
        "section_name": s.section_name,
        "label": f"{s.class_name} – {s.section_name}",
        "date": s.date.isoformat(),
        "period_number": s.period.period_number,
        "present_count": s.present_count,
        "absent_count": s.absent_count,
        "leave_count": s.leave_count,
        "status": s.status,
        "submitted_at": s.submitted_at.isoformat(),
        "decided_at": s.decided_at.isoformat() if s.decided_at else None,
        "decided_by": s.decided_by.full_name if s.decided_by else None,
        "rejection_reason": s.rejection_reason,
    }
    if with_items:
        out["items"] = [
            {
                "student_id": i.student_id,
                "full_name": i.student.full_name,
                "roll_number": i.student.roll_number,
                "photo_url": student_photo_url(i.student),
                "status": i.status,
                "absence_reason": i.absence_reason,
                "remarks": i.remarks,
            }
            for i in sorted(s.items, key=lambda i: i.student.roll_number)
        ]
        out["audit_trail"] = [
            {"action": ap.action, "acted_by_role": ap.acted_by_role, "reason": ap.reason,
             "records_finalized": ap.records_finalized, "acted_at": ap.acted_at.isoformat(),
             "acted_by": db.get(Teacher, ap.acted_by_teacher_id).full_name if ap.acted_by_teacher_id else "Administrator"}
            for ap in db.scalars(
                select(AttendanceApproval).where(AttendanceApproval.submission_id == s.id).order_by(AttendanceApproval.acted_at)
            )
        ]
    return out


def list_for_reviewer(db: Session, teacher: Teacher, status: str | None) -> list[dict]:
    q = _submission_query().where(AttendanceSubmission.responsible_teacher_id == teacher.id)
    if status:
        q = q.where(AttendanceSubmission.status == status)
    rows = db.scalars(q.order_by(AttendanceSubmission.submitted_at.desc())).unique().all()
    return [_submission_dict(db, s) for s in rows]


def list_mine(db: Session, teacher: Teacher) -> list[dict]:
    rows = db.scalars(
        _submission_query().where(AttendanceSubmission.substitute_teacher_id == teacher.id)
        .order_by(AttendanceSubmission.submitted_at.desc())
    ).unique().all()
    return [_submission_dict(db, s) for s in rows]


def _can_review(s: AttendanceSubmission, teacher: Teacher | None, permissions: set[str]) -> bool:
    return (teacher is not None and s.responsible_teacher_id == teacher.id) or "attendance.substitute.approve_any" in permissions


def get_detail(db: Session, teacher: Teacher, permissions: set[str], submission_id: int) -> dict:
    s = db.scalars(_submission_query().where(AttendanceSubmission.id == submission_id)).unique().first()
    if s is None:
        raise NotFound("Submission not found.")
    if not (_can_review(s, teacher, permissions) or s.substitute_teacher_id == teacher.id):
        raise Forbidden("You are not allowed to view this submission.")
    data = _submission_dict(db, s, with_items=True)
    data["can_decide"] = s.status == "pending" and _can_review(s, teacher, permissions)
    return data


def _lock_pending(db: Session, teacher: Teacher, permissions: set[str], submission_id: int) -> AttendanceSubmission:
    s = db.scalar(select(AttendanceSubmission).where(AttendanceSubmission.id == submission_id).with_for_update())
    if s is None:
        raise NotFound("Submission not found.")
    if not _can_review(s, teacher, permissions):
        raise Forbidden("Only the responsible teacher can review this submission.")
    if s.status != "pending":
        raise Conflict(f"This submission has already been {s.status}.")
    return s


def approve(db: Session, teacher: Teacher, account_id: int, role: str, permissions: set[str], submission_id: int, ip: str | None) -> dict:
    s = _lock_pending(db, teacher, permissions, submission_id)
    already = db.scalar(
        select(func.count(Attendance.id)).where(
            Attendance.section_id == s.section_id, Attendance.date == s.date, Attendance.period_id == s.period_id
        )
    )
    if already:
        raise Conflict("Official attendance already exists for this period; the submission cannot be finalised twice.")
    slot = db.get(Timetable, s.timetable_id) if s.timetable_id else None
    items = db.scalars(select(AttendanceSubmissionItem).where(AttendanceSubmissionItem.submission_id == s.id)).all()
    active_ids = {st.id for st in db.scalars(select(Student).where(Student.id.in_([i.student_id for i in items]), Student.status == "active"))}
    finalized = 0
    try:
        for item in items:
            if item.student_id not in active_ids:
                continue
            db.add(Attendance(
                student_id=item.student_id, section_id=s.section_id, date=s.date, period_id=s.period_id,
                timetable_id=s.timetable_id, subject_id=slot.subject_id if slot else None, status=item.status,
                absence_reason=item.absence_reason, remarks=item.remarks,
                marked_by_teacher_id=s.substitute_teacher_id, source="substitute", submission_id=s.id,
            ))
            finalized += 1
        now = utcnow()
        s.status, s.decided_at, s.decided_by_teacher_id, s.decided_by_account_id = "approved", now, teacher.id, account_id
        db.add(AttendanceApproval(submission_id=s.id, action="approved", acted_by_teacher_id=teacher.id,
                                  acted_by_account_id=account_id, acted_by_role=role, records_finalized=finalized))
        audit_service.record(db, account_id=account_id, role=role, action="substitute_attendance.approved",
                             entity_type="attendance_submission", entity_id=s.id, details={"finalized": finalized}, ip=ip)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict("Official attendance already exists for this period.") from None
    mongo.log_notification(recipient_id=s.substitute_teacher_id, recipient_role="teacher", channel="in_app",
                           destination=s.substitute_teacher_name, subject="Temporary attendance approved",
                           body=f"Your submission #{s.id} was approved by {teacher.full_name}.")
    return {"message": f"Approved. {finalized} records added to official attendance.", "status": "approved"}


def reject(db: Session, teacher: Teacher, account_id: int, role: str, permissions: set[str], submission_id: int, reason: str, ip: str | None) -> dict:
    s = _lock_pending(db, teacher, permissions, submission_id)
    now = utcnow()
    s.status, s.decided_at, s.decided_by_teacher_id, s.decided_by_account_id = "rejected", now, teacher.id, account_id
    s.rejection_reason = reason
    db.add(AttendanceApproval(submission_id=s.id, action="rejected", acted_by_teacher_id=teacher.id,
                              acted_by_account_id=account_id, acted_by_role=role, reason=reason))
    audit_service.record(db, account_id=account_id, role=role, action="substitute_attendance.rejected",
                         entity_type="attendance_submission", entity_id=s.id, details={"reason": reason}, ip=ip)
    db.commit()
    mongo.log_notification(recipient_id=s.substitute_teacher_id, recipient_role="teacher", channel="in_app",
                           destination=s.substitute_teacher_name, subject="Temporary attendance rejected",
                           body=f"Submission #{s.id} was rejected: {reason}")
    return {"message": "Submission rejected. It remains available in history.", "status": "rejected"}


def default_window() -> tuple[date, date]:
    today = today_local()
    return today - timedelta(days=14), today + timedelta(days=14)


def pending_count(db: Session, teacher: Teacher) -> int:
    return db.scalar(
        select(func.count(AttendanceSubmission.id)).where(
            AttendanceSubmission.responsible_teacher_id == teacher.id, AttendanceSubmission.status == "pending"
        )
    ) or 0
