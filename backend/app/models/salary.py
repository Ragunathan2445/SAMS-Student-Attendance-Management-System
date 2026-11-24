"""Teacher salary (predefined demo data; read-only for teachers)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

Money = Numeric(12, 2)


class TeacherSalary(Base, TimestampMixin):
    __tablename__ = "teacher_salary"
    __table_args__ = (
        UniqueConstraint("teacher_id", "salary_month"),
        CheckConstraint("status IN ('paid','processing','on_hold')", name="valid_status"),
        CheckConstraint("net_salary = gross_salary - total_deductions", name="net_reconciles"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="RESTRICT"), index=True)
    salary_month: Mapped[date] = mapped_column(Date)  # first day of month
    working_days: Mapped[int] = mapped_column(default=0)
    days_present: Mapped[int] = mapped_column(default=0)
    basic_salary: Mapped[Decimal] = mapped_column(Money)
    dearness_allowance: Mapped[Decimal] = mapped_column(Money)
    house_rent_allowance: Mapped[Decimal] = mapped_column(Money)
    transport_allowance: Mapped[Decimal] = mapped_column(Money)
    special_allowance: Mapped[Decimal] = mapped_column(Money)
    gross_salary: Mapped[Decimal] = mapped_column(Money)
    penalty_deductions: Mapped[Decimal] = mapped_column(Money)
    other_deductions: Mapped[Decimal] = mapped_column(Money)
    total_deductions: Mapped[Decimal] = mapped_column(Money)
    net_salary: Mapped[Decimal] = mapped_column(Money)
    status: Mapped[str] = mapped_column(String(15))
    payment_date: Mapped[date | None] = mapped_column(Date)

    deductions: Mapped[list[SalaryDeduction]] = relationship(
        back_populates="salary", order_by="SalaryDeduction.id"
    )
    payments: Mapped[list[SalaryPayment]] = relationship(back_populates="salary")


class SalaryDeduction(Base, TimestampMixin):
    __tablename__ = "salary_deductions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive"),
        CheckConstraint(
            "deduction_type IN ('provident_fund','professional_tax','income_tax','late_arrival_penalty',"
            "'loss_of_pay','other_penalty','other')",
            name="valid_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_salary_id: Mapped[int] = mapped_column(ForeignKey("teacher_salary.id", ondelete="RESTRICT"), index=True)
    deduction_type: Mapped[str] = mapped_column(String(30))
    is_penalty: Mapped[bool] = mapped_column(default=False)
    description: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Money)

    salary: Mapped[TeacherSalary] = relationship(back_populates="deductions")


class SalaryPayment(Base, TimestampMixin):
    __tablename__ = "salary_payments"
    __table_args__ = (CheckConstraint("status IN ('success','failed')", name="valid_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_salary_id: Mapped[int] = mapped_column(ForeignKey("teacher_salary.id", ondelete="RESTRICT"), index=True)
    payment_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Money)
    method: Mapped[str] = mapped_column(String(30), default="bank_transfer")
    reference_number: Mapped[str] = mapped_column(String(40), unique=True)
    status: Mapped[str] = mapped_column(String(10), default="success")

    salary: Mapped[TeacherSalary] = relationship(back_populates="payments")
