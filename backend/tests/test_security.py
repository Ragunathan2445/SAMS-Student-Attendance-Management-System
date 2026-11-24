from datetime import datetime, time
from types import SimpleNamespace as NS
from zoneinfo import ZoneInfo

import pyotp
import pytest

from app.core import security
from app.core.config import get_settings
from app.core.errors import Forbidden
from app.services import session_service, totp_service

IST = ZoneInfo("Asia/Kolkata")


def test_otp_is_random_six_digits():
    codes = {security.generate_otp() for _ in range(200)}
    assert all(len(c) == 6 and c.isdigit() for c in codes)
    assert len(codes) > 150  # never a fixed code


def test_otp_hash_is_bound_to_request():
    assert security.hash_otp("a", "123456") != security.hash_otp("b", "123456")
    assert "123456" not in security.hash_otp("a", "123456")


def test_password_hashing():
    h = security.hash_password("Teacher@2026")
    assert h.startswith("$argon2")
    assert security.verify_password("Teacher@2026", h)
    assert not security.verify_password("wrong", h)
    assert not security.verify_password("x", None)


def test_challenge_token_roundtrip_and_tamper():
    token = security.create_challenge_token(7, "totp")
    assert security.decode_challenge_token(token)["sub"] == "7"
    assert security.decode_challenge_token(token[:-2] + "xx") is None


def test_secret_encryption_roundtrip():
    enc = security.encrypt_secret("JBSWY3DPEHPK3PXP")
    assert "JBSWY3DPEHPK3PXP" not in enc
    assert security.decrypt_secret(enc) == "JBSWY3DPEHPK3PXP"


@pytest.mark.parametrize("hour,minute,expected,expiry", [
    (9, 0, "morning", time(12, 30)),
    (12, 45, "afternoon", time(16, 30)),
    (15, 0, "afternoon", time(16, 30)),
])
def test_teacher_session_windows(hour, minute, expected, expiry):
    kind, expires = session_service.teacher_session_window(datetime(2026, 11, 20, hour, minute, tzinfo=IST))
    assert kind == expected and expires.time() == expiry


def test_off_hours_policy(monkeypatch):
    now = datetime(2026, 11, 20, 19, 0, tzinfo=IST)
    kind, _ = session_service.teacher_session_window(now)
    assert kind == "extended"
    monkeypatch.setattr(get_settings(), "allow_off_hours_teacher_login", False)
    with pytest.raises(Forbidden):
        session_service.teacher_session_window(now)


def test_totp_code_cannot_be_replayed():
    secret = pyotp.random_base32()
    row = NS(secret_encrypted=security.encrypt_secret(secret), last_used_counter=None)
    code = pyotp.TOTP(secret).now()
    assert totp_service.verify_code(None, row, code)
    assert not totp_service.verify_code(None, row, code)      # same code again -> rejected
    assert not totp_service.verify_code(None, row, "000000" if code != "000000" else "111111")
