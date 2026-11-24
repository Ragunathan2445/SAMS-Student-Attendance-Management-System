"""Teacher attendance analytics: class-wise, student-wise, overall, top absentees,
repeated absences and monthly summaries. Built on the shared calculation engine."""
from __future__ import annotations

import io
from collections import defaultdict
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import AcademicYear, Section, Student, Teacher
from app.utils.files import student_photo_url
from app.services import attendance_calc as calc
from app.services import attendance_reports, teacher_scope
from app.utils.timeutils import today_local

REPEATED_STREAK = 3          # consecutive absent working days
REPEATED_MIN_TOTAL = 3       # or at least this many absent days …
REPEATED_SHARE = Decimal("0.08")  # … and at least 8% of the recorded working days in the range


def _repeated_threshold(recorded_days: int) -> int:
    from math import ceil

    return max(REPEATED_MIN_TOTAL, ceil(Decimal(recorded_days) * REPEATED_SHARE))


def _range(ay: AcademicYear, start: date | None, end: date | None) -> tuple[date, date]:
    today = today_local()
    s = max(start or ay.start_date, ay.start_date)
    e = min(end or today, today, ay.end_date)
    return s, e


def _students(db: Session, section_ids: set[int], student_id: int | None = None) -> list[Student]:
    q = (select(Student).options(joinedload(Student.section).joinedload(Section.school_class))
         .where(Student.section_id.in_(section_ids), Student.status == "active"))
    if student_id:
        q = q.where(Student.id == student_id)
    return list(db.scalars(q.order_by(Student.section_id, Student.roll_number)).unique())


def _student_stats(student: Student, days: list[calc.DayResult]) -> dict:
    s = calc.summarize(days)
    return {
        "student_id": student.id,
        "full_name": student.full_name,
        "roll_number": student.roll_number,
        "class_label": f"{student.section.school_class.name} – {student.section.name}",
        "photo_url": student_photo_url(student),
        "present_days": s["present_days"],
        "partial_days": s["partial_days"],
        "absent_days": s["absent_days"],
        "approved_leave_days": s["approved_leave_days"],
        "pending_leave_days": s["pending_leave_days"],
        "recorded_working_days": s["recorded_working_days"],
        "daily_percentage": s["daily_percentage"],
        "period_percentage": s["period_percentage"],
        "absent_periods": s["absent_periods"],
        "longest_absence_streak": calc.longest_absence_streak(days),
    }


def class_report(db: Session, teacher: Teacher, ay: AcademicYear, *, section_id: int | None,
                 start: date | None, end: date | None, student_id: int | None = None) -> dict:
    sections = teacher_scope.authorised_section_ids(db, teacher, ay)
    if section_id:
        teacher_scope.require_section(db, teacher, ay, section_id)
        sections = {section_id}
    s, e = _range(ay, start, end)
    students = _students(db, sections, student_id)
    if not students or s > e:
        return {"start_date": s.isoformat(), "end_date": e.isoformat(), "students": [], "daily": [], "overall": None,
                "top_absentees": [], "repeated_absences": [], "sections": []}
    data = calc.load_many(db, students, ay, s, e)

    student_rows = []
    daily = defaultdict(lambda: {"present": 0, "partial": 0, "absent": 0, "approved_leave": 0, "pending_leave": 0})
    section_totals = defaultdict(lambda: {"present_equiv": Decimal(0), "recorded": 0, "absent_days": 0})
    all_days: list[calc.DayResult] = []
    for st in students:
        days = calc.compute_range(data[st.id], s, e)
        all_days.extend(days)
        row = _student_stats(st, days)
        student_rows.append(row)
        for d in days:
            if d.category in daily[d.date]:
                daily[d.date][d.category] += 1
        sec = section_totals[row["class_label"]]
        sec["present_equiv"] += Decimal(row["present_days"]) + Decimal(row["partial_days"]) / 2
        sec["recorded"] += row["recorded_working_days"]
        sec["absent_days"] += row["absent_days"]

    daily_rows = []
    for d in sorted(daily):
        counts = daily[d]
        marked = sum(counts.values())
        if not marked:
            continue
        present_equiv = Decimal(counts["present"]) + Decimal(counts["partial"]) / 2
        daily_rows.append({"date": d.isoformat(), **counts, "students_recorded": marked,
                           "percentage": calc.pct(present_equiv, marked)})

    overall = calc.summarize(all_days)
    top = sorted([r for r in student_rows if r["absent_days"]], key=lambda r: (-r["absent_days"], r["roll_number"]))[:5]
    recorded = max((r["recorded_working_days"] for r in student_rows), default=0)
    total_threshold = _repeated_threshold(recorded)
    repeated = [r for r in student_rows
                if r["longest_absence_streak"] >= REPEATED_STREAK or r["absent_days"] >= total_threshold]
    repeated.sort(key=lambda r: (-r["longest_absence_streak"], -r["absent_days"]))
    return {
        "start_date": s.isoformat(),
        "end_date": e.isoformat(),
        "overall": {
            "students": len(students),
            "daily_percentage": overall["daily_percentage"],
            "period_percentage": overall["period_percentage"],
            "present_days": overall["present_days"],
            "absent_days": overall["absent_days"],
            "approved_leave_days": overall["approved_leave_days"],
            "pending_leave_days": overall["pending_leave_days"],
            "student_days_recorded": overall["recorded_working_days"],
        },
        "sections": [{"label": k, "percentage": calc.pct(v["present_equiv"], v["recorded"]), "absent_days": v["absent_days"]}
                     for k, v in sorted(section_totals.items())],
        "students": student_rows,
        "daily": daily_rows,
        "top_absentees": top,
        "repeated_absences": repeated,
        "criteria": {"streak": REPEATED_STREAK, "total": total_threshold},
    }


