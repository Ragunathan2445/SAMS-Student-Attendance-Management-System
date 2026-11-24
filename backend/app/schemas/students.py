"""Student management payloads (sent as multipart form fields because of the photo)."""
from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.utils.timeutils import today_local

Gender = Literal["Male", "Female", "Other"]
BloodGroup = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
_NAME = re.compile(r"^[A-Za-z][A-Za-z .'\-]{1,149}$")
_MOBILE = re.compile(r"^[6-9]\d{9}$")
_CODE = re.compile(r"^[A-Za-z0-9\-/]{1,30}$")
_TOTP = re.compile(r"^\d{6}$")


def _clean_mobile(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    digits = re.sub(r"\D", "", v)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if not _MOBILE.fullmatch(digits):
        raise ValueError("Enter a valid 10-digit Indian mobile number")
    return digits


class _Common(BaseModel):
    totp_code: str
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("totp_code")
    @classmethod
    def _totp(cls, v: str) -> str:
        v = v.strip()
        if not _TOTP.fullmatch(v):
            raise ValueError("Authenticator code must be 6 digits")
        return v


class StudentCreate(_Common):
    full_name: str
    roll_number: str
    admission_number: str
    date_of_birth: date
    gender: Gender
    blood_group: BloodGroup | None = None
    class_id: int | None = None
    section_id: int = Field(gt=0)
    parent_name: str
    parent_mobile: str
    parent_email: EmailStr
    address: str = Field(min_length=5, max_length=500)
    contact_number: str | None = None
    uses_school_bus: bool = False
    reason: str = Field(default="New admission", min_length=5, max_length=500)

    @field_validator("full_name", "parent_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not _NAME.fullmatch(v):
            raise ValueError("Name may contain letters, spaces, '.', ''' and '-' only")
        return v

    @field_validator("roll_number", "admission_number")
    @classmethod
    def _code(cls, v: str) -> str:
        v = v.strip()
        if not _CODE.fullmatch(v):
            raise ValueError("Use letters, digits, '-' or '/' only")
        return v

    @field_validator("parent_mobile")
    @classmethod
    def _pm(cls, v: str) -> str:
        cleaned = _clean_mobile(v)
        if not cleaned:
            raise ValueError("Parent mobile number is required")
        return cleaned

    @field_validator("contact_number")
    @classmethod
    def _cm(cls, v: str | None) -> str | None:
        return _clean_mobile(v)

    @model_validator(mode="after")
    def _dob(self):
        today = today_local()
        age = (today - self.date_of_birth).days / 365.25
        if not 3 <= age <= 20:
            raise ValueError("Date of birth must give an age between 3 and 20 years")
        return self


class StudentUpdate(_Common):
    full_name: str | None = None
    roll_number: str | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    blood_group: BloodGroup | None = None
    section_id: int | None = Field(default=None, gt=0)
    address: str | None = Field(default=None, min_length=5, max_length=500)
    contact_number: str | None = None
    uses_school_bus: bool | None = None
    parent_name: str | None = None
    parent_mobile: str | None = None
    parent_email: EmailStr | None = None

    @field_validator("full_name", "parent_name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = " ".join(v.split())
        if not _NAME.fullmatch(v):
            raise ValueError("Name may contain letters, spaces, '.', ''' and '-' only")
        return v

    @field_validator("roll_number")
    @classmethod
    def _code(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not _CODE.fullmatch(v):
            raise ValueError("Use letters, digits, '-' or '/' only")
        return v

    @field_validator("parent_mobile", "contact_number")
    @classmethod
    def _mob(cls, v: str | None) -> str | None:
        return _clean_mobile(v)


class StatusChange(_Common):
    confirm: bool

    @model_validator(mode="after")
    def _confirmed(self):
        if not self.confirm:
            raise ValueError("Please confirm this action")
        return self
