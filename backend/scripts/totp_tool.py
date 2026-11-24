
from __future__ import annotations

import sys
import time

import pyotp
from sqlalchemy import func, select

from app.core.security import decrypt_secret
from app.db.session import SessionLocal
from app.models import Teacher, TeacherTOTP


def _teacher(db, code: str) -> Teacher:
    t = db.scalar(select(Teacher).where(func.upper(Teacher.employee_code) == code.upper()))
    if t is None:
        raise SystemExit(f"No teacher with ID {code}")
    return t


def main(argv: list[str]) -> None:
    if not argv or argv[0] not in ("status", "reset", "code"):
        raise SystemExit(__doc__)
    db = SessionLocal()
    try:
        if argv[0] == "status":
            for t in db.scalars(select(Teacher).order_by(Teacher.employee_code)):
                row = db.scalar(select(TeacherTOTP).where(TeacherTOTP.teacher_id == t.id))
                state = "enrolled" if row and row.is_confirmed else ("QR issued, not confirmed" if row else "not enrolled")
                print(f"{t.employee_code:6} {t.full_name:24} {state}")
        elif argv[0] == "reset":
            t = _teacher(db, argv[1])
            row = db.scalar(select(TeacherTOTP).where(TeacherTOTP.teacher_id == t.id))
            if row:
                db.delete(row)
                db.commit()
            print(f"Authenticator enrolment removed for {t.employee_code}. A new QR code will be shown at next login.")
        else:
            t = _teacher(db, argv[1])
            row = db.scalar(select(TeacherTOTP).where(TeacherTOTP.teacher_id == t.id))
            if row is None:
                raise SystemExit("Teacher has not started enrolment yet – sign in once to generate the QR code.")
            totp = pyotp.TOTP(decrypt_secret(row.secret_encrypted))
            remaining = 30 - int(time.time()) % 30
            print(f"{t.employee_code}: {totp.now()}  (valid for {remaining}s; each code can be used once)")
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1:])
