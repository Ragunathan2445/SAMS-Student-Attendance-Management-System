"""Google Authenticator compatible TOTP (RFC 6238) using pyotp, with replay protection."""
from __future__ import annotations

import base64
import io
import time

import pyotp
import qrcode
from qrcode.image.pil import PilImage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, Conflict
from app.core.security import constant_time_equals, decrypt_secret, encrypt_secret
from app.models import Teacher, TeacherTOTP
from app.utils.timeutils import utcnow

ISSUER = "Sri Vidya Mandir SAMS"
STEP = 30


def get_totp_row(db: Session, teacher_id: int) -> TeacherTOTP | None:
    return db.scalar(select(TeacherTOTP).where(TeacherTOTP.teacher_id == teacher_id))


def start_enrollment(db: Session, teacher: Teacher) -> str:
    """Create (or reuse) an unconfirmed secret and return a QR code PNG as a data URI.
    The QR image is the only place the secret ever leaves the server."""
    row = get_totp_row(db, teacher.id)
    if row and row.is_confirmed:
        raise Conflict("Google Authenticator is already set up for this account.")
    if row is None:
        row = TeacherTOTP(teacher_id=teacher.id, secret_encrypted=encrypt_secret(pyotp.random_base32()))
        db.add(row)
        db.flush()
    secret = decrypt_secret(row.secret_encrypted)
    uri = pyotp.TOTP(secret).provisioning_uri(name=f"{teacher.employee_code} ({teacher.email})", issuer_name=ISSUER)
    img = qrcode.make(uri, image_factory=PilImage, box_size=8, border=2)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def verify_code(db: Session, row: TeacherTOTP | None, code: str) -> bool:
    """Accepts the current code (±1 step for clock drift). A code is usable only once."""
    if row is None or not code or not code.isdigit() or len(code) != 6:
        return False
    totp = pyotp.TOTP(decrypt_secret(row.secret_encrypted))
    current = int(time.time()) // STEP
    for counter in (current - 1, current, current + 1):
        if constant_time_equals(totp.at(counter * STEP), code):
            if row.last_used_counter is not None and counter <= row.last_used_counter:
                return False  # replayed code
            row.last_used_counter = counter
            return True
    return False


def confirm_enrollment(row: TeacherTOTP) -> None:
    row.is_confirmed = True
    row.confirmed_at = utcnow()


def require_valid_code(db: Session, teacher: Teacher, code: str) -> None:
    """Step-up verification for sensitive operations (student add/update/deactivate)."""
    row = get_totp_row(db, teacher.id)
    if row is None or not row.is_confirmed:
        raise AppError("Google Authenticator is not set up for this account.", status_code=403, code="totp_required")
    if not verify_code(db, row, code):
        raise AppError(
            "Invalid or already-used authenticator code. Wait for the next code and try again.",
            status_code=403,
            code="totp_invalid",
        )
