"""Parent OTP login and teacher password + TOTP login."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, NotAuthenticated, TooManyRequests
from app.core.security import (
    constant_time_equals,
    create_challenge_token,
    decode_challenge_token,
    generate_otp,
    hash_otp,
    verify_password,
)
from app.models import Parent, ParentOTP, ParentStudent, Student, Teacher, UserAccount
from app.services import audit_service, notification_service, session_service, totp_service
from app.utils.timeutils import utcnow

PARENT_MISMATCH = "The details you entered do not match our records. Please check and try again."
OTP_INVALID = "This code is invalid or has expired. Please request a new code."
TEACHER_INVALID = "Invalid Teacher ID / email or password."
MAX_PASSWORD_FAILURES = 5
LOCK_MINUTES = 15


@dataclass
class LoginResult:
    token: str
    account: UserAccount
    session_type: str
    expires_at: object


# ============================================================== Parent: OTP
def _normalise_identifier(identifier: str) -> tuple[str, str]:
    identifier = identifier.strip()
    if "@" in identifier:
        return "email", identifier.lower()
    digits = re.sub(r"\D", "", identifier)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return "sms", digits


def request_parent_otp(db: Session, identifier: str, roll_number: str, ip: str | None) -> dict:
    settings = get_settings()
    channel, value = _normalise_identifier(identifier)
    parent_q = select(Parent).where(Parent.email == value if channel == "email" else Parent.mobile == value)
    parent = db.scalar(parent_q)
    student = None
    if parent:
        student = db.scalar(
            select(Student)
            .join(ParentStudent, ParentStudent.student_id == Student.id)
            .where(
                ParentStudent.parent_id == parent.id,
                func.upper(Student.roll_number) == roll_number.strip().upper(),
                Student.status == "active",
            )
        )
    if not parent or not student:
        audit_service.record(
            db, account_id=None, role="parent", action="parent.otp.denied",
            details={"channel": channel}, ip=ip,
        )
        db.commit()
        raise NotAuthenticated(PARENT_MISMATCH, code="details_mismatch")

    now = utcnow()
    # Only one live OTP per parent: invalidate earlier ones.
    db.execute(
        update(ParentOTP)
        .where(ParentOTP.parent_id == parent.id, ParentOTP.consumed_at.is_(None), ParentOTP.invalidated_at.is_(None))
        .values(invalidated_at=now)
    )
    otp_id = uuid.uuid4()
    code = generate_otp()
    destination = parent.email if channel == "email" else parent.mobile
    masked = (
        notification_service.mask_email(destination)
        if channel == "email"
        else notification_service.mask_mobile(destination)
    )
    otp = ParentOTP(
        id=otp_id,
        parent_id=parent.id,
        student_id=student.id,
        channel=channel,
        destination_masked=masked,
        code_hash=hash_otp(str(otp_id), code),
        expires_at=now + timedelta(seconds=settings.otp_expiry_seconds),
        attempts=0,
        max_attempts=settings.otp_max_attempts,
        resend_count=0,
        last_sent_at=now,
        request_ip=ip,
    )
    db.add(otp)
    audit_service.record(
        db, account_id=parent.user_account_id, role="parent", action="parent.otp.issued",
        entity_type="parent_otp", entity_id=otp_id, details={"channel": channel}, ip=ip,
    )
    db.commit()
    notification_service.deliver_otp(
        request_id=str(otp_id), parent_id=parent.id, channel=channel, destination=destination,
        masked=masked, code=code, expires_at=otp.expires_at,
    )
    return _otp_response(otp)


def _otp_response(otp: ParentOTP) -> dict:
    settings = get_settings()
    now = utcnow()
    return {
        "request_id": str(otp.id),
        "channel": otp.channel,
        "destination": otp.destination_masked,
        "expires_in": max(int((otp.expires_at - now).total_seconds()), 0),
        "resend_after": max(settings.otp_resend_cooldown_seconds - int((now - otp.last_sent_at).total_seconds()), 0),
        "attempts_remaining": max(otp.max_attempts - otp.attempts, 0),
        "resends_remaining": max(settings.otp_max_resends - otp.resend_count, 0),
        "demo_inbox_enabled": settings.enable_demo_otp_inbox,
    }


def _get_live_otp(db: Session, request_id: str) -> ParentOTP:
    try:
        otp_uuid = uuid.UUID(request_id)
    except ValueError:
        raise NotAuthenticated(OTP_INVALID, code="otp_invalid") from None
    otp = db.get(ParentOTP, otp_uuid, with_for_update=True)
    if otp is None or otp.consumed_at or otp.invalidated_at:
        raise NotAuthenticated(OTP_INVALID, code="otp_invalid")
    return otp


def resend_parent_otp(db: Session, request_id: str, ip: str | None) -> dict:
    settings = get_settings()
    otp = _get_live_otp(db, request_id)
    now = utcnow()
    wait = settings.otp_resend_cooldown_seconds - int((now - otp.last_sent_at).total_seconds())
    if wait > 0:
        raise TooManyRequests(f"Please wait {wait} seconds before requesting a new code.")
    if otp.resend_count >= settings.otp_max_resends:
        otp.invalidated_at = now
        db.commit()
        raise TooManyRequests("Resend limit reached. Please start the login again.")
    code = generate_otp()
    otp.code_hash = hash_otp(str(otp.id), code)
    otp.expires_at = now + timedelta(seconds=settings.otp_expiry_seconds)
    otp.attempts = 0
    otp.resend_count += 1
    otp.last_sent_at = now
    parent = db.get(Parent, otp.parent_id)
    audit_service.record(
        db, account_id=parent.user_account_id, role="parent", action="parent.otp.resent",
        entity_type="parent_otp", entity_id=otp.id, ip=ip,
    )
    db.commit()
    destination = parent.email if otp.channel == "email" else parent.mobile
    notification_service.deliver_otp(
        request_id=str(otp.id), parent_id=parent.id, channel=otp.channel, destination=destination,
        masked=otp.destination_masked, code=code, expires_at=otp.expires_at,
    )
    return _otp_response(otp)


def verify_parent_otp(db: Session, request_id: str, code: str, ip: str | None, user_agent: str | None) -> LoginResult:
    settings = get_settings()
    otp = _get_live_otp(db, request_id)
    now = utcnow()
    if otp.expires_at <= now:
        otp.invalidated_at = now
        db.commit()
        raise NotAuthenticated("This code has expired. Please request a new code.", code="otp_expired")
    if otp.attempts >= otp.max_attempts:
        otp.invalidated_at = now
        db.commit()
        raise TooManyRequests("Too many incorrect attempts. Please start the login again.")

    if not constant_time_equals(otp.code_hash, hash_otp(str(otp.id), code.strip())):
        otp.attempts += 1
        remaining = otp.max_attempts - otp.attempts
        if remaining <= 0:
            otp.invalidated_at = now
        audit_service.record(
            db, account_id=None, role="parent", action="parent.otp.failed",
            entity_type="parent_otp", entity_id=otp.id, details={"remaining": remaining}, ip=ip,
        )
        db.commit()
        if remaining <= 0:
            raise TooManyRequests("Too many incorrect attempts. Please start the login again.")
        raise NotAuthenticated(f"Incorrect code. {remaining} attempt(s) remaining.", code="otp_incorrect")

    otp.consumed_at = now  # single use
    notification_service.discard(str(otp.id))
    parent = db.get(Parent, otp.parent_id)
    account = db.get(UserAccount, parent.user_account_id) if parent.user_account_id else None
    if account is None or not account.is_active:
        db.commit()
        raise NotAuthenticated(PARENT_MISMATCH, code="details_mismatch")
    token, session = session_service.create_session(
        db, account, session_type="parent",
        expires_at=now + timedelta(minutes=settings.parent_session_minutes),
        ip=ip, user_agent=user_agent, verified_student_id=otp.student_id,
    )
    audit_service.record(
        db, account_id=account.id, role="parent", action="parent.login",
        entity_type="session", entity_id=session.id, ip=ip,
    )
    db.commit()
    audit_service.activity(account_id=account.id, role="parent", activity_type="login",
                           description=f"{parent.full_name} signed in to the parent portal")
    return LoginResult(token, account, "parent", session.expires_at)


# ============================================================== Teacher: password + TOTP
def _find_teacher(db: Session, identifier: str) -> Teacher | None:
    identifier = identifier.strip()
    if "@" in identifier:
        return db.scalar(select(Teacher).where(func.lower(Teacher.email) == identifier.lower()))
    return db.scalar(select(Teacher).where(func.upper(Teacher.employee_code) == identifier.upper()))


def teacher_password_step(db: Session, identifier: str, password: str, ip: str | None) -> dict:
    teacher = _find_teacher(db, identifier)
    account = db.get(UserAccount, teacher.user_account_id) if teacher and teacher.user_account_id else None
    now = utcnow()
    if account and account.locked_until and account.locked_until > now:
        minutes = int((account.locked_until - now).total_seconds() // 60) + 1
        raise TooManyRequests(f"Account temporarily locked after repeated failures. Try again in {minutes} minute(s).")

    if not verify_password(password, account.password_hash if account else None) or not teacher.is_active:
        if account:
            account.failed_login_count += 1
            if account.failed_login_count >= MAX_PASSWORD_FAILURES:
                account.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                account.failed_login_count = 0
        audit_service.record(db, account_id=account.id if account else None, role="teacher",
                             action="teacher.password.failed", ip=ip)
        db.commit()
        raise NotAuthenticated(TEACHER_INVALID, code="invalid_credentials")

    # Fail early if the school-hours policy would refuse the session anyway.
    session_type, expires_at = session_service.teacher_session_window()
    account.failed_login_count = 0
    account.locked_until = None
    row = totp_service.get_totp_row(db, teacher.id)
    purpose = "totp" if row and row.is_confirmed else "enroll"
    db.commit()
    return {
        "challenge_token": create_challenge_token(account.id, purpose),
        "next_step": purpose,
        "teacher_name": teacher.full_name,
        "session_type": session_type,
        "session_expires_at": expires_at.isoformat(),
    }


def _teacher_from_challenge(db: Session, challenge_token: str, expected: tuple[str, ...]) -> tuple[Teacher, UserAccount, str]:
    payload = decode_challenge_token(challenge_token)
    if not payload or payload.get("purpose") not in expected:
        raise NotAuthenticated("Your login step has expired. Please sign in again.", code="challenge_expired")
    account = db.get(UserAccount, int(payload["sub"]))
    teacher = db.scalar(select(Teacher).where(Teacher.user_account_id == account.id)) if account else None
    if not account or not teacher or not account.is_active or not teacher.is_active:
        raise NotAuthenticated("Your login step has expired. Please sign in again.", code="challenge_expired")
    return teacher, account, payload["purpose"]


def teacher_totp_setup(db: Session, challenge_token: str) -> dict:
    teacher, _, _ = _teacher_from_challenge(db, challenge_token, ("enroll",))
    qr = totp_service.start_enrollment(db, teacher)
    db.commit()
    return {"qr_code": qr, "issuer": totp_service.ISSUER, "account_label": teacher.employee_code}


def teacher_totp_verify(db: Session, challenge_token: str, code: str, ip: str | None, user_agent: str | None) -> LoginResult:
    teacher, account, purpose = _teacher_from_challenge(db, challenge_token, ("totp", "enroll"))
    row = totp_service.get_totp_row(db, teacher.id)
    if purpose == "enroll" and row is None:
        raise AppError("Scan the QR code first.", code="enrollment_not_started")
    if purpose == "totp" and (row is None or not row.is_confirmed):
        raise NotAuthenticated("Authenticator is not set up. Please sign in again.", code="challenge_expired")
    if not totp_service.verify_code(db, row, code.strip()):
        audit_service.record(db, account_id=account.id, role="teacher", action="teacher.totp.failed", ip=ip)
        db.commit()
        raise NotAuthenticated("Invalid or already-used authenticator code.", code="totp_invalid")
    if purpose == "enroll":
        totp_service.confirm_enrollment(row)
        audit_service.record(db, account_id=account.id, role="teacher", action="teacher.totp.enrolled",
                             entity_type="teacher", entity_id=teacher.id, ip=ip)

    session_type, expires_at = session_service.teacher_session_window()
    token, session = session_service.create_session(
        db, account, session_type=session_type, expires_at=expires_at, ip=ip, user_agent=user_agent
    )
    audit_service.record(db, account_id=account.id, role="teacher", action="teacher.login",
                         entity_type="session", entity_id=session.id, details={"session_type": session_type}, ip=ip)
    db.commit()
    audit_service.activity(account_id=account.id, role="teacher", activity_type="login",
                           description=f"{teacher.full_name} signed in ({session_type} session)")
    return LoginResult(token, account, session_type, expires_at)
