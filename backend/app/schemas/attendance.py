from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["present", "absent", "leave"]
AbsenceReason = Literal["fever", "medical_appointment", "family_function", "personal", "informed_leave", "uninformed", "other"]


class AttendanceRecordIn(BaseModel):
    student_id: int = Field(gt=0)
    status: Status
    absence_reason: AbsenceReason | None = None
    remarks: str | None = Field(default=None, max_length=255)


class AttendanceSubmit(BaseModel):
    date: date
    section_id: int = Field(gt=0)
    period_id: int = Field(gt=0)
    records: list[AttendanceRecordIn] = Field(min_length=1, max_length=200)


class AttendanceCorrectionIn(BaseModel):
    status: Status
    absence_reason: AbsenceReason | None = None
    reason: str = Field(min_length=5, max_length=500)


class SubstituteSubmit(BaseModel):
    records: list[AttendanceRecordIn] = Field(min_length=1, max_length=200)


class RejectIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class LeaveDecision(BaseModel):
    action: Literal["approved", "rejected"]
    remarks: str | None = Field(default=None, max_length=500)
