from datetime import date
from decimal import Decimal
from types import SimpleNamespace as NS

import pytest
from pydantic import ValidationError

from app.schemas.auth import OtpVerify, ParentOtpRequest
from app.schemas.students import StudentCreate
from app.services import pdf_service

SCHOOL = NS(name="Sri Vidya Mandir School", address="Chennai", phone="+91 44 2600 1234", email="office@example.com")


def test_inr_grouping():
    assert pdf_service.inr(Decimal("1234567.5")) == "Rs. 12,34,567.50"
    assert pdf_service.inr(Decimal("500")) == "Rs. 500.00"


def test_fee_receipt_pdf():
    pdf = pdf_service.fee_receipt_pdf(
        school=SCHOOL, receipt_number="SVM/2026-27/R00001", student_name="Aditi Ramesh", roll_number="6A01",
        class_label="Grade 6 – A", academic_year="2026-27", payment_date="10 Jun 2026", category_label="Academic Fee",
        description="Academic Fee (Tuition)", amount=Decimal("21000.00"), payment_ref="TXN1", method_label="UPI",
        total_paid=Decimal("21000.00"), remaining_balance=Decimal("54800.00"))
    assert pdf.startswith(b"%PDF") and len(pdf) > 1500


def test_salary_slip_pdf():
    salary = {"month_label": "October 2026", "working_days": 20, "days_present": 20, "status_label": "Paid",
              "payment_date": "2026-10-31", "basic_salary": "42000.00", "gross_salary": "60440.00",
              "allowance_breakdown": [{"label": "DA", "amount": "5040.00"}],
              "deductions": [{"label": "PF", "amount": "5040.00", "is_penalty": False}],
              "penalty_deductions": "0.00", "total_deductions": "5040.00", "net_salary": "55400.00"}
    pdf = pdf_service.salary_slip_pdf(school=SCHOOL, salary=salary,
                                      teacher={"full_name": "Lakshmi Narayanan", "employee_code": "T1001",
                                               "designation": "PG Assistant"})
    assert pdf.startswith(b"%PDF")


def test_parent_login_validation():
    assert ParentOtpRequest(identifier="98400 11001", roll_number="6A01").identifier
    with pytest.raises(ValidationError):
        ParentOtpRequest(identifier="12345", roll_number="6A01")
    with pytest.raises(ValidationError):
        ParentOtpRequest(identifier="9840011001", roll_number="6A01; DROP TABLE")
    with pytest.raises(ValidationError):
        OtpVerify(request_id="x" * 36, code="12ab56")


def test_student_create_validation():
    base = dict(totp_code="123456", full_name="Test Student", roll_number="6A11", admission_number="SVM-2026-1",
                date_of_birth=date(2015, 5, 1), gender="Female", section_id=1, parent_name="Test Parent",
                parent_mobile="+91 98400 99999", parent_email="p@example.com", address="12, Some Street, Chennai")
    s = StudentCreate(**base)
    assert s.parent_mobile == "9840099999"
    with pytest.raises(ValidationError):
        StudentCreate(**{**base, "parent_mobile": "12345"})
    with pytest.raises(ValidationError):
        StudentCreate(**{**base, "date_of_birth": date(2025, 1, 1)})
