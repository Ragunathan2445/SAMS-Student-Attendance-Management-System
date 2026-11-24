"""Add / update / deactivate students (class teachers, TOTP step-up, fully audited).

Students are never hard-deleted: deactivation keeps attendance, fee and academic history.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError, Conflict, NotFound
from app.models import (
    AcademicYear,
    FeeBalanceHistory,
    Parent,
    ParentStudent,
    Role,
    Section,
    Student,
    StudentChangeHistory,
    StudentFeeRecord,
    Teacher,
    UserAccount,
)
from app.repositories import students as student_repo
from app.utils.files import student_photo_url
from app.services import audit_service, fee_service, teacher_scope, totp_service
from app.utils import files
from app.utils.timeutils import today_local, utcnow

EDITABLE_FIELDS = ("full_name", "roll_number", "date_of_birth", "gender", "blood_group", "section_id",
                   "address", "contact_number", "uses_school_bus")
PARENT_FIELDS = ("parent_name", "parent_mobile", "parent_email")


_primary_parent = student_repo.primary_parent


def student_admin_dict(db: Session, s: Student) -> dict:
    parent = _primary_parent(db, s.id)
    return {
        "id": s.id, "full_name": s.full_name, "roll_number": s.roll_number, "admission_number": s.admission_number,
        "date_of_birth": s.date_of_birth.isoformat(), "gender": s.gender, "blood_group": s.blood_group,
        "section_id": s.section_id, "class_label": f"{s.section.school_class.name} – {s.section.name}",
        "address": s.address, "contact_number": s.contact_number, "uses_school_bus": s.uses_school_bus,
        "photo_url": student_photo_url(s), "status": s.status,
        "deactivation_reason": s.deactivation_reason,
        "deactivated_at": s.deactivated_at.isoformat() if s.deactivated_at else None,
        "parent_name": parent.full_name if parent else None,
        "parent_mobile": parent.mobile if parent else None,
        "parent_email": parent.email if parent else None,
    }


def list_students(db: Session, teacher: Teacher, ay: AcademicYear, section_id: int | None, q: str | None,
                  include_inactive: bool) -> list[dict]:
    allowed = teacher_scope.class_teacher_section_ids(db, teacher, ay)
    if section_id:
        teacher_scope.require_section(db, teacher, ay, section_id, class_teacher=True)
        allowed = {section_id}
    if not allowed:
        return []
    query = (select(Student).options(joinedload(Student.section).joinedload(Section.school_class))
             .where(Student.section_id.in_(allowed)))
    if not include_inactive:
        query = query.where(Student.status == "active")
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(func.lower(Student.full_name).like(like) | func.lower(Student.roll_number).like(like))
    rows = db.scalars(query.order_by(Student.section_id, Student.roll_number)).unique().all()
    return [student_admin_dict(db, s) for s in rows]


def _link_parent(db: Session, *, name: str, mobile: str, email: str, address: str | None, school_id: int) -> Parent:
    email = email.lower()
    by_mobile = db.scalar(select(Parent).where(Parent.mobile == mobile))
    by_email = db.scalar(select(Parent).where(Parent.email == email))
    if by_mobile and by_email and by_mobile.id == by_email.id:
        return by_mobile
    if by_mobile or by_email:
        raise Conflict("This mobile number or e-mail is already registered to a different parent record. "
                       "Use the same mobile and e-mail as the existing parent, or new ones.")
    role = db.scalar(select(Role).where(Role.code == "parent"))
    account = UserAccount(role_id=role.id, username=email, password_hash=None, is_active=True)
    db.add(account)
    db.flush()
    parent = Parent(school_id=school_id, user_account_id=account.id, full_name=name, relation_type="Guardian",
                    mobile=mobile, email=email, address=address)
    db.add(parent)
    db.flush()
    return parent


def _check_unique(db: Session, ay: AcademicYear, *, roll_number: str | None = None, admission_number: str | None = None,
                  exclude_id: int | None = None) -> None:
    if roll_number:
        q = select(Student.id).where(Student.academic_year_id == ay.id, func.upper(Student.roll_number) == roll_number.upper())
        if exclude_id:
            q = q.where(Student.id != exclude_id)
        if db.scalar(q):
            raise Conflict(f"Roll number {roll_number} is already in use this academic year.")
    if admission_number:
        q = select(Student.id).where(func.upper(Student.admission_number) == admission_number.upper())
        if exclude_id:
            q = q.where(Student.id != exclude_id)
        if db.scalar(q):
            raise Conflict(f"Admission number {admission_number} already exists.")


def _assign_fees(db: Session, student: Student, ay: AcademicYear, class_id: int) -> None:
    """Apply the school's predefined fee structures (teachers never enter amounts)."""
    seq, balance = fee_service.next_sequence(db, student.id, ay.id)
    today = today_local()
    if seq == 1:
        db.add(FeeBalanceHistory(student_id=student.id, academic_year_id=ay.id, sequence=seq, entry_date=today,
                                 entry_type="opening", description="Opening balance", debit=Decimal("0.00"),
                                 credit=Decimal("0.00"), balance_after=Decimal("0.00")))
        seq += 1
    for fs in fee_service.structures_for_class(db, ay.id, class_id):
        if fs.is_optional and not (fs.category == "bus" and student.uses_school_bus):
            continue
        record = StudentFeeRecord(student_id=student.id, academic_year_id=ay.id, fee_structure_id=fs.id,
                                  category=fs.category, description=fs.name, amount=fs.amount,
                                  charged_on=today, due_date=fs.due_date)
        db.add(record)
        db.flush()
        balance += fs.amount
        db.add(FeeBalanceHistory(student_id=student.id, academic_year_id=ay.id, sequence=seq, entry_date=today,
                                 entry_type="charge", description=f"{fs.name} charged", fee_record_id=record.id,
                                 debit=fs.amount, credit=Decimal("0.00"), balance_after=balance))
        seq += 1


