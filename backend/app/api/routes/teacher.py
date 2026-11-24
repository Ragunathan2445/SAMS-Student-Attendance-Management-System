"""Teacher portal: profile, official attendance, leave decisions and analytics."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, client_ip, current_year, require_permission, require_teacher
from app.core.errors import NotFound
from app.db.session import get_db
from app.models import AcademicYear, LeaveRequest, Student
from app.schemas.attendance import AttendanceCorrectionIn, AttendanceSubmit, LeaveDecision
from app.services import (
    analytics_service,
    attendance_marking,
    leave_service,
    profile_service,
    substitute_service,
    teacher_scope,
)
from app.utils.timeutils import today_local

router = APIRouter(prefix="/teacher", tags=["Teacher portal"])


@router.get("/profile")
def profile(user: CurrentUser = Depends(require_teacher), db: Session = Depends(get_db),
            ay: AcademicYear = Depends(current_year)):
    data = profile_service.teacher_profile(db, user.teacher, ay)
    data["timetable"] = profile_service.weekly_timetable(db, user.teacher, ay)
    data["pending_approvals"] = substitute_service.pending_count(db, user.teacher)
    data["pending_leave_requests"] = len(leave_service.list_for_teacher(db, user.teacher, ay, "pending"))
    return data


@router.get("/sections")
def sections(user: CurrentUser = Depends(require_teacher), db: Session = Depends(get_db),
             ay: AcademicYear = Depends(current_year)):
    ct = teacher_scope.class_teacher_section_ids(db, user.teacher, ay)
    return {"sections": teacher_scope.sections_payload(db, teacher_scope.authorised_section_ids(db, user.teacher, ay), ct),
            "class_teacher_sections": teacher_scope.sections_payload(db, ct, ct)}


# ----------------------------------------------------------------- attendance marking
@router.get("/attendance/slots")
def attendance_slots(day: date | None = Query(None, alias="date"), user: CurrentUser = Depends(require_permission("attendance.mark")),
                     db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return attendance_marking.slots_for_date(db, user.teacher, ay, day or today_local())


@router.get("/attendance/sheet")
def attendance_sheet(section_id: int = Query(..., gt=0), period_id: int = Query(..., gt=0),
                     day: date = Query(..., alias="date"),
                     user: CurrentUser = Depends(require_permission("attendance.mark")),
                     db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return attendance_marking.get_sheet(db, user.teacher, ay, day, section_id, period_id)


@router.post("/attendance", status_code=201)
def submit_attendance(body: AttendanceSubmit, request: Request,
                      user: CurrentUser = Depends(require_permission("attendance.mark")),
                      db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return attendance_marking.submit(db, user.teacher, user.account_id, ay, body, client_ip(request))


@router.patch("/attendance/{attendance_id}")
def correct_attendance(attendance_id: int, body: AttendanceCorrectionIn, request: Request,
                       user: CurrentUser = Depends(require_permission("attendance.correct")),
                       db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return attendance_marking.correct(db, user.teacher, user.account_id, ay, attendance_id, body, client_ip(request))


# ----------------------------------------------------------------- leave approvals
@router.get("/leave-requests")
def leave_requests(status: Literal["pending", "approved", "rejected"] | None = None,
                   user: CurrentUser = Depends(require_permission("leave.approve")),
                   db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return {"requests": leave_service.list_for_teacher(db, user.teacher, ay, status)}


@router.post("/leave-requests/{leave_id}/decision")
def decide_leave(leave_id: int, body: LeaveDecision, request: Request,
                 user: CurrentUser = Depends(require_permission("leave.approve")),
                 db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return leave_service.decide(db, user.teacher, user.account_id, ay, leave_id, action=body.action,
                                remarks=body.remarks, ip=client_ip(request))


@router.get("/leave-requests/{leave_id}/document")
def leave_document(leave_id: int, user: CurrentUser = Depends(require_permission("leave.approve")),
                   db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    lv = db.get(LeaveRequest, leave_id)
    student = db.get(Student, lv.student_id) if lv else None
    if student is None or student.section_id not in teacher_scope.class_teacher_section_ids(db, user.teacher, ay):
        raise NotFound("Leave request not found.")
    path, doc = leave_service.get_document_path(db, lv)
    return FileResponse(path, media_type=doc.content_type, filename=doc.original_name)


# ----------------------------------------------------------------- analytics
@router.get("/analytics/class")
def class_report(section_id: int | None = Query(None, gt=0), student_id: int | None = Query(None, gt=0),
                 start: date | None = Query(None, alias="from"), end: date | None = Query(None, alias="to"),
                 user: CurrentUser = Depends(require_permission("attendance.reports.view")),
                 db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return analytics_service.class_report(db, user.teacher, ay, section_id=section_id, start=start, end=end,
                                          student_id=student_id)


@router.get("/analytics/monthly")
def monthly(section_id: int | None = Query(None, gt=0),
            user: CurrentUser = Depends(require_permission("attendance.reports.view")),
            db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return {"months": analytics_service.monthly_summary(db, user.teacher, ay, section_id)}


@router.get("/analytics/students/{student_id}")
def student_report(student_id: int, user: CurrentUser = Depends(require_permission("attendance.reports.view")),
                   db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return analytics_service.student_report(db, user.teacher, ay, student_id)


@router.get("/analytics/export")
def export(section_id: int | None = Query(None, gt=0), start: date | None = Query(None, alias="from"),
           end: date | None = Query(None, alias="to"),
           user: CurrentUser = Depends(require_permission("attendance.reports.view")),
           db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    report = analytics_service.class_report(db, user.teacher, ay, section_id=section_id, start=start, end=end)
    content = analytics_service.export_xlsx(report, "Attendance report")
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="attendance-{report["start_date"]}-to-{report["end_date"]}.xlsx"'})
