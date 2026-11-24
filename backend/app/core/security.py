"""Cryptographic helpers: password hashing, OTP hashing, opaque session tokens,
short-lived login challenge tokens and at-rest encryption of TOTP secrets."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import get_settings

_password_hash = PasswordHash((Argon2Hasher(),))


# --- Passwords --------------------------------------------------------------
def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        # Still spend time hashing to reduce timing differences.
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    try:
        return _password_hash.verify(password, password_hash)
    except Exception:
        return False


_DUMMY_HASH = _password_hash.hash("dummy-password-for-timing")


# --- OTP --------------------------------------------------------------------
def generate_otp() -> str:
    """Cryptographically random 6-digit OTP (never a fixed value)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp_id: str, code: str) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, f"{otp_id}:{code}".encode(), hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# --- Session tokens -----------------------------------------------------------
def new_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# --- Login challenge (between password and TOTP step) ---------------------------
CHALLENGE_ALG = "HS256"


def create_challenge_token(account_id: int, purpose: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account_id),
        "purpose": purpose,  # totp | enroll
        "iat": now,
        "exp": now + timedelta(minutes=settings.login_challenge_minutes),
        "jti": secrets.token_hex(8),
        "typ": "teacher-login-challenge",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=CHALLENGE_ALG)


def decode_challenge_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[CHALLENGE_ALG])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "teacher-login-challenge":
        return None
    return payload


# --- TOTP secret encryption ----------------------------------------------------
def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.totp_encryption_key.strip()
    if not key:
        # Derive a stable key from SECRET_KEY when a dedicated key is not configured.
        key = base64.urlsafe_b64encode(hashlib.sha256(("totp:" + settings.secret_key).encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:  # pragma: no cover
        raise RuntimeError("TOTP secret could not be decrypted – check TOTP_ENCRYPTION_KEY") from exc
