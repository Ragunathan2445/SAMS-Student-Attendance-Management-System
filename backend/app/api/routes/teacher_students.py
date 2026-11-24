"""Student management (add/update/deactivate) and the emergency student directory."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, client_ip, current_year, parse_form_model, require_permission
from app.db.session import get_db
from app.models import AcademicYear
from app.schemas.students import StatusChange, StudentCreate, StudentUpdate
from app.services import student_admin_service

router = APIRouter(prefix="/teacher", tags=["Student management"])


@router.get("/manage/students")
def manage_list(section_id: int | None = Query(None, gt=0), q: str | None = Query(None, max_length=100),
                include_inactive: bool = False,
                user: CurrentUser = Depends(require_permission("students.manage")),
                db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return {"students": student_admin_service.list_students(db, user.teacher, ay, section_id, q, include_inactive)}


@router.post("/manage/students", status_code=201)
def create(request: Request, payload: str = Form(..., max_length=10_000), photo: UploadFile | None = File(None),
           user: CurrentUser = Depends(require_permission("students.manage")),
           db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    data = parse_form_model(StudentCreate, payload)
    return student_admin_service.create_student(db, user.teacher, user.account_id, ay, data, photo, client_ip(request))


@router.put("/manage/students/{student_id}")
def update(student_id: int, request: Request, payload: str = Form(..., max_length=10_000),
           photo: UploadFile | None = File(None),
           user: CurrentUser = Depends(require_permission("students.manage")),
           db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    data = parse_form_model(StudentUpdate, payload)
    return student_admin_service.update_student(db, user.teacher, user.account_id, ay, student_id, data, photo,
                                                client_ip(request))


@router.post("/manage/students/{student_id}/deactivate")
def deactivate(student_id: int, body: StatusChange, request: Request,
               user: CurrentUser = Depends(require_permission("students.manage")),
               db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return student_admin_service.set_active(db, user.teacher, user.account_id, ay, student_id, active=False,
                                            reason=body.reason, totp_code=body.totp_code, ip=client_ip(request))


@router.post("/manage/students/{student_id}/reactivate")
def reactivate(student_id: int, body: StatusChange, request: Request,
               user: CurrentUser = Depends(require_permission("students.manage")),
               db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return student_admin_service.set_active(db, user.teacher, user.account_id, ay, student_id, active=True,
                                            reason=body.reason, totp_code=body.totp_code, ip=client_ip(request))


@router.get("/manage/students/{student_id}/history")
def history(student_id: int, user: CurrentUser = Depends(require_permission("students.manage")),
            db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return {"history": student_admin_service.change_history(db, user.teacher, ay, student_id)}


@router.get("/students/directory")
def directory(section_id: int | None = Query(None, gt=0), q: str | None = Query(None, max_length=100),
              user: CurrentUser = Depends(require_permission("students.directory.view")),
              db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return {"students": student_admin_service.directory(db, user.teacher, ay, section_id, q)}
