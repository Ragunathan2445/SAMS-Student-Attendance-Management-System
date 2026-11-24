"""Business rules of the attendance engine (no database required)."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace as NS

from app.services import attendance_calc as calc
from app.services.calendar_service import DayInfo, daterange, default_day_type

AY = NS(id=1, start_date=date(2026, 6, 1), end_date=date(2027, 4, 30), saturday_is_working=True)
TODAY = date(2026, 11, 20)  # Friday
STUDENT = NS(id=1, section_id=1, admission_date=date(2020, 6, 1))
SLOTS = {dow: [NS(period_id=p) for p in range(1, 8)] for dow in range(1, 6)}
SLOTS[6] = [NS(period_id=p) for p in range(1, 5)]


def rec(status, period_id, reason=None):
    return NS(status=status, period_id=period_id, absence_reason=reason)


def make(start, end, calendar_overrides=None, records=None, leaves=None, student=STUDENT):
    cal = {}
    for d in daterange(start, end):
        t, title = default_day_type(AY, d)
        cal[d] = DayInfo(d, t, title)
    for d, t in (calendar_overrides or {}).items():
        cal[d] = DayInfo(d, t, "override")
    return calc.StudentAttendanceData(student=student, academic_year=AY, calendar=cal, slots_by_weekday=SLOTS,
                                      records_by_date=records or {}, leaves=leaves or [])


def full_day(status, reason=None, n=7):
    return [rec(status, p, reason) for p in range(1, n + 1)]


def test_sunday_and_holidays_are_never_absent():
    sunday, festival = date(2026, 11, 15), date(2026, 11, 9)
    data = make(date(2026, 11, 9), date(2026, 11, 15), {festival: "festival_holiday"})
    assert calc.compute_day(data, sunday, TODAY).category == "weekly_holiday"
    assert calc.compute_day(data, festival, TODAY).category == "festival_holiday"


def test_management_holiday_reported_as_school_holiday():
    d = date(2026, 11, 13)
    data = make(d, d, {d: "management_holiday"})
    assert calc.compute_day(data, d, TODAY).category == "school_holiday"


def test_saturday_is_a_working_day_by_default():
    sat = date(2026, 11, 7)
    data = make(sat, sat, records={sat: full_day("present", n=4)})
    day = calc.compute_day(data, sat, TODAY)
    assert day.is_working and day.category == "present" and day.scheduled_periods == 4


def test_saturday_can_be_declared_holiday_by_calendar():
    sat = date(2026, 11, 28)
    data = make(sat, sat, {sat: "school_holiday"})
    assert calc.compute_day(data, sat, TODAY).category == "school_holiday"


def test_pending_leave_is_not_approved_leave():
    d = date(2026, 11, 18)
    data = make(d, d, records={d: full_day("absent", "informed_leave")},
                leaves=[calc.LeaveSpan(1, d, d, "pending", "fever")])
    day = calc.compute_day(data, d, TODAY)
    assert day.category == "pending_leave"
    assert day.absent_periods == 0 and day.pending_leave_periods == 7 and day.leave_periods == 0


def test_approved_leave_shown_separately_from_absence():
    d = date(2026, 11, 18)
    data = make(d, d, records={d: full_day("leave")}, leaves=[calc.LeaveSpan(1, d, d, "approved", "fever")])
    s = calc.summarize([calc.compute_day(data, d, TODAY)])
    assert s["approved_leave_days"] == 1 and s["absent_days"] == 0


def test_partial_day_and_percentages():
    mon, tue, wed = date(2026, 11, 16), date(2026, 11, 17), date(2026, 11, 18)
    partial = [rec("present", p) for p in range(1, 5)] + [rec("absent", p, "medical_appointment") for p in range(5, 8)]
    data = make(mon, wed, records={mon: full_day("present"), tue: partial, wed: full_day("absent", "fever")})
    days = calc.compute_range(data, mon, wed, TODAY)
    assert [d.category for d in days] == ["present", "partial", "absent"]
    s = calc.summarize(days)
    assert s["daily_percentage"] == Decimal("50.00")            # (1 + 0.5) / 3
    assert s["period_percentage"] == Decimal("52.38")           # 11 / 21
    assert s["absence_reasons"] == {"medical_appointment": 1, "fever": 1}


def test_unrecorded_and_future_days_excluded_from_percentage():
    thu, fri, nxt = date(2026, 11, 19), date(2026, 11, 20), date(2026, 11, 23)
    data = make(thu, nxt, records={thu: full_day("present")})
    days = calc.compute_range(data, thu, nxt, TODAY)
    cats = {d.date: d.category for d in days}
    assert cats[fri] == "not_recorded" and cats[nxt] == "upcoming"
    s = calc.summarize(days)
    assert s["recorded_working_days"] == 1 and s["daily_percentage"] == Decimal("100.00")


def test_days_before_admission_are_outside_record():
    late = NS(id=2, section_id=1, admission_date=date(2026, 11, 18))
    d = date(2026, 11, 17)
    data = make(d, d, student=late)
    assert calc.compute_day(data, d, TODAY).category == "outside"


def test_absence_streak_ignores_holidays():
    fri, sat, mon = date(2026, 11, 13), date(2026, 11, 14), date(2026, 11, 16)  # Sunday 15th in between
    data = make(fri, mon, {sat: "school_holiday"}, records={fri: full_day("absent"), mon: full_day("absent")})
    days = calc.compute_range(data, fri, mon, TODAY)
    assert calc.longest_absence_streak(days) == 2