def monthly_summary(db: Session, teacher: Teacher, ay: AcademicYear, section_id: int | None) -> list[dict]:
    sections = teacher_scope.authorised_section_ids(db, teacher, ay)
    if section_id:
        teacher_scope.require_section(db, teacher, ay, section_id)
        sections = {section_id}
    students = _students(db, sections)
    s, e = _range(ay, None, None)
    if not students or s > e:
        return []
    data = calc.load_many(db, students, ay, s, e)
    per_month: dict[tuple[int, int], list[calc.DayResult]] = defaultdict(list)
    for st in students:
        for d in calc.compute_range(data[st.id], s, e):
            per_month[(d.date.year, d.date.month)].append(d)
    out = []
    for y, m in attendance_reports.academic_months(ay):
        if (y, m) not in per_month:
            continue
        summ = calc.summarize(per_month[(y, m)])
        working = len({d.date for d in per_month[(y, m)] if d.is_working and d.category not in ("upcoming", "outside")})
        out.append({"label": date(y, m, 1).strftime("%b %Y"), "year": y, "month": m, "working_days": working,
                    "daily_percentage": summ["daily_percentage"], "present_days": summ["present_days"],
                    "absent_days": summ["absent_days"], "approved_leave_days": summ["approved_leave_days"],
                    "pending_leave_days": summ["pending_leave_days"], "partial_days": summ["partial_days"]})
    return out


def student_report(db: Session, teacher: Teacher, ay: AcademicYear, student_id: int) -> dict:
    student = teacher_scope.require_student(db, teacher, ay, student_id)
    return {
        "student": {"id": student.id, "full_name": student.full_name, "roll_number": student.roll_number,
                    "class_label": f"{student.section.school_class.name} – {student.section.name}",
                    "photo_url": student_photo_url(student)},
        "overview": attendance_reports.overview(db, student, ay),
        "yearly": attendance_reports.yearly_report(db, student, ay),
    }


def export_xlsx(report: dict, title: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Student summary"
    brown = PatternFill("solid", fgColor="6B4226")
    ws.append([title])
    ws["A1"].font = Font(bold=True, size=13, color="6B4226")
    ws.append([f"Period: {report['start_date']} to {report['end_date']}"])
    ws.append([])
    headers = ["Roll No", "Student", "Class", "Present", "Partial", "Absent", "Approved leave", "Pending leave",
               "Recorded days", "Daily %", "Period %", "Longest absence streak"]
    ws.append(headers)
    for cell in ws[4]:
        cell.font, cell.fill, cell.alignment = Font(bold=True, color="FFFFFF"), brown, Alignment(horizontal="center")
    for r in report["students"]:
        ws.append([r["roll_number"], r["full_name"], r["class_label"], r["present_days"], r["partial_days"],
                   r["absent_days"], r["approved_leave_days"], r["pending_leave_days"], r["recorded_working_days"],
                   float(r["daily_percentage"] or 0), float(r["period_percentage"] or 0), r["longest_absence_streak"]])
    for col, width in zip("ABCDEFGHIJKL", (10, 26, 16, 9, 9, 9, 15, 14, 14, 9, 9, 22)):
        ws.column_dimensions[col].width = width

    ws2 = wb.create_sheet("Daily class attendance")
    ws2.append(["Date", "Present", "Partial", "Absent", "Approved leave", "Pending leave", "Students recorded", "Attendance %"])
    for cell in ws2[1]:
        cell.font, cell.fill = Font(bold=True, color="FFFFFF"), brown
    for d in report["daily"]:
        ws2.append([d["date"], d["present"], d["partial"], d["absent"], d["approved_leave"], d["pending_leave"],
                    d["students_recorded"], float(d["percentage"] or 0)])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
