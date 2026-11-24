"""Attendance calculation engine.

Everything parents and teachers see (daily / weekly / monthly / yearly reports, charts,
percentages and analytics) is derived here from three sources of truth in PostgreSQL:
the school calendar, the section timetable and the official ``attendance`` rows –
plus leave requests for pending/approved leave display.

Day categories (one per date):
    present, partial, absent, approved_leave, pending_leave, not_recorded, upcoming,
    school_holiday, festival_holiday, weekly_holiday

* Holidays (school / festival / management / weekly) are never working days and are
  never counted as absent. Management holidays are reported as school holidays.
* Pending leave is shown separately and never treated as approved leave.
* Working days with no attendance recorded yet are excluded from the percentage
  (they are reported as "not recorded") rather than counted as absences.
* Daily % = (present days + 0.5 × partial days) / recorded working days.
* Period % = present periods / recorded periods.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import AcademicYear, Attendance, LeaveRequest, Student, Timetable
from app.services.calendar_service import DayInfo, daterange, get_calendar
from app.utils.timeutils import today_local

HOLIDAY_CATEGORY = {
    "school_holiday": "school_holiday",
    "management_holiday": "school_holiday",
    "festival_holiday": "festival_holiday",
    "weekly_holiday": "weekly_holiday",
}
DAY_CATEGORIES = (
    "present",
    "partial",
    "absent",
    "approved_leave",
    "pending_leave",
    "not_recorded",
    "upcoming",
    "school_holiday",
    "festival_holiday",
    "weekly_holiday",
)


def pct(numerator: Decimal | int, denominator: Decimal | int) -> Decimal | None:
    if not denominator:
        return None
    value = Decimal(numerator) * Decimal(100) / Decimal(denominator)
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------- data
@dataclass
class LeaveSpan:
    id: int
    start: date
    end: date
    status: str
    reason: str

    def covers(self, day: date) -> bool:
        return self.start <= day <= self.end


@dataclass
class StudentAttendanceData:
    student: Student
    academic_year: AcademicYear
    calendar: dict[date, DayInfo]
    slots_by_weekday: dict[int, list[Timetable]]
    records_by_date: dict[date, list[Attendance]]
    leaves: list[LeaveSpan]

    def leave_for(self, day: date) -> LeaveSpan | None:
        approved = next((lv for lv in self.leaves if lv.status == "approved" and lv.covers(day)), None)
        return approved or next((lv for lv in self.leaves if lv.status == "pending" and lv.covers(day)), None)


@dataclass
class DayResult:
    date: date
    day_type: str
    title: str | None
    category: str
    scheduled_periods: int = 0
    present_periods: int = 0
    absent_periods: int = 0
    leave_periods: int = 0
    pending_leave_periods: int = 0
    absence_reasons: list[str] = field(default_factory=list)
    leave_request_id: int | None = None
    leave_status: str | None = None

    @property
    def is_working(self) -> bool:
        return self.day_type == "working"

    def as_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "weekday": self.date.strftime("%A"),
            "day_type": self.day_type,
            "title": self.title,
            "category": self.category,
            "scheduled_periods": self.scheduled_periods,
            "present_periods": self.present_periods,
            "absent_periods": self.absent_periods,
            "leave_periods": self.leave_periods,
            "pending_leave_periods": self.pending_leave_periods,
            "absence_reasons": sorted(set(self.absence_reasons)),
            "leave_request_id": self.leave_request_id,
            "leave_status": self.leave_status,
        }


# --------------------------------------------------------------------------- loading
def _timetable_by_weekday(db: Session, academic_year_id: int, section_id: int) -> dict[int, list[Timetable]]:
    rows = db.scalars(
        select(Timetable)
        .options(joinedload(Timetable.period), joinedload(Timetable.subject), joinedload(Timetable.teacher))
        .where(Timetable.academic_year_id == academic_year_id, Timetable.section_id == section_id)
    ).all()
    result: dict[int, list[Timetable]] = defaultdict(list)
    for row in rows:
        result[row.day_of_week].append(row)
    for slots in result.values():
        slots.sort(key=lambda s: s.period.period_number)
    return result


def effective_range(student: Student, academic_year: AcademicYear, start: date, end: date) -> tuple[date, date]:
    first = max(start, academic_year.start_date, student.admission_date or academic_year.start_date)
    last = min(end, academic_year.end_date)
    return first, last


def load_student_data(
    db: Session, student: Student, academic_year: AcademicYear, start: date, end: date
) -> StudentAttendanceData:
    return load_many(db, [student], academic_year, start, end)[student.id]


def load_many(
    db: Session, students: list[Student], academic_year: AcademicYear, start: date, end: date
) -> dict[int, StudentAttendanceData]:
    """Batch-load everything needed to compute attendance for many students."""
    if not students:
        return {}
    calendar = get_calendar(db, academic_year, start, end)
    timetable_cache: dict[int, dict[int, list[Timetable]]] = {}
    ids = [s.id for s in students]

    records: dict[int, dict[date, list[Attendance]]] = defaultdict(lambda: defaultdict(list))
    rows = db.scalars(
        select(Attendance)
        .options(joinedload(Attendance.period), joinedload(Attendance.subject), joinedload(Attendance.marked_by))
        .where(Attendance.student_id.in_(ids), Attendance.date >= start, Attendance.date <= end)
    ).all()
    for row in rows:
        records[row.student_id][row.date].append(row)

    leaves: dict[int, list[LeaveSpan]] = defaultdict(list)
    for lv in db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.student_id.in_(ids),
            LeaveRequest.status.in_(("pending", "approved")),
            LeaveRequest.start_date <= end,
            LeaveRequest.end_date >= start,
        )
    ):
        leaves[lv.student_id].append(LeaveSpan(lv.id, lv.start_date, lv.end_date, lv.status, lv.reason))

    result = {}
    for student in students:
        if student.section_id not in timetable_cache:
            timetable_cache[student.section_id] = _timetable_by_weekday(db, academic_year.id, student.section_id)
        result[student.id] = StudentAttendanceData(
            student=student,
            academic_year=academic_year,
            calendar=calendar,
            slots_by_weekday=timetable_cache[student.section_id],
            records_by_date=records[student.id],
            leaves=leaves[student.id],
        )
    return result


# --------------------------------------------------------------------------- computing
def compute_day(data: StudentAttendanceData, day: date, today: date | None = None) -> DayResult:
    today = today or today_local()
    info = data.calendar.get(day) or DayInfo(day, "outside")
    first, last = effective_range(data.student, data.academic_year, day, day)

    if info.day_type == "outside":
        return DayResult(day, info.day_type, info.title, "outside")
    if not info.is_working:
        return DayResult(day, info.day_type, info.title, HOLIDAY_CATEGORY.get(info.day_type, "school_holiday"))
    if day < first or day > last:
        # Working day before the student's admission – not part of their record.
        return DayResult(day, info.day_type, "Before admission", "outside")

    scheduled = len(data.slots_by_weekday.get(day.isoweekday(), []))
    records = data.records_by_date.get(day, [])
    leave = data.leave_for(day)
    result = DayResult(day, "working", info.title, "not_recorded", scheduled_periods=scheduled)
    if leave:
        result.leave_request_id, result.leave_status = leave.id, leave.status

    present = sum(1 for r in records if r.status == "present")
    absent = sum(1 for r in records if r.status == "absent")
    on_leave = sum(1 for r in records if r.status == "leave")
    result.absence_reasons = [r.absence_reason for r in records if r.status == "absent" and r.absence_reason]

    if not records:
        if day > today:
            result.category = "upcoming"
        if leave and leave.status == "approved":
            result.category = "approved_leave"
            result.leave_periods = scheduled
        elif leave and leave.status == "pending" and day <= today:
            result.category = "pending_leave"
            result.pending_leave_periods = scheduled
        return result

    if leave and leave.status == "pending":
        # Absences covered by a pending request are shown as pending leave (not approved).
        result.present_periods, result.pending_leave_periods, result.leave_periods = present, absent, on_leave
    elif leave and leave.status == "approved":
        result.present_periods, result.leave_periods = present, absent + on_leave
    else:
        result.present_periods, result.absent_periods, result.leave_periods = present, absent, on_leave

    not_present = result.absent_periods + result.leave_periods + result.pending_leave_periods
    if result.present_periods and not_present:
        result.category = "partial"
    elif result.present_periods:
        result.category = "present"
    elif result.pending_leave_periods:
        result.category = "pending_leave"
    elif result.leave_periods and not result.absent_periods:
        result.category = "approved_leave"
    else:
        result.category = "absent"
    return result


def compute_range(data: StudentAttendanceData, start: date, end: date, today: date | None = None) -> list[DayResult]:
    return [compute_day(data, d, today) for d in daterange(start, end)]


def summarize(days: list[DayResult]) -> dict:
    counts = {c: 0 for c in DAY_CATEGORIES}
    reasons: dict[str, int] = defaultdict(int)
    present_p = absent_p = leave_p = pending_p = 0
    for d in days:
        if d.category in counts:
            counts[d.category] += 1
        present_p += d.present_periods
        absent_p += d.absent_periods
        leave_p += d.leave_periods
        pending_p += d.pending_leave_periods
        if d.category in ("absent", "partial"):
            for reason in set(d.absence_reasons) or {"not_specified"}:
                reasons[reason] += 1

    working_elapsed = sum(
        counts[c] for c in ("present", "partial", "absent", "approved_leave", "pending_leave", "not_recorded")
    )
    recorded = working_elapsed - counts["not_recorded"]
    present_equiv = Decimal(counts["present"]) + Decimal(counts["partial"]) * Decimal("0.5")
    period_total = present_p + absent_p + leave_p + pending_p
    return {
        "total_working_days": working_elapsed,
        "recorded_working_days": recorded,
        "not_recorded_days": counts["not_recorded"],
        "upcoming_working_days": counts["upcoming"],
        "present_days": counts["present"],
        "partial_days": counts["partial"],
        "absent_days": counts["absent"],
        "approved_leave_days": counts["approved_leave"],
        "pending_leave_days": counts["pending_leave"],
        "school_holidays": counts["school_holiday"],
        "festival_holidays": counts["festival_holiday"],
        "weekly_holidays": counts["weekly_holiday"],
        "daily_percentage": pct(present_equiv, recorded),
        "present_periods": present_p,
        "absent_periods": absent_p,
        "leave_periods": leave_p,
        "pending_leave_periods": pending_p,
        "total_periods": period_total,
        "period_percentage": pct(present_p, period_total),
        "absence_reasons": dict(reasons),
    }


def period_breakdown(data: StudentAttendanceData, day: date, today: date | None = None) -> list[dict]:
    """Period-wise rows for the daily table."""
    today = today or today_local()
    day_result = compute_day(data, day, today)
    if not day_result.is_working:
        return []
    by_period = {r.period_id: r for r in data.records_by_date.get(day, [])}
    leave = data.leave_for(day)
    rows = []
    for slot in data.slots_by_weekday.get(day.isoweekday(), []):
        record = by_period.get(slot.period_id)
        if record is None:
            status = "not_marked"
            if leave and leave.status == "approved":
                status = "approved_leave"
            elif leave and leave.status == "pending" and day <= today:
                status = "pending_leave"
        elif record.status == "present":
            status = "present"
        elif record.status == "leave" or (leave and leave.status == "approved"):
            status = "approved_leave"
        elif leave and leave.status == "pending":
            status = "pending_leave"
        else:
            status = "absent"
        rows.append(
            {
                "period_number": slot.period.period_number,
                "start_time": slot.period.start_time.strftime("%H:%M"),
                "end_time": slot.period.end_time.strftime("%H:%M"),
                "subject": (record.subject.name if record and record.subject else slot.subject.name),
                "teacher": (record.marked_by.full_name if record else slot.teacher.full_name),
                "status": status,
                "absence_reason": record.absence_reason if record else None,
                "remarks": record.remarks if record else None,
                "source": record.source if record else None,
                "marked_at": record.marked_at.isoformat() if record else None,
            }
        )
    return rows


def week_bounds(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.isoweekday() - 1)
    return start, start + timedelta(days=6)


def longest_absence_streak(days: list[DayResult]) -> int:
    """Consecutive *working* days absent (holidays do not break or extend the streak)."""
    best = current = 0
    for d in days:
        if not d.is_working or d.category in ("not_recorded", "upcoming"):
            continue
        if d.category == "absent":
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best
