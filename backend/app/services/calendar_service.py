"""School working calendar.

Rules:
* An explicit ``school_calendar`` entry always wins (holiday or declared working day).
* Otherwise Sunday is a weekly holiday.
* Saturday is a working day unless the academic year says otherwise – it is never
  assumed to be a holiday automatically; specific Saturdays are made holidays via
  calendar entries (e.g. "Second Saturday").
* All other weekdays are working days.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AcademicYear, SchoolCalendar


@dataclass(frozen=True)
class DayInfo:
    date: date
    day_type: str  # working | school_holiday | festival_holiday | management_holiday | weekly_holiday | outside
    title: str | None = None

    @property
    def is_working(self) -> bool:
        return self.day_type == "working"


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def default_day_type(academic_year: AcademicYear, day: date) -> tuple[str, str | None]:
    weekday = day.isoweekday()
    if weekday == 7:
        return "weekly_holiday", "Sunday"
    if weekday == 6 and not academic_year.saturday_is_working:
        return "weekly_holiday", "Saturday"
    return "working", None


def get_calendar(db: Session, academic_year: AcademicYear, start: date, end: date) -> dict[date, DayInfo]:
    entries = {
        row.date: row
        for row in db.scalars(
            select(SchoolCalendar).where(
                SchoolCalendar.academic_year_id == academic_year.id,
                SchoolCalendar.date >= start,
                SchoolCalendar.date <= end,
            )
        )
    }
    result: dict[date, DayInfo] = {}
    for day in daterange(start, end):
        if day < academic_year.start_date or day > academic_year.end_date:
            result[day] = DayInfo(day, "outside", "Outside academic year")
        elif day in entries:
            result[day] = DayInfo(day, entries[day].day_type, entries[day].title)
        else:
            day_type, title = default_day_type(academic_year, day)
            result[day] = DayInfo(day, day_type, title)
    return result


def get_day(db: Session, academic_year: AcademicYear, day: date) -> DayInfo:
    return get_calendar(db, academic_year, day, day)[day]


def get_current_academic_year(db: Session) -> AcademicYear:
    from app.core.errors import NotFound

    year = db.scalar(select(AcademicYear).where(AcademicYear.is_current.is_(True)))
    if not year:
        raise NotFound("No current academic year is configured.")
    return year