def create_student(db: Session, teacher: Teacher, account_id: int, ay: AcademicYear, data, photo: UploadFile | None,
                   ip: str | None) -> dict:
    totp_service.require_valid_code(db, teacher, data.totp_code)
    section = teacher_scope.require_section(db, teacher, ay, data.section_id, class_teacher=True)
    if data.class_id and data.class_id != section.class_id:
        raise AppError("Selected section does not belong to the selected class.", code="class_section_mismatch")
    _check_unique(db, ay, roll_number=data.roll_number, admission_number=data.admission_number)
    if photo is None or not photo.filename:
        raise AppError("A student photograph is required.", code="photo_required")
    photo_path = files.save_photo(photo)

    student = Student(
        school_id=teacher.school_id, academic_year_id=ay.id, section_id=section.id,
        roll_number=data.roll_number.strip().upper(), admission_number=data.admission_number.strip().upper(),
        full_name=data.full_name.strip(), date_of_birth=data.date_of_birth, gender=data.gender,
        blood_group=data.blood_group, address=data.address, contact_number=data.contact_number,
        photo_path=photo_path, uses_school_bus=data.uses_school_bus, admission_date=today_local(), status="active",
    )
    db.add(student)
    db.flush()
    parent = _link_parent(db, name=data.parent_name.strip(), mobile=data.parent_mobile, email=data.parent_email,
                          address=data.address, school_id=teacher.school_id)
    db.add(ParentStudent(parent_id=parent.id, student_id=student.id, relationship_label="Parent", is_primary=True))
    _assign_fees(db, student, ay, section.class_id)
    snapshot = {f: {"old": None, "new": getattr(student, f)} for f in EDITABLE_FIELDS}
    snapshot.update({"parent_name": {"old": None, "new": parent.full_name},
                     "parent_mobile": {"old": None, "new": parent.mobile},
                     "parent_email": {"old": None, "new": parent.email}})
    db.add(StudentChangeHistory(student_id=student.id, action="create", changes=_json(snapshot), reason=data.reason,
                                performed_by_teacher_id=teacher.id, performed_by_account_id=account_id, totp_verified=True))
    audit_service.record(db, account_id=account_id, role="teacher", action="student.created", entity_type="student",
                         entity_id=student.id, details={"reason": data.reason, "section_id": section.id}, ip=ip)
    db.commit()
    audit_service.activity(account_id=account_id, role="teacher", activity_type="student_created",
                           description=f"Added student {student.full_name} ({student.roll_number})",
                           entity_type="student", entity_id=student.id)
    db.refresh(student)
    return student_admin_dict(db, student)


def _json(changes: dict) -> dict:
    return {k: {kk: (vv.isoformat() if isinstance(vv, date) else vv) for kk, vv in v.items()} for k, v in changes.items()}


