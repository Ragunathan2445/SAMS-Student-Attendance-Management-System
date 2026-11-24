"""PDF generation with ReportLab: fee receipts and salary slips."""
from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import School

BROWN = colors.HexColor("#6B4226")
BROWN_LIGHT = colors.HexColor("#F5EDE4")
BROWN_LINE = colors.HexColor("#D8C3AE")
TEXT = colors.HexColor("#2B2118")
MUTED = colors.HexColor("#7A6A5C")

_styles = getSampleStyleSheet()
H_SCHOOL = ParagraphStyle("school", parent=_styles["Title"], fontName="Helvetica-Bold", fontSize=17, textColor=BROWN, spaceAfter=2, alignment=TA_CENTER)
H_SUB = ParagraphStyle("sub", parent=_styles["Normal"], fontSize=8.5, textColor=MUTED, alignment=TA_CENTER, leading=11)
H_DOC = ParagraphStyle("doc", parent=_styles["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, textColor=TEXT, alignment=TA_CENTER, spaceBefore=6, spaceAfter=6)
BODY = ParagraphStyle("body", parent=_styles["Normal"], fontSize=9.5, textColor=TEXT, leading=13)
SMALL = ParagraphStyle("small", parent=_styles["Normal"], fontSize=7.5, textColor=MUTED, leading=10, alignment=TA_CENTER)
RIGHT = ParagraphStyle("right", parent=BODY, alignment=TA_RIGHT)
HDR = ParagraphStyle("hdr", parent=BODY, textColor=colors.white)


def inr(value) -> str:
    amount = f"{value:,.2f}"
    whole, _, frac = amount.replace(",", "").partition(".")
    # Indian digit grouping (12,34,567.00)
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"Rs. {whole}.{frac}"


def _header(school: School, title: str) -> list:
    return [
        Paragraph(school.name, H_SCHOOL),
        Paragraph(f"{school.address}<br/>Phone: {school.phone} &nbsp;|&nbsp; Email: {school.email or '-'}", H_SUB),
        Spacer(1, 4 * mm),
        Table([[""]], colWidths=[180 * mm], rowHeights=[1.2],
              style=TableStyle([("LINEABOVE", (0, 0), (-1, -1), 1.2, BROWN)])),
        Paragraph(title, H_DOC),
    ]


def _kv_table(rows: list[tuple[str, str, str, str]]) -> Table:
    t = Table([[Paragraph(f"<b>{a}</b>", BODY), Paragraph(b, BODY), Paragraph(f"<b>{c}</b>", BODY), Paragraph(d, BODY)]
               for a, b, c, d in rows], colWidths=[34 * mm, 56 * mm, 34 * mm, 56 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BROWN_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.6, BROWN_LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _amount_table(header: list[str], rows: list[list], total_rows: list[list], widths) -> Table:
    data = [[Paragraph(f"<b>{h}</b>", HDR) for h in header]]
    data += [[Paragraph(str(c), RIGHT if i == len(r) - 1 else BODY) for i, c in enumerate(r)] for r in rows]
    data += [[Paragraph(f"<b>{c}</b>", RIGHT if i == len(r) - 1 else BODY) for i, c in enumerate(r)] for r in total_rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BROWN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, BROWN_LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(len(total_rows)):
        style.append(("BACKGROUND", (0, len(data) - 1 - i), (-1, len(data) - 1 - i), BROWN_LIGHT))
    t.setStyle(TableStyle(style))
    return t


def _demo_watermark(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 54)
    canvas.setFillColor(colors.Color(0.42, 0.26, 0.15, alpha=0.07))
    canvas.translate(A4[0] / 2, A4[1] / 2)
    canvas.rotate(35)
    canvas.drawCentredString(0, 0, "DEMO RECORD")
    canvas.restoreState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(15 * mm, 10 * mm, f"Generated {datetime.now().strftime('%d %b %Y %H:%M')} – computer generated document, no signature required.")


def _build(story: list) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=16 * mm)
    doc.build(story, onFirstPage=_demo_watermark, onLaterPages=_demo_watermark)
    return buffer.getvalue()


def fee_receipt_pdf(*, school: School, receipt_number: str, student_name: str, roll_number: str, class_label: str,
                    academic_year: str, payment_date: str, category_label: str, description: str, amount,
                    payment_ref: str, method_label: str, total_paid, remaining_balance) -> bytes:
    story = _header(school, "FEE RECEIPT")
    story += [
        _kv_table([
            ("Receipt No.", receipt_number, "Payment Date", payment_date),
            ("Student Name", student_name, "Roll Number", roll_number),
            ("Class", class_label, "Academic Year", academic_year),
            ("Payment Ref.", payment_ref, "Payment Mode", method_label),
        ]),
        Spacer(1, 6 * mm),
        _amount_table(["Fee Category", "Description", "Amount Paid"],
                      [[category_label, description, inr(amount)]],
                      [["", "Amount received (this receipt)", inr(amount)],
                       ["", "Total paid this academic year", inr(total_paid)],
                       ["", "Remaining balance after this payment", inr(remaining_balance)]],
                      [45 * mm, 85 * mm, 50 * mm]),
        Spacer(1, 10 * mm),
        Paragraph("This is a <b>demonstration receipt</b> generated from sample data for the school attendance "
                  "management system demo. No real payment was processed.", SMALL),
    ]
    return _build(story)


def salary_slip_pdf(*, school: School, salary: dict, teacher: dict) -> bytes:
    story = _header(school, f"SALARY SLIP – {salary['month_label'].upper()}")
    story += [
        _kv_table([
            ("Teacher Name", teacher["full_name"], "Teacher ID", teacher["employee_code"]),
            ("Designation", teacher["designation"], "Salary Month", salary["month_label"]),
            ("Working Days", str(salary["working_days"]), "Days Present", str(salary["days_present"])),
            ("Payment Status", salary["status_label"], "Payment Date", salary["payment_date"] or "—"),
        ]),
        Spacer(1, 6 * mm),
    ]
    from decimal import Decimal

    earnings = [["Basic Salary", inr(Decimal(salary["basic_salary"]))]] + [
        [a["label"], inr(Decimal(a["amount"]))] for a in salary["allowance_breakdown"]
    ]
    deductions = [[d["label"] + (" (penalty)" if d["is_penalty"] else ""), inr(Decimal(d["amount"]))] for d in salary["deductions"]]
    story.append(_amount_table(["Earnings", "Amount"], earnings, [["Gross Salary", inr(Decimal(salary["gross_salary"]))]],
                               [130 * mm, 50 * mm]))
    story.append(Spacer(1, 5 * mm))
    story.append(_amount_table(
        ["Deductions", "Amount"], deductions or [["No deductions", inr(Decimal("0"))]],
        [["Penalty deductions", inr(Decimal(salary["penalty_deductions"]))],
         ["Total Deductions", inr(Decimal(salary["total_deductions"]))]],
        [130 * mm, 50 * mm]))
    story.append(Spacer(1, 5 * mm))
    net = Table([[Paragraph("<b>NET SALARY</b>", BODY), Paragraph(f"<b>{inr(Decimal(salary['net_salary']))}</b>", RIGHT)]],
                colWidths=[130 * mm, 50 * mm])
    net.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BROWN_LIGHT), ("BOX", (0, 0), (-1, -1), 1, BROWN),
                             ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [net, Spacer(1, 10 * mm),
              Paragraph("Demonstration salary slip generated from predefined sample data.", SMALL)]
    return _build(story)
