"""Authorised access to student and teacher photographs (never publicly served)."""
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, current_year, get_current_user
from app.core.errors import NotFound
from app.db.session import get_db
from app.models import AcademicYear, ParentStudent, Student, Teacher
from app.services import teacher_scope
from app.utils import files

router = APIRouter(prefix="/files", tags=["Files"])
_CACHE = {"Cache-Control": "private, max-age=86400"}  # URLs carry ?v=<photo version>


def _send(rel_path: str | None):
    path = files.resolve(rel_path)
    if path is None:
        raise NotFound("Photo not found.")
    media = "image/png" if path.suffix == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media, headers=_CACHE)


@router.get("/students/{student_id}/photo")
def student_photo(student_id: int, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
                  ay: AcademicYear = Depends(current_year)):
    student = db.get(Student, student_id)
    allowed = False
    if student and user.parent:
        allowed = db.scalar(select(ParentStudent).where(ParentStudent.parent_id == user.parent.id,
                                                        ParentStudent.student_id == student_id)) is not None
    elif student and user.teacher:
        allowed = teacher_scope.can_view_student_photo(db, user.teacher, ay, student)
    if not allowed:
        raise NotFound("Photo not found.")
    return _send(student.photo_path)


@router.get("/teachers/{teacher_id}/photo")
def teacher_photo(teacher_id: int, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.teacher or user.teacher.id != teacher_id:
        raise NotFound("Photo not found.")
    teacher = db.get(Teacher, teacher_id)
    return _send(teacher.photo_path if teacher else None)
