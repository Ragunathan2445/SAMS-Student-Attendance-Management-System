"""Leave requests: parents submit, class teachers decide.

A submitted request never changes attendance by itself. Only on approval are the
student's existing *absent* records within the leave range converted to approved
leave (each change logged in ``attendance_corrections``). Periods not yet marked are
pre-filled as "Leave" in the teacher's marking sheet.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.db import mongo
from app.models import (
    AcademicYear,
    Attendance,
    AttendanceCorrection,
    LeaveApproval,
    LeaveRequest,
    Parent,
    Section,
    Student,
    StudentDocument,
    Teacher,
)
from app.utils.files import student_photo_url
from app.services import audit_service, teacher_scope
from app.utils import files
from app.utils.timeutils import today_local, utcnow

MAX_LEAVE_DAYS = 30
BACKDATE_DAYS = 7

REASON_LABELS = {
    "fever": "Fever",
    "medical_appointment": "Medical appointment",
    "family_function": "Family function",
    "personal": "Personal reasons",
    "other": "Other",
}


def to_dict(lv: LeaveRequest, *, include_student: bool = False) -> dict:
    data = {
        "id": lv.id,
        "student_id": lv.student_id,
        "start_date": lv.start_date.isoformat(),
        "end_date": lv.end_date.isoformat(),
        "days": (lv.end_date - lv.start_date).days + 1,
        "reason": lv.reason,
        "reason_label": REASON_LABELS.get(lv.reason, lv.reason),
        "description": lv.description,
        "status": lv.status,
        "submitted_at": lv.submitted_at.isoformat() if lv.submitted_at else None,
        "decided_at": lv.decided_at.isoformat() if lv.decided_at else None,
        "decided_by": lv.decided_by.full_name if lv.decided_by else None,
        "teacher_remarks": lv.teacher_remarks,
        "has_document": lv.document_id is not None,
        "document_name": lv.document.original_name if lv.document else None,
    }
    if include_student:
        s = lv.student
        data.update({
            "student_name": s.full_name,
            "roll_number": s.roll_number,
            "class_label": f"{s.section.school_class.name} – {s.section.name}",
            "photo_url": student_photo_url(s),
            "parent_name": lv.parent.full_name,
        })
    return data


def _query():
    return select(LeaveRequest).options(
        joinedload(LeaveRequest.decided_by),
        joinedload(LeaveRequest.document),
        joinedload(LeaveRequest.parent),
        joinedload(LeaveRequest.student).joinedload(Student.section).joinedload(Section.school_class),
    )


# --------------------------------------------------------------------------- parent side
def create(db: Session, parent: Parent, account_id: int, ay: AcademicYear, student: Student, *,
           start_date: date, end_date: date, reason: str, description: str | None,
           document: UploadFile | None, ip: str | None) -> dict:
    if student.status != "active":
        raise AppError("Leave cannot be requested for an inactive student.", code="student_inactive")
    if end_date < start_date:
        raise AppError("Leave end date must be on or after the start date.", code="invalid_range")
    today = today_local()
    if start_date < today - timedelta(days=BACKDATE_DAYS):
        raise AppError(f"Leave can be requested for absences up to {BACKDATE_DAYS} days in the past.", code="too_old")
    if (end_date - start_date).days + 1 > MAX_LEAVE_DAYS:
        raise AppError(f"A single leave request cannot exceed {MAX_LEAVE_DAYS} days.", code="too_long")
    if start_date < ay.start_date or end_date > ay.end_date:
        raise AppError("Leave dates must be within the current academic year.", code="outside_year")
    overlap = db.scalar(
        select(LeaveRequest.id).where(
            LeaveRequest.student_id == student.id, LeaveRequest.status.in_(("pending", "approved")),
            LeaveRequest.start_date <= end_date, LeaveRequest.end_date >= start_date,
        )
    )
    if overlap:
        raise Conflict("A pending or approved leave request already covers some of these dates.")

    doc_id = None
    if document is not None and document.filename:
        rel, content_type, size = files.save_document(document)
        doc = StudentDocument(student_id=student.id, doc_type="leave_support", file_path=rel,
                              original_name=files.safe_filename(document.filename), content_type=content_type,
                              size_bytes=size, uploaded_by_account_id=account_id)
        db.add(doc)
        db.flush()
        doc_id = doc.id

    lv = LeaveRequest(student_id=student.id, parent_id=parent.id, start_date=start_date, end_date=end_date,
                      reason=reason, description=description, document_id=doc_id, status="pending")
    db.add(lv)
    db.flush()
    audit_service.record(db, account_id=account_id, role="parent", action="leave.submitted",
                         entity_type="leave_request", entity_id=lv.id,
                         details={"student_id": student.id, "from": start_date, "to": end_date}, ip=ip)
    db.commit()
    mongo.log_notification(recipient_id=None, recipient_role="teacher", channel="in_app",
                           destination=f"Class teacher of section {student.section_id}",
                           subject="New leave request", body=f"Leave request #{lv.id} for {student.full_name}")
    audit_service.activity(account_id=account_id, role="parent", activity_type="leave_submitted",
                           description=f"Leave requested for {student.full_name}", entity_type="leave_request", entity_id=lv.id)
    return to_dict(db.scalars(_query().where(LeaveRequest.id == lv.id)).unique().one())


def list_for_parent(db: Session, parent: Parent, student_ids: list[int], *, student_id: int | None,
                    status: str | None, start: date | None, end: date | None) -> list[dict]:
    q = _query().where(LeaveRequest.student_id.in_([student_id] if student_id else student_ids))
    if status:
        q = q.where(LeaveRequest.status == status)
    if start:
        q = q.where(LeaveRequest.end_date >= start)
    if end:
        q = q.where(LeaveRequest.start_date <= end)
    rows = db.scalars(q.order_by(LeaveRequest.submitted_at.desc())).unique().all()
    return [to_dict(lv, include_student=True) for lv in rows]


# --------------------------------------------------------------------------- teacher side
def list_for_teacher(db: Session, teacher: Teacher, ay: AcademicYear, status: str | None) -> list[dict]:
    sections = teacher_scope.class_teacher_section_ids(db, teacher, ay)
    if not sections:
        return []
    q = _query().join(Student, Student.id == LeaveRequest.student_id).where(Student.section_id.in_(sections))
    if status:
        q = q.where(LeaveRequest.status == status)
    rows = db.scalars(q.order_by(LeaveRequest.status != "pending", LeaveRequest.submitted_at.desc())).unique().all()
    return [to_dict(lv, include_student=True) for lv in rows]


def decide(db: Session, teacher: Teacher, account_id: int, ay: AcademicYear, leave_id: int, *,
           action: str, remarks: str | None, ip: str | None) -> dict:
    lv = db.scalar(select(LeaveRequest).where(LeaveRequest.id == leave_id).with_for_update())
    if lv is None:
        raise NotFound("Leave request not found.")
    student = db.get(Student, lv.student_id)
    if student.section_id not in teacher_scope.class_teacher_section_ids(db, teacher, ay):
        raise Forbidden("Only the class teacher of this student can decide this leave request.")
    if lv.status != "pending":
        raise Conflict(f"This leave request has already been {lv.status}.")
    if action == "rejected" and not (remarks and remarks.strip()):
        raise AppError("Please give a reason when rejecting a leave request.", code="remarks_required")

    updated = 0
    if action == "approved":
        absent_rows = db.scalars(
            select(Attendance).where(
                Attendance.student_id == lv.student_id, Attendance.date >= lv.start_date,
                Attendance.date <= lv.end_date, Attendance.status == "absent",
            ).with_for_update()
        ).all()
        for row in absent_rows:
            db.add(AttendanceCorrection(
                attendance_id=row.id, old_status=row.status, new_status="leave", old_reason=row.absence_reason,
                new_reason=None, reason=f"Leave request #{lv.id} approved", trigger="leave_approval",
                leave_request_id=lv.id, corrected_by_teacher_id=teacher.id,
            ))
            row.status, row.absence_reason = "leave", None
            updated += 1

    lv.status, lv.decided_at, lv.decided_by_teacher_id = action, utcnow(), teacher.id
    lv.teacher_remarks = remarks.strip() if remarks else None
    db.add(LeaveApproval(leave_request_id=lv.id, action=action, acted_by_teacher_id=teacher.id,
                         remarks=lv.teacher_remarks, attendance_rows_updated=updated))
    audit_service.record(db, account_id=account_id, role="teacher", action=f"leave.{action}",
                         entity_type="leave_request", entity_id=lv.id,
                         details={"attendance_rows_updated": updated, "remarks": lv.teacher_remarks}, ip=ip)
    db.commit()
    mongo.log_notification(recipient_id=lv.parent_id, recipient_role="parent", channel="in_app",
                           destination=f"parent:{lv.parent_id}", subject=f"Leave request {action}",
                           body=f"Leave request #{lv.id} for {student.full_name} was {action}.")
    msg = f"Leave request {action}."
    if updated:
        msg += f" {updated} absent period record(s) updated to approved leave."
    return {"message": msg, "attendance_rows_updated": updated,
            "leave": to_dict(db.scalars(_query().where(LeaveRequest.id == lv.id)).unique().one(), include_student=True)}


def get_document_path(db: Session, lv: LeaveRequest):
    if not lv.document_id:
        raise NotFound("No document attached.")
    doc = db.get(StudentDocument, lv.document_id)
    path = files.resolve(doc.file_path) if doc else None
    if path is None:
        raise NotFound("Document file is missing.")
    return path, doc
