"""Teacher salary (predefined, read-only for teachers)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFound
from app.models import Teacher, TeacherSalary
from app.services.fee_service import money

STATUS_LABELS = {"paid": "Paid", "processing": "Processing", "on_hold": "On hold"}
DEDUCTION_LABELS = {
    "provident_fund": "Provident Fund (12% of basic)",
    "professional_tax": "Professional Tax",
    "income_tax": "Income Tax (TDS)",
    "late_arrival_penalty": "Late arrival penalty",
    "loss_of_pay": "Loss of pay",
    "other_penalty": "Other penalty",
    "other": "Other deduction",
}


def _to_dict(s: TeacherSalary, teacher: Teacher, *, detail: bool = False) -> dict:
    allowances = s.dearness_allowance + s.house_rent_allowance + s.transport_allowance + s.special_allowance
    data = {
        "id": s.id,
        "teacher_name": teacher.full_name,
        "teacher_code": teacher.employee_code,
        "salary_month": s.salary_month.isoformat(),
        "month_label": s.salary_month.strftime("%B %Y"),
        "basic_salary": money(s.basic_salary),
        "allowances": money(allowances),
        "gross_salary": money(s.gross_salary),
        "penalty_deductions": money(s.penalty_deductions),
        "other_deductions": money(s.other_deductions),
        "total_deductions": money(s.total_deductions),
        "net_salary": money(s.net_salary),
        "status": s.status,
        "status_label": STATUS_LABELS.get(s.status, s.status),
        "payment_date": s.payment_date.isoformat() if s.payment_date else None,
    }
    if detail:
        data["allowance_breakdown"] = [
            {"label": "Dearness Allowance", "amount": money(s.dearness_allowance)},
            {"label": "House Rent Allowance", "amount": money(s.house_rent_allowance)},
            {"label": "Transport Allowance", "amount": money(s.transport_allowance)},
            {"label": "Special Allowance", "amount": money(s.special_allowance)},
        ]
        data["deductions"] = [
            {"type": d.deduction_type, "label": DEDUCTION_LABELS.get(d.deduction_type, d.deduction_type),
             "description": d.description, "amount": money(d.amount), "is_penalty": d.is_penalty}
            for d in s.deductions
        ]
        data["payments"] = [
            {"payment_date": p.payment_date.isoformat(), "amount": money(p.amount), "method": p.method,
             "reference_number": p.reference_number, "status": p.status}
            for p in s.payments
        ]
        data["working_days"] = s.working_days
        data["days_present"] = s.days_present
    return data


def list_salaries(db: Session, teacher: Teacher) -> list[dict]:
    rows = db.scalars(select(TeacherSalary).where(TeacherSalary.teacher_id == teacher.id)
                      .order_by(TeacherSalary.salary_month.desc())).all()
    return [_to_dict(s, teacher) for s in rows]


def get_salary(db: Session, teacher: Teacher, salary_id: int) -> tuple[TeacherSalary, dict]:
    s = db.scalar(select(TeacherSalary)
                  .options(selectinload(TeacherSalary.deductions), selectinload(TeacherSalary.payments))
                  .where(TeacherSalary.id == salary_id, TeacherSalary.teacher_id == teacher.id))
    if s is None:  # also covers other teachers' records (no IDOR)
        raise NotFound("Salary record not found.")
    return s, _to_dict(s, teacher, detail=True)