def update_student(db: Session, teacher: Teacher, account_id: int, ay: AcademicYear, student_id: int, data,
                   photo: UploadFile | None, ip: str | None) -> dict:
    totp_service.require_valid_code(db, teacher, data.totp_code)
    student = teacher_scope.require_student(db, teacher, ay, student_id, class_teacher=True)
    if student.status != "active":
        raise AppError("Reactivate the student before editing their details.", code="student_inactive")
    changes: dict = {}
    if data.section_id and data.section_id != student.section_id:
        teacher_scope.require_section(db, teacher, ay, data.section_id, class_teacher=True)
    if data.roll_number and data.roll_number.upper() != student.roll_number:
        _check_unique(db, ay, roll_number=data.roll_number, exclude_id=student.id)
        data.roll_number = data.roll_number.upper()
    for field in EDITABLE_FIELDS:
        new = getattr(data, field, None)
        if new is not None and new != getattr(student, field):
            changes[field] = {"old": getattr(student, field), "new": new}
            setattr(student, field, new)
    if photo is not None and photo.filename:
        changes["photo"] = {"old": "previous photo", "new": "new photo uploaded"}
        student.photo_path = files.save_photo(photo)

    parent = _primary_parent(db, student.id)
    if parent:
        for field, attr in (("parent_name", "full_name"), ("parent_mobile", "mobile"), ("parent_email", "email")):
            new = getattr(data, field, None)
            if new is None:
                continue
            new = new.lower() if attr == "email" else new
            if new != getattr(parent, attr):
                if attr in ("mobile", "email"):
                    clash = db.scalar(select(Parent.id).where(getattr(Parent, attr) == new, Parent.id != parent.id))
                    if clash:
                        raise Conflict(f"That parent {attr} is already registered to another parent.")
                changes[field] = {"old": getattr(parent, attr), "new": new}
                setattr(parent, attr, new)
                if attr == "email" and parent.user_account_id:
                    db.get(UserAccount, parent.user_account_id).username = new
    if not changes:
        raise AppError("No changes to save.", code="no_change")
    db.add(StudentChangeHistory(student_id=student.id, action="update", changes=_json(changes), reason=data.reason,
                                performed_by_teacher_id=teacher.id, performed_by_account_id=account_id, totp_verified=True))
    audit_service.record(db, account_id=account_id, role="teacher", action="student.updated", entity_type="student",
                         entity_id=student.id, details={"fields": list(changes), "reason": data.reason}, ip=ip)
    db.commit()
    db.refresh(student)
    return student_admin_dict(db, student)


def set_active(db: Session, teacher: Teacher, account_id: int, ay: AcademicYear, student_id: int, *, active: bool,
               reason: str, totp_code: str, ip: str | None) -> dict:
    totp_service.require_valid_code(db, teacher, totp_code)
    student = teacher_scope.require_student(db, teacher, ay, student_id, class_teacher=True)
    target = "active" if active else "inactive"
    if student.status == target:
        raise AppError(f"Student is already {target}.", code="no_change")
    old = student.status
    student.status = target
    if active:
        student.deactivated_at = student.deactivation_reason = student.deactivated_by_teacher_id = None
    else:
        student.deactivated_at, student.deactivation_reason, student.deactivated_by_teacher_id = utcnow(), reason, teacher.id
    action = "reactivate" if active else "deactivate"
    db.add(StudentChangeHistory(student_id=student.id, action=action, changes={"status": {"old": old, "new": target}},
                                reason=reason, performed_by_teacher_id=teacher.id, performed_by_account_id=account_id,
                                totp_verified=True))
    audit_service.record(db, account_id=account_id, role="teacher", action=f"student.{action}d", entity_type="student",
                         entity_id=student.id, details={"reason": reason}, ip=ip)
    db.commit()
    audit_service.activity(account_id=account_id, role="teacher", activity_type=f"student_{action}d",
                           description=f"{action.title()}d student {student.full_name}", entity_type="student", entity_id=student.id)
    db.refresh(student)
    return student_admin_dict(db, student)


def change_history(db: Session, teacher: Teacher, ay: AcademicYear, student_id: int) -> list[dict]:
    teacher_scope.require_student(db, teacher, ay, student_id, class_teacher=True)
    rows = db.scalars(select(StudentChangeHistory).where(StudentChangeHistory.student_id == student_id)
                      .order_by(StudentChangeHistory.performed_at.desc())).all()
    return [{"id": r.id, "action": r.action, "changes": r.changes, "reason": r.reason,
             "performed_by": db.get(Teacher, r.performed_by_teacher_id).full_name, "totp_verified": r.totp_verified,
             "performed_at": r.performed_at.isoformat()} for r in rows]


def directory(db: Session, teacher: Teacher, ay: AcademicYear, section_id: int | None, q: str | None) -> list[dict]:
    """Emergency contact view – deliberately limited fields."""
    allowed = teacher_scope.authorised_section_ids(db, teacher, ay)
    if section_id:
        teacher_scope.require_section(db, teacher, ay, section_id)
        allowed = {section_id}
    if not allowed:
        return []
    query = (select(Student).options(joinedload(Student.section).joinedload(Section.school_class))
             .where(Student.section_id.in_(allowed), Student.status == "active"))
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(func.lower(Student.full_name).like(like) | func.lower(Student.roll_number).like(like))
    out = []
    for s in db.scalars(query.order_by(Student.section_id, Student.roll_number)).unique():
        parent = _primary_parent(db, s.id)
        out.append({
            "id": s.id, "full_name": s.full_name, "roll_number": s.roll_number,
            "class_label": f"{s.section.school_class.name} – {s.section.name}",
            "photo_url": student_photo_url(s),
            "parent_name": parent.full_name if parent else None,
            "parent_mobile": parent.mobile if parent else None,
            "parent_email": parent.email if parent else None,
            "address": s.address,
        })
    return out


def get_student_or_404(db: Session, student_id: int) -> Student:
    s = db.get(Student, student_id)
    if s is None:
        raise NotFound("Student not found.")
    return s
