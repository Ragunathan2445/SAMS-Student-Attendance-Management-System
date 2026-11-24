"""Development-only OTP delivery.

No real SMS/e-mail is sent. The OTP is printed to the backend console and – when
ENABLE_DEMO_OTP_INBOX=true – kept in a short-lived in-memory "demo inbox" that the
OTP screen can display (clearly labelled DEMO). The notification metadata (never the
code itself) is stored in MongoDB ``notification_history``.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db import mongo

logger = logging.getLogger("sams.otp")


@dataclass
class DemoMessage:
    code: str
    destination: str
    channel: str
    expires_at: datetime


_inbox: dict[str, DemoMessage] = {}
_lock = threading.Lock()


def mask_mobile(mobile: str) -> str:
    return f"{'*' * max(len(mobile) - 4, 0)}{mobile[-4:]}"


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}{'*' * max(len(local) - len(visible), 1)}@{domain}"


def deliver_otp(*, request_id: str, parent_id: int, channel: str, destination: str, masked: str, code: str,
                expires_at: datetime) -> None:
    banner = "=" * 64
    print(
        f"\n{banner}\n[DEMO OTP] {code}  ->  {channel.upper()} {masked}  (request {request_id[:8]}…, "
        f"expires {expires_at.astimezone().strftime('%H:%M:%S')})\n{banner}\n",
        flush=True,
    )
    if get_settings().enable_demo_otp_inbox:
        with _lock:
            _purge()
            _inbox[request_id] = DemoMessage(code, masked, channel, expires_at)
    mongo.log_notification(
        recipient_id=parent_id,
        recipient_role="parent",
        channel=channel,
        destination=masked,
        subject="Parent portal login OTP",
        body="One-time password issued (code not stored).",
    )


def read_demo_inbox(request_id: str) -> DemoMessage | None:
    with _lock:
        _purge()
        return _inbox.get(request_id)


def discard(request_id: str) -> None:
    with _lock:
        _inbox.pop(request_id, None)


def _purge() -> None:
    now = datetime.now(timezone.utc)
    for key in [k for k, v in _inbox.items() if v.expires_at <= now]:
        _inbox.pop(key, None)
