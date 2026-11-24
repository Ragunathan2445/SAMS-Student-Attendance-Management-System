"""Fee details, payment history and the transaction-based balance ledger (read-only).

Balance = Σ charges + Σ adjustments − Σ successful payments (+ opening balance).
The stored ledger (fee_balance_history) is cross-checked against this on every read.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import NotFound
from app.models import (
    AcademicYear,
    FeeAdjustment,
    FeeBalanceHistory,
    FeePayment,
    FeeReceipt,
    FeeStructure,
    StudentFeeRecord,
)
from app.utils.timeutils import today_local

ZERO = Decimal("0.00")
CATEGORY_LABELS = {
    "academic": "Academic Fee",
    "bus": "Bus Fee",
    "term": "Term Fee",
    "extra_activity": "Extra Activity Fee",
    "penalty": "Penalty Fee",
    "other": "Other Fees",
}
METHOD_LABELS = {"cash": "Cash", "upi": "UPI", "card": "Debit/Credit Card", "net_banking": "Net Banking", "cheque": "Cheque"}


def money(value: Decimal | None) -> str:
    return str((value or ZERO).quantize(Decimal("0.01")))


def fee_details(db: Session, student_id: int, ay: AcademicYear) -> dict:
    today = today_local()
    records = db.scalars(
        select(StudentFeeRecord).where(StudentFeeRecord.student_id == student_id, StudentFeeRecord.academic_year_id == ay.id)
        .order_by(StudentFeeRecord.due_date.nulls_last(), StudentFeeRecord.id)
    ).all()
    paid_by_record: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for p in db.scalars(select(FeePayment).where(FeePayment.student_id == student_id, FeePayment.academic_year_id == ay.id,
                                                 FeePayment.status == "success")):
        paid_by_record[p.student_fee_record_id] += p.amount
    adj_by_record: dict[int | None, Decimal] = defaultdict(lambda: ZERO)
    for a in db.scalars(select(FeeAdjustment).where(FeeAdjustment.student_id == student_id, FeeAdjustment.academic_year_id == ay.id)):
        adj_by_record[a.student_fee_record_id] += a.amount

    items, categories = [], defaultdict(lambda: {"charged": ZERO, "adjustments": ZERO, "paid": ZERO, "balance": ZERO, "overdue": ZERO})
    total_charged = total_paid = total_adj = overdue = ZERO
    for r in records:
        paid = paid_by_record[r.id]
        adj = adj_by_record[r.id]
        balance = r.amount + adj - paid
        is_overdue = balance > 0 and r.due_date is not None and r.due_date < today
        status = "paid" if balance <= 0 else ("partially_paid" if paid > 0 else ("overdue" if is_overdue else "due"))
        if balance > 0 and is_overdue:
            status = "overdue" if paid == 0 else "partially_paid_overdue"
        items.append({
            "id": r.id, "category": r.category, "category_label": CATEGORY_LABELS[r.category],
            "description": r.description, "amount": money(r.amount), "adjustments": money(adj),
            "paid": money(paid), "balance": money(balance), "due_date": r.due_date.isoformat() if r.due_date else None,
            "status": status,
        })
        c = categories[r.category]
        c["charged"] += r.amount
        c["adjustments"] += adj
        c["paid"] += paid
        c["balance"] += balance
        if is_overdue:
            c["overdue"] += balance
            overdue += balance
        total_charged += r.amount
        total_paid += paid
        total_adj += adj
    total_adj += adj_by_record[None]  # adjustments not linked to a single charge

    opening = db.scalar(
        select(FeeBalanceHistory.balance_after).where(
            FeeBalanceHistory.student_id == student_id, FeeBalanceHistory.academic_year_id == ay.id,
            FeeBalanceHistory.entry_type == "opening")
    ) or ZERO
    balance = opening + total_charged + total_adj - total_paid
    ledger_last = db.scalar(
        select(FeeBalanceHistory.balance_after).where(
            FeeBalanceHistory.student_id == student_id, FeeBalanceHistory.academic_year_id == ay.id)
        .order_by(FeeBalanceHistory.sequence.desc()).limit(1)
    )
    upcoming = [i for i in items if Decimal(i["balance"]) > 0 and i["due_date"] and i["due_date"] >= today.isoformat()]
    return {
        "academic_year": ay.name,
        "opening_balance": money(opening),
        "total_fee": money(total_charged),
        "total_adjustments": money(total_adj),
        "amount_paid": money(total_paid),
        "pending_amount": money(overdue),          # overdue (due date passed, unpaid)
        "balance_amount": money(balance),          # everything still outstanding
        "next_due": upcoming[0] if upcoming else None,
        "ledger_reconciled": ledger_last is not None and ledger_last == balance,
        "categories": [
            {"category": k, "category_label": CATEGORY_LABELS[k], **{f: money(v) for f, v in vals.items()}}
            for k, vals in sorted(categories.items(), key=lambda kv: list(CATEGORY_LABELS).index(kv[0]))
        ],
        "items": items,
        "is_demo_data": True,
    }


def payment_history(db: Session, student_id: int, ay: AcademicYear | None = None,
                    start: date | None = None, end: date | None = None) -> list[dict]:
    q = (select(FeePayment).options(joinedload(FeePayment.fee_record), joinedload(FeePayment.receipt))
         .where(FeePayment.student_id == student_id))
    if ay:
        q = q.where(FeePayment.academic_year_id == ay.id)
    if start:
        q = q.where(FeePayment.payment_date >= start)
    if end:
        q = q.where(FeePayment.payment_date <= end)
    return [
        {
            "id": p.id, "transaction_ref": p.transaction_ref, "payment_date": p.payment_date.isoformat(),
            "category": p.fee_record.category, "category_label": CATEGORY_LABELS[p.fee_record.category],
            "description": p.fee_record.description, "amount": money(p.amount), "method": p.method,
            "method_label": METHOD_LABELS.get(p.method, p.method), "status": p.status,
            "receipt_number": p.receipt.receipt_number if p.receipt else None,
            "receipt_available": p.receipt is not None and p.status == "success",
            "is_demo_record": p.is_demo_record,
        }
        for p in db.scalars(q.order_by(FeePayment.payment_date.desc(), FeePayment.id.desc())).unique()
    ]


def balance_history(db: Session, student_id: int, ay: AcademicYear, start: date | None = None, end: date | None = None) -> dict:
    q = select(FeeBalanceHistory).where(FeeBalanceHistory.student_id == student_id, FeeBalanceHistory.academic_year_id == ay.id)
    rows = db.scalars(q.order_by(FeeBalanceHistory.sequence)).all()
    # Verify the chain: each balance must equal previous + debit − credit.
    running, consistent = ZERO, True
    for r in rows:
        running = (r.balance_after if r.entry_type == "opening" else running + r.debit - r.credit)
        consistent &= running == r.balance_after
    entries = [
        {"sequence": r.sequence, "entry_date": r.entry_date.isoformat(), "entry_type": r.entry_type,
         "description": r.description, "debit": money(r.debit), "credit": money(r.credit),
         "balance_after": money(r.balance_after)}
        for r in rows
        if (not start or r.entry_date >= start) and (not end or r.entry_date <= end)
    ]
    return {"academic_year": ay.name, "entries": entries, "chain_consistent": consistent,
            "closing_balance": money(rows[-1].balance_after if rows else ZERO)}


def get_payment(db: Session, payment_id: int) -> FeePayment:
    p = db.scalar(select(FeePayment).options(joinedload(FeePayment.fee_record), joinedload(FeePayment.receipt))
                  .where(FeePayment.id == payment_id))
    if p is None:
        raise NotFound("Payment not found.")
    return p


def total_paid_until(db: Session, student_id: int, ay_id: int, payment: FeePayment) -> Decimal:
    rows = db.scalars(select(FeePayment).where(FeePayment.student_id == student_id, FeePayment.academic_year_id == ay_id,
                                               FeePayment.status == "success")).all()
    return sum((p.amount for p in rows if (p.payment_date, p.id) <= (payment.payment_date, payment.id)), ZERO)


def structures_for_class(db: Session, ay_id: int, class_id: int) -> list[FeeStructure]:
    return db.scalars(select(FeeStructure).where(FeeStructure.academic_year_id == ay_id, FeeStructure.class_id == class_id)
                      .order_by(FeeStructure.due_date)).all()


def next_sequence(db: Session, student_id: int, ay_id: int) -> tuple[int, Decimal]:
    last = db.scalar(select(FeeBalanceHistory).where(FeeBalanceHistory.student_id == student_id,
                                                     FeeBalanceHistory.academic_year_id == ay_id)
                     .order_by(FeeBalanceHistory.sequence.desc()).limit(1))
    return (last.sequence + 1, last.balance_after) if last else (1, ZERO)


__all__ = ["fee_details", "payment_history", "balance_history", "get_payment", "FeeReceipt"]
