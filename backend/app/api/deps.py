"""Request dependencies: current session/user, role and permission guards."""
from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Forbidden, NotAuthenticated, NotFound
from app.db.session import get_db
from app.models import AcademicYear, Parent, ParentStudent, Student, Teacher, UserAccount, UserSession
from app.services import session_service
from app.services.calendar_service import get_current_academic_year


@dataclass
class CurrentUser:
    account: UserAccount
    session: UserSession
    role: str
    permissions: set[str] = field(default_factory=set)
    parent: Parent | None = None
    teacher: Teacher | None = None

    @property
    def account_id(self) -> int:
        return self.account.id


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        raise NotAuthenticated("Please sign in to continue.")
    session = session_service.resolve_session(db, token)
    if session is None:
        raise NotAuthenticated("Your session has expired. Please sign in again.", code="session_expired")
    account = session.account
    user = CurrentUser(account=account, session=session, role=account.role.code,
                       permissions={p.code for p in account.role.permissions})
    if user.role == "parent":
        user.parent = db.scalar(select(Parent).where(Parent.user_account_id == account.id))
        if user.parent is None:
            raise NotAuthenticated("Account not linked.")
    elif user.role == "teacher":
        user.teacher = db.scalar(select(Teacher).where(Teacher.user_account_id == account.id))
        if user.teacher is None or not user.teacher.is_active:
            raise NotAuthenticated("Account not linked.")
    return user


def require_parent(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "parent":
        raise Forbidden("This area is for parents only.")
    return user


def require_teacher(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "teacher":
        raise Forbidden("This area is for teachers only.")
    return user


def require_permission(code: str):
    def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if code not in user.permissions:
            raise Forbidden("You do not have permission to perform this action.")
        return user

    return _check


def current_year(db: Session = Depends(get_db)) -> AcademicYear:
    return get_current_academic_year(db)


def parent_student_ids(db: Session, parent: Parent) -> list[int]:
    return list(db.scalars(select(ParentStudent.student_id).where(ParentStudent.parent_id == parent.id)))


def get_parent_student(db: Session, user: CurrentUser, student_id: int) -> Student:
    """IDOR protection: a parent may only load students linked to their own account.
    Unlinked and non-existent IDs give the same 404 response."""
    linked = db.scalar(
        select(ParentStudent).where(ParentStudent.parent_id == user.parent.id, ParentStudent.student_id == student_id)
    )
    student = db.get(Student, student_id) if linked else None
    if student is None:
        raise NotFound("Student not found.")
    return student


def parse_form_model(model: type[BaseModel], raw: str):
    try:
        return model.model_validate_json(raw)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from None
