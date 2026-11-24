"""Parent portal API. Every student-scoped endpoint goes through ``get_parent_student``
so a parent can never read another family's data by changing an ID."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import (
    CurrentUser,
    client_ip,
    current_year,
    get_parent_student,
    parent_student_ids,
    require_parent,
)
from app.core.errors import AppError, NotFound
from app.db.session import get_db
from app.models import AcademicYear, FeeReceipt, LeaveRequest, School, Section, Student
from app.services import attendance_reports, fee_service, leave_service, pdf_service, profile_service
from app.utils.timeutils import today_local

router = APIRouter(prefix="/parent", tags=["Parent portal"])


@router.get("/students")
def my_students(user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db)):
    return {"parent_name": user.parent.full_name, "students": profile_service.parent_students(db, user.parent)}


@router.get("/students/{student_id}/profile")
def student_profile(student_id: int, user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db)):
    return profile_service.student_profile(db, get_parent_student(db, user, student_id))


# ----------------------------------------------------------------- attendance
@router.get("/students/{student_id}/attendance/overview")
def attendance_overview(student_id: int, user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db),
                        ay: AcademicYear = Depends(current_year)):
    return attendance_reports.overview(db, get_parent_student(db, user, student_id), ay)


@router.get("/students/{student_id}/attendance/daily")
def attendance_daily(student_id: int, day: date | None = Query(None, alias="date"),
                     user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db),
                     ay: AcademicYear = Depends(current_year)):
    return attendance_reports.daily_report(db, get_parent_student(db, user, student_id), ay, day or today_local())


@router.get("/students/{student_id}/attendance/weekly")
def attendance_weekly(student_id: int, day: date | None = Query(None, alias="date"),
                      user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db),
                      ay: AcademicYear = Depends(current_year)):
    return attendance_reports.weekly_report(db, get_parent_student(db, user, student_id), ay, day or today_local())


@router.get("/students/{student_id}/attendance/monthly")
def attendance_monthly(student_id: int, year: int | None = Query(None, ge=2000, le=2100),
                       month: int | None = Query(None, ge=1, le=12),
                       user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db),
                       ay: AcademicYear = Depends(current_year)):
    today = today_local()
    return attendance_reports.monthly_report(db, get_parent_student(db, user, student_id), ay,
                                             year or today.year, month or today.month)


@router.get("/students/{student_id}/attendance/yearly")
def attendance_yearly(student_id: int, user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db),
                      ay: AcademicYear = Depends(current_year)):
    return attendance_reports.yearly_report(db, get_parent_student(db, user, student_id), ay)


@router.get("/students/{student_id}/attendance/history")
def attendance_history(student_id: int, start: date | None = Query(None, alias="from"),
                       end: date | None = Query(None, alias="to"),
                       user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db),
                       ay: AcademicYear = Depends(current_year)):
    student = get_parent_student(db, user, student_id)
    return {"days": attendance_reports.history(db, student, ay, start or ay.start_date, end or today_local())}


@router.get("/students/{student_id}/academic-records")
def academic_records(student_id: int, user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db)):
    get_parent_student(db, user, student_id)
    return {"records": profile_service.academic_records(db, student_id)}


# ----------------------------------------------------------------- leave
@router.get("/leave-requests")
def list_leave(student_id: int | None = None, status: Literal["pending", "approved", "rejected"] | None = None,
               start: date | None = Query(None, alias="from"), end: date | None = Query(None, alias="to"),
               user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db)):
    if student_id:
        get_parent_student(db, user, student_id)
    return {"requests": leave_service.list_for_parent(db, user.parent, parent_student_ids(db, user.parent),
                                                      student_id=student_id, status=status, start=start, end=end)}


@router.post("/leave-requests", status_code=201)
def create_leave(
    request: Request,
    student_id: int = Form(..., gt=0),
    start_date: date = Form(...),
    end_date: date = Form(...),
    reason: Literal["fever", "medical_appointment", "family_function", "personal", "other"] = Form(...),
    description: str | None = Form(None, max_length=1000),
    document: UploadFile | None = File(None),
    user: CurrentUser = Depends(require_parent),
    db: Session = Depends(get_db),
    ay: AcademicYear = Depends(current_year),
):
    student = get_parent_student(db, user, student_id)
    return leave_service.create(db, user.parent, user.account_id, ay, student, start_date=start_date, end_date=end_date,
                                reason=reason, description=(description or "").strip() or None,
                                document=document, ip=client_ip(request))


@router.get("/leave-requests/{leave_id}/document")
def leave_document(leave_id: int, user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db)):
    lv = db.get(LeaveRequest, leave_id)
    if lv is None or lv.student_id not in parent_student_ids(db, user.parent):
        raise NotFound("Leave request not found.")
    path, doc = leave_service.get_document_path(db, lv)
    return FileResponse(path, media_type=doc.content_type, filename=doc.original_name)


# ----------------------------------------------------------------- fees
@router.get("/students/{student_id}/fees")
def fees(student_id: int, user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db),
         ay: AcademicYear = Depends(current_year)):
    get_parent_student(db, user, student_id)
    return fee_service.fee_details(db, student_id, ay)


@router.get("/students/{student_id}/payments")
def payments(student_id: int, start: date | None = Query(None, alias="from"), end: date | None = Query(None, alias="to"),
             user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db),
             ay: AcademicYear = Depends(current_year)):
    get_parent_student(db, user, student_id)
    return {"payments": fee_service.payment_history(db, student_id, ay, start, end)}


@router.get("/students/{student_id}/balance-history")
def balance_history(student_id: int, start: date | None = Query(None, alias="from"),
                    end: date | None = Query(None, alias="to"),
                    user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db),
                    ay: AcademicYear = Depends(current_year)):
    get_parent_student(db, user, student_id)
    return fee_service.balance_history(db, student_id, ay, start, end)


@router.get("/payments/{payment_id}/receipt")
def receipt_pdf(payment_id: int, user: CurrentUser = Depends(require_parent), db: Session = Depends(get_db)):
    payment = fee_service.get_payment(db, payment_id)
    if payment.student_id not in parent_student_ids(db, user.parent):
        raise NotFound("Payment not found.")
    receipt = db.scalar(select(FeeReceipt).where(FeeReceipt.payment_id == payment.id))
    if receipt is None or payment.status != "success":
        raise AppError("No receipt is available for this payment.", code="no_receipt")
    student = db.scalar(select(Student).options(joinedload(Student.section).joinedload(Section.school_class))
                        .where(Student.id == payment.student_id))
    ay = db.get(AcademicYear, payment.academic_year_id)
    pdf = pdf_service.fee_receipt_pdf(
        school=db.scalar(select(School).limit(1)), receipt_number=receipt.receipt_number,
        student_name=student.full_name, roll_number=student.roll_number,
        class_label=f"{student.section.school_class.name} – {student.section.name}", academic_year=ay.name,
        payment_date=payment.payment_date.strftime("%d %b %Y"),
        category_label=fee_service.CATEGORY_LABELS[payment.fee_record.category],
        description=payment.fee_record.description, amount=payment.amount, payment_ref=payment.transaction_ref,
        method_label=fee_service.METHOD_LABELS.get(payment.method, payment.method),
        total_paid=receipt.total_paid_to_date, remaining_balance=receipt.balance_after,
    )
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="receipt-{receipt.receipt_number}.pdf"'})
