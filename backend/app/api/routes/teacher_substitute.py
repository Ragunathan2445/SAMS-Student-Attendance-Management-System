"""Substitute (temporary) attendance and approvals."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, client_ip, current_year, require_permission
from app.db.session import get_db
from app.models import AcademicYear
from app.schemas.attendance import RejectIn, SubstituteSubmit
from app.services import substitute_service

router = APIRouter(prefix="/teacher/substitute", tags=["Substitute attendance"])


@router.get("/assignments")
def assignments(start: date | None = Query(None, alias="from"), end: date | None = Query(None, alias="to"),
                user: CurrentUser = Depends(require_permission("attendance.substitute.submit")),
                db: Session = Depends(get_db)):
    d_start, d_end = substitute_service.default_window()
    return {"assignments": substitute_service.my_assignments(db, user.teacher, start or d_start, end or d_end)}


@router.get("/assignments/{assignment_id}/sheet")
def sheet(assignment_id: int, user: CurrentUser = Depends(require_permission("attendance.substitute.submit")),
          db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return substitute_service.get_sheet(db, user.teacher, ay, assignment_id)


@router.post("/assignments/{assignment_id}/submissions", status_code=201)
def submit(assignment_id: int, body: SubstituteSubmit, request: Request,
           user: CurrentUser = Depends(require_permission("attendance.substitute.submit")),
           db: Session = Depends(get_db), ay: AcademicYear = Depends(current_year)):
    return substitute_service.submit(db, user.teacher, user.account_id, ay, assignment_id, body.records, client_ip(request))


@router.get("/submissions/mine")
def my_submissions(user: CurrentUser = Depends(require_permission("attendance.substitute.submit")),
                   db: Session = Depends(get_db)):
    return {"submissions": substitute_service.list_mine(db, user.teacher)}


@router.get("/approvals")
def approvals(status: Literal["pending", "approved", "rejected"] | None = None,
              user: CurrentUser = Depends(require_permission("attendance.substitute.approve")),
              db: Session = Depends(get_db)):
    return {"submissions": substitute_service.list_for_reviewer(db, user.teacher, status)}


@router.get("/submissions/{submission_id}")
def detail(submission_id: int, user: CurrentUser = Depends(require_permission("attendance.substitute.submit")),
           db: Session = Depends(get_db)):
    return substitute_service.get_detail(db, user.teacher, user.permissions, submission_id)


@router.post("/submissions/{submission_id}/approve")
def approve(submission_id: int, request: Request,
            user: CurrentUser = Depends(require_permission("attendance.substitute.approve")),
            db: Session = Depends(get_db)):
    return substitute_service.approve(db, user.teacher, user.account_id, user.role, user.permissions, submission_id,
                                      client_ip(request))


@router.post("/submissions/{submission_id}/reject")
def reject(submission_id: int, body: RejectIn, request: Request,
           user: CurrentUser = Depends(require_permission("attendance.substitute.approve")),
           db: Session = Depends(get_db)):
    return substitute_service.reject(db, user.teacher, user.account_id, user.role, user.permissions, submission_id,
                                     body.reason, client_ip(request))
