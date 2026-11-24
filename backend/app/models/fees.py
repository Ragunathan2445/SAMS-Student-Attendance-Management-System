"""Fees: structures, per-student charges, payments, receipts, adjustments and the balance ledger.

All money columns are NUMERIC(12,2) and handled with Python Decimal end-to-end.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

FEE_CATEGORIES = ("academic", "bus", "term", "extra_activity", "penalty", "other")
_CAT_SQL = ",".join(f"'{c}'" for c in FEE_CATEGORIES)
Money = Numeric(12, 2)


class FeeStructure(Base, TimestampMixin):
    __tablename__ = "fee_structures"
    __table_args__ = (
        UniqueConstraint("academic_year_id", "class_id", "name"),
        CheckConstraint(f"category IN ({_CAT_SQL})", name="valid_category"),
        CheckConstraint("amount >= 0", name="non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="RESTRICT"), index=True)
    category: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Money)
    due_date: Mapped[date | None] = mapped_column(Date)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)  # e.g. bus fee
    description: Mapped[str | None] = mapped_column(String(255))


class StudentFeeRecord(Base, TimestampMixin):
    """A charge raised against a student (from a fee structure, or a penalty/other charge)."""

    __tablename__ = "student_fee_records"
    __table_args__ = (
        CheckConstraint(f"category IN ({_CAT_SQL})", name="valid_category"),
        CheckConstraint("amount > 0", name="positive"),
        Index("ix_fee_records_student_year", "student_id", "academic_year_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    fee_structure_id: Mapped[int | None] = mapped_column(ForeignKey("fee_structures.id", ondelete="RESTRICT"))
    category: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(150))
    amount: Mapped[Decimal] = mapped_column(Money)
    charged_on: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)

    structure: Mapped[FeeStructure | None] = relationship()
    payments: Mapped[list[FeePayment]] = relationship(back_populates="fee_record")


class FeeAdjustment(Base, TimestampMixin):
    """Concessions / waivers (negative) or corrections (positive) to a student's balance."""

    __tablename__ = "fee_adjustments"
    __table_args__ = (CheckConstraint("amount <> 0", name="non_zero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"), index=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    student_fee_record_id: Mapped[int | None] = mapped_column(ForeignKey("student_fee_records.id", ondelete="RESTRICT"))
    amount: Mapped[Decimal] = mapped_column(Money)  # negative reduces balance
    adjusted_on: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(255))
    approved_by: Mapped[str | None] = mapped_column(String(100))


class FeePayment(Base, TimestampMixin):
    __tablename__ = "fee_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive"),
        CheckConstraint("method IN ('cash','upi','card','net_banking','cheque')", name="valid_method"),
        CheckConstraint("status IN ('success','failed','refunded')", name="valid_status"),
        Index("ix_fee_payments_student_date", "student_id", "payment_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    student_fee_record_id: Mapped[int] = mapped_column(ForeignKey("student_fee_records.id", ondelete="RESTRICT"))
    transaction_ref: Mapped[str] = mapped_column(String(40), unique=True)
    payment_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Money)
    method: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10), default="success")
    is_demo_record: Mapped[bool] = mapped_column(Boolean, default=True)
    remarks: Mapped[str | None] = mapped_column(String(255))

    fee_record: Mapped[StudentFeeRecord] = relationship(back_populates="payments")
    receipt: Mapped[FeeReceipt | None] = relationship(back_populates="payment", uselist=False)


class FeeReceipt(Base):
    __tablename__ = "fee_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("fee_payments.id", ondelete="RESTRICT"), unique=True)
    receipt_number: Mapped[str] = mapped_column(String(40), unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    total_paid_to_date: Mapped[Decimal] = mapped_column(Money)
    balance_after: Mapped[Decimal] = mapped_column(Money)

    payment: Mapped[FeePayment] = relationship(back_populates="receipt")


class FeeBalanceHistory(Base):
    """Append-only ledger. balance_after(n) = balance_after(n-1) + debit - credit."""

    __tablename__ = "fee_balance_history"
    __table_args__ = (
        UniqueConstraint("student_id", "academic_year_id", "sequence"),
        CheckConstraint("entry_type IN ('opening','charge','payment','adjustment')", name="valid_type"),
        CheckConstraint("debit >= 0 AND credit >= 0", name="non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"), index=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    sequence: Mapped[int] = mapped_column(Integer)
    entry_date: Mapped[date] = mapped_column(Date)
    entry_type: Mapped[str] = mapped_column(String(15))
    description: Mapped[str] = mapped_column(String(200))
    fee_record_id: Mapped[int | None] = mapped_column(ForeignKey("student_fee_records.id", ondelete="RESTRICT"))
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("fee_payments.id", ondelete="RESTRICT"))
    adjustment_id: Mapped[int | None] = mapped_column(ForeignKey("fee_adjustments.id", ondelete="RESTRICT"))
    debit: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.00"))
    credit: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.00"))
    balance_after: Mapped[Decimal] = mapped_column(Money)
    notes: Mapped[str | None] = mapped_column(Text)
