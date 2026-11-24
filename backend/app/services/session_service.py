"""Server-side sessions.

Sessions are opaque random tokens delivered in an HttpOnly cookie; only the SHA-256
hash is stored in PostgreSQL. Expiry is enforced on every request by the backend.

Teacher sessions follow the school day:
* morning   – login between school opening and the lunch break, expires at lunch break start
* afternoon – login from lunch break start until closing time, expires at closing time
* extended  – (optional, demo) login outside school hours, short fixed duration
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Forbidden
from app.core.security import hash_token, new_session_token
from app.models import UserAccount, UserSession
from app.utils.timeutils import now_local, utcnow


def _at(day_dt: datetime, t: time) -> datetime:
    return day_dt.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)


def teacher_session_window(now: datetime | None = None) -> tuple[str, datetime]:
    s = get_settings()
    now = now or now_local()
    opening, lunch, closing = _at(now, s.school_open_time), _at(now, s.lunch_break_start), _at(now, s.school_closing_time)
    if opening <= now < lunch:
        return "morning", lunch
    if lunch <= now < closing:
        return "afternoon", closing
    if not s.allow_off_hours_teacher_login:
        raise Forbidden(
            f"Teacher login is available during school hours "
            f"({s.school_open_time.strftime('%H:%M')}–{s.school_closing_time.strftime('%H:%M')}).",
            code="outside_school_hours",
        )
    expiry = now + timedelta(minutes=s.off_hours_session_minutes)
    if now < opening:
        expiry = min(expiry, opening)  # a fresh morning login is required once school opens
    return "extended", expiry


def create_session(
    db: Session,
    account: UserAccount,
    *,
    session_type: str,
    expires_at: datetime,
    ip: str | None,
    user_agent: str | None,
    verified_student_id: int | None = None,
) -> tuple[str, UserSession]:
    token = new_session_token()
    session = UserSession(
        account_id=account.id,
        token_hash=hash_token(token),
        session_type=session_type,
        verified_student_id=verified_student_id,
        expires_at=expires_at,
        last_seen_at=utcnow(),
        ip_address=ip,
        user_agent=(user_agent or "")[:255],
    )
    db.add(session)
    account.last_login_at = utcnow()
    db.flush()
    return token, session


def resolve_session(db: Session, token: str) -> UserSession | None:
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if session is None or session.revoked_at is not None:
        return None
    now = utcnow()
    if session.expires_at <= now:
        session.revoked_at = now
        session.revoke_reason = "expired"
        db.commit()
        return None
    if not session.account.is_active:
        return None
    if session.last_seen_at is None or now - session.last_seen_at > timedelta(seconds=60):
        session.last_seen_at = now
        db.commit()
    return session


def revoke(db: Session, session: UserSession, reason: str = "logout") -> None:
    session.revoked_at = utcnow()
    session.revoke_reason = reason
    db.commit()


def revoke_all_for_account(db: Session, account_id: int, reason: str) -> None:
    db.execute(
        update(UserSession)
        .where(UserSession.account_id == account_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow(), revoke_reason=reason)
    )
