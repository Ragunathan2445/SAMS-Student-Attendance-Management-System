"""Application configuration loaded from environment variables / .env file."""
from __future__ import annotations

from datetime import time
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Sri Vidya Mandir – Attendance Management System"
    environment: str = "development"

    # --- Databases -------------------------------------------------------
    database_url: str = "postgresql+psycopg://sams_user:sams_password@localhost:5432/sams_db"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db_name: str = "sams_logs"

    # --- Secrets ---------------------------------------------------------
    secret_key: str = Field(default="change-me-in-env-file-please-0123456789abcdef", min_length=32)
    # Fernet key (urlsafe base64, 32 bytes) used to encrypt TOTP secrets at rest.
    totp_encryption_key: str = ""

    # --- HTTP ------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"  # comma separated
    session_cookie_name: str = "sams_session"
    session_cookie_secure: bool = False  # localhost demo runs over plain HTTP

    # --- Parent OTP -----------------------------------------------------
    otp_expiry_seconds: int = 300
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 30
    otp_max_resends: int = 3
    parent_session_minutes: int = 60
    enable_demo_otp_inbox: bool = True  # demo-only OTP viewer; never enable in production

    # --- Teacher session windows (school local time) ----------------------
    school_timezone: str = "Asia/Kolkata"
    school_open_time: time = time(8, 0)
    lunch_break_start: time = time(12, 30)
    lunch_break_end: time = time(13, 15)
    school_closing_time: time = time(16, 30)
    # When true, logins outside school hours receive a short "extended demo" session
    # so the demo can be shown in the evening. Set false to enforce school hours strictly.
    allow_off_hours_teacher_login: bool = True
    off_hours_session_minutes: int = 60
    login_challenge_minutes: int = 5

    # --- Rate limiting ----------------------------------------------------
    login_rate_limit_per_minute: int = 10

    # --- Uploads ---------------------------------------------------------
    upload_dir: Path = BACKEND_DIR / "uploads"
    max_photo_bytes: int = 2 * 1024 * 1024
    max_document_bytes: int = 5 * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [v.strip() for v in self.cors_origins.split(",") if v.strip()]

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.school_timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
