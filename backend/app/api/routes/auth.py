from __future__ import annotations

from datetime import timezone

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, client_ip, get_current_user
from app.core.config import get_settings
from app.core.errors import NotFound
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.auth import ChallengeOnly, OtpResend, OtpVerify, ParentOtpRequest, TeacherLogin, TotpVerify
from app.services import audit_service, auth_service, notification_service, session_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_cookie(response: Response, token: str, expires_at) -> None:
    s = get_settings()
    response.set_cookie(
        s.session_cookie_name, token, httponly=True, secure=s.session_cookie_secure, samesite="lax",
        path="/", expires=expires_at.astimezone(timezone.utc),
    )


def _rate(request: Request, scope: str) -> None:
    limiter.hit(f"{scope}:{client_ip(request)}", get_settings().login_rate_limit_per_minute)


# ----------------------------------------------------------------- parent
@router.post("/parent/request-otp")
def parent_request_otp(body: ParentOtpRequest, request: Request, db: Session = Depends(get_db)):
    _rate(request, "parent-otp")
    return auth_service.request_parent_otp(db, body.identifier, body.roll_number, client_ip(request))


@router.post("/parent/resend-otp")
def parent_resend_otp(body: OtpResend, request: Request, db: Session = Depends(get_db)):
    _rate(request, "parent-otp")
    return auth_service.resend_parent_otp(db, body.request_id, client_ip(request))


@router.post("/parent/verify-otp")
def parent_verify_otp(body: OtpVerify, request: Request, response: Response, db: Session = Depends(get_db)):
    _rate(request, "parent-verify")
    result = auth_service.verify_parent_otp(db, body.request_id, body.code, client_ip(request),
                                            request.headers.get("user-agent"))
    _set_cookie(response, result.token, result.expires_at)
    return {"role": "parent", "session_type": result.session_type, "expires_at": result.expires_at.isoformat()}


@router.get("/parent/demo-inbox/{request_id}", tags=["Demo only"])
def parent_demo_inbox(request_id: str):
    """DEMO ONLY – shows the simulated SMS/e-mail for an OTP request the caller already holds.
    Disabled unless ENABLE_DEMO_OTP_INBOX=true. Never enable in a live deployment."""
    if not get_settings().enable_demo_otp_inbox:
        raise NotFound("Not available.")
    msg = notification_service.read_demo_inbox(request_id)
    if msg is None:
        raise NotFound("No message for this request (it may have expired or been used).")
    return {"channel": msg.channel, "destination": msg.destination, "code": msg.code,
            "expires_at": msg.expires_at.isoformat(), "notice": "Demo inbox – simulates the SMS/e-mail delivery."}


# ----------------------------------------------------------------- teacher
@router.post("/teacher/login")
def teacher_login(body: TeacherLogin, request: Request, db: Session = Depends(get_db)):
    _rate(request, "teacher-login")
    return auth_service.teacher_password_step(db, body.identifier, body.password, client_ip(request))


@router.post("/teacher/totp/setup")
def teacher_totp_setup(body: ChallengeOnly, request: Request, db: Session = Depends(get_db)):
    _rate(request, "teacher-totp")
    return auth_service.teacher_totp_setup(db, body.challenge_token)


@router.post("/teacher/totp/verify")
def teacher_totp_verify(body: TotpVerify, request: Request, response: Response, db: Session = Depends(get_db)):
    _rate(request, "teacher-totp")
    result = auth_service.teacher_totp_verify(db, body.challenge_token, body.code, client_ip(request),
                                              request.headers.get("user-agent"))
    _set_cookie(response, result.token, result.expires_at)
    return {"role": "teacher", "session_type": result.session_type, "expires_at": result.expires_at.isoformat()}


# ----------------------------------------------------------------- common
@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)):
    s = get_settings()
    data = {
        "role": user.role,
        "session": {"type": user.session.session_type, "expires_at": user.session.expires_at.isoformat(),
                    "created_at": user.session.created_at.isoformat()},
    }
    if user.parent:
        data["name"] = user.parent.full_name
        data["parent_id"] = user.parent.id
    if user.teacher:
        data["name"] = user.teacher.full_name
        data["teacher_id"] = user.teacher.id
        data["employee_code"] = user.teacher.employee_code
        data["schedule"] = {"open": s.school_open_time.strftime("%H:%M"), "lunch": s.lunch_break_start.strftime("%H:%M"),
                            "lunch_end": s.lunch_break_end.strftime("%H:%M"), "closing": s.school_closing_time.strftime("%H:%M")}
    return data


@router.post("/logout")
def logout(response: Response, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    session_service.revoke(db, user.session, "logout")
    audit_service.record(db, account_id=user.account_id, role=user.role, action=f"{user.role}.logout",
                         entity_type="session", entity_id=user.session.id)
    db.commit()
    audit_service.activity(account_id=user.account_id, role=user.role, activity_type="logout", description="Signed out")
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    return {"message": "Signed out."}
