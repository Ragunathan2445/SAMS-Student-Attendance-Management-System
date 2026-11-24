"""Packaging of attendance calculations into daily / weekly / monthly / yearly reports."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models import AcademicYear, Student
from app.services import attendance_calc as calc
from app.utils.timeutils import month_bounds, today_local


def _clip(ay: AcademicYear, start: date, end: date) -> tuple[date, date]:
    return max(start, ay.start_date), min(end, ay.end_date)


def daily_report(db: Session, student: Student, ay: AcademicYear, day: date) -> dict:
    data = calc.load_student_data(db, student, ay, day, day)
    result = calc.compute_day(data, day)
    return {"date": day.isoformat(), "day": result.as_dict(), "periods": calc.period_breakdown(data, day)}


def weekly_report(db: Session, student: Student, ay: AcademicYear, day: date) -> dict:
    start, end = calc.week_bounds(day)
    data = calc.load_student_data(db, student, ay, start, end)
    days = calc.compute_range(data, start, end)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": [d.as_dict() for d in days],
        "summary": calc.summarize(days),
    }


def monthly_report(db: Session, student: Student, ay: AcademicYear, year: int, month: int) -> dict:
    start, end = month_bounds(year, month)
    data = calc.load_student_data(db, student, ay, start, end)
    days = calc.compute_range(data, start, end)
    return {
        "year": year,
        "month": month,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": [d.as_dict() for d in days],
        "summary": calc.summarize(days),
    }


def academic_months(ay: AcademicYear) -> list[tuple[int, int]]:
    months, y, m = [], ay.start_date.year, ay.start_date.month
    while (y, m) <= (ay.end_date.year, ay.end_date.month):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def yearly_report(db: Session, student: Student, ay: AcademicYear) -> dict:
    data = calc.load_student_data(db, student, ay, ay.start_date, ay.end_date)
    all_days = calc.compute_range(data, ay.start_date, ay.end_date)
    by_month: dict[tuple[int, int], list] = {}
    for d in all_days:
        by_month.setdefault((d.date.year, d.date.month), []).append(d)
    months = []
    for y, m in academic_months(ay):
        s = calc.summarize(by_month.get((y, m), []))
        months.append({"year": y, "month": m, "label": date(y, m, 1).strftime("%b %Y"), **s})
    return {
        "academic_year": ay.name,
        "start_date": ay.start_date.isoformat(),
        "end_date": ay.end_date.isoformat(),
        "months": months,
        "summary": calc.summarize(all_days),
    }


def overview(db: Session, student: Student, ay: AcademicYear) -> dict:
    """Academic-year-to-date summary for the top of the attendance page."""
    today = today_local()
    start, end = _clip(ay, ay.start_date, today)
    data = calc.load_student_data(db, student, ay, start, end)
    days = calc.compute_range(data, start, end, today)
    summary = calc.summarize(days)
    summary["longest_absence_streak"] = calc.longest_absence_streak(days)
    summary["as_of"] = end.isoformat()
    summary["academic_year"] = ay.name
    return summary


def history(db: Session, student: Student, ay: AcademicYear, start: date, end: date) -> list[dict]:
    start, end = _clip(ay, start, min(end, today_local()))
    if start > end:
        return []
    data = calc.load_student_data(db, student, ay, start, end)
    days = calc.compute_range(data, start, end)
    return [d.as_dict() for d in reversed(days) if d.category != "outside"]
