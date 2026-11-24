from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

_OTP = re.compile(r"^\d{6}$")


class ParentOtpRequest(BaseModel):
    identifier: str = Field(min_length=5, max_length=255, description="Registered mobile number or e-mail")
    roll_number: str = Field(min_length=1, max_length=20)

    @field_validator("identifier")
    @classmethod
    def _identifier(cls, v: str) -> str:
        v = v.strip()
        if "@" in v:
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
                raise ValueError("Enter a valid e-mail address")
        else:
            digits = re.sub(r"\D", "", v)
            if len(digits) not in (10, 12):
                raise ValueError("Enter a valid 10-digit mobile number")
        return v

    @field_validator("roll_number")
    @classmethod
    def _roll(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"[A-Za-z0-9\-/]+", v):
            raise ValueError("Roll number may contain letters, digits, '-' or '/' only")
        return v


class OtpResend(BaseModel):
    request_id: str = Field(min_length=10, max_length=64)


class OtpVerify(BaseModel):
    request_id: str = Field(min_length=10, max_length=64)
    code: str

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        v = v.strip()
        if not _OTP.fullmatch(v):
            raise ValueError("Code must be 6 digits")
        return v


class TeacherLogin(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class ChallengeOnly(BaseModel):
    challenge_token: str = Field(min_length=20, max_length=2048)


class TotpVerify(ChallengeOnly):
    code: str

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        v = v.strip().replace(" ", "")
        if not _OTP.fullmatch(v):
            raise ValueError("Authenticator code must be 6 digits")
        return v
