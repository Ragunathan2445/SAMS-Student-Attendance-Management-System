"""End-to-end API workflows against PostgreSQL (requires TEST_DATABASE_URL)."""
import json
import os
from pathlib import Path

import pyotp
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def app_env():
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    from scripts.seed import run

    run()
    from app.main import app

    return app


def new_client(app):
    from fastapi.testclient import TestClient

    c = TestClient(app)
    c.headers["X-Requested-With"] = "SAMS"
    return c


def totp_code(teacher_code: str, reset_counter: bool = True) -> str:
    from sqlalchemy import select

    from app.core.security import decrypt_secret
    from app.db.session import SessionLocal
    from app.models import Teacher, TeacherTOTP

    with SessionLocal() as db:
        t = db.scalar(select(Teacher).where(Teacher.employee_code == teacher_code))
        row = db.scalar(select(TeacherTOTP).where(TeacherTOTP.teacher_id == t.id))
        if reset_counter:  # tests cannot wait 30 s for the next code
            row.last_used_counter = None
            db.commit()
        return pyotp.TOTP(decrypt_secret(row.secret_encrypted)).now()


def teacher_login(app, code: str):
    c = new_client(app)
    r = c.post("/api/auth/teacher/login", json={"identifier": code, "password": "Teacher@2026"})
    assert r.status_code == 200, r.text
    body = r.json()
    if body["next_step"] == "enroll":
        assert c.post("/api/auth/teacher/totp/setup", json={"challenge_token": body["challenge_token"]}).json()["qr_code"]
    r = c.post("/api/auth/teacher/totp/verify", json={"challenge_token": body["challenge_token"], "code": totp_code(code)})
    assert r.status_code == 200, r.text
    return c


def parent_login(app, identifier="9840011001", roll="6A01"):
    c = new_client(app)
    r = c.post("/api/auth/parent/request-otp", json={"identifier": identifier, "roll_number": roll})
    assert r.status_code == 200, r.text
    rid = r.json()["request_id"]
    code = c.get(f"/api/auth/parent/demo-inbox/{rid}").json()["code"]
    assert c.post("/api/auth/parent/verify-otp", json={"request_id": rid, "code": code}).status_code == 200
    return c


def test_csrf_header_required(app_env):
    from fastapi.testclient import TestClient

    r = TestClient(app_env).post("/api/auth/teacher/login", json={"identifier": "T1001", "password": "x"})
    assert r.status_code == 403


def test_parent_otp_flow_and_access_control(app_env):
    c = new_client(app_env)
    bad = c.post("/api/auth/parent/request-otp", json={"identifier": "9840011001", "roll_number": "7A01"})
    assert bad.status_code == 401 and "do not match" in bad.json()["detail"]
    r = c.post("/api/auth/parent/request-otp", json={"identifier": "ramesh.venkatesan@example.com", "roll_number": "6a01"})
    rid = r.json()["request_id"]
    code = c.get(f"/api/auth/parent/demo-inbox/{rid}").json()["code"]
    wrong = "000000" if code != "000000" else "111111"
    r = c.post("/api/auth/parent/verify-otp", json={"request_id": rid, "code": wrong})
    assert r.status_code == 401 and "remaining" in r.json()["detail"]
    assert c.post("/api/auth/parent/verify-otp", json={"request_id": rid, "code": code}).status_code == 200
    # OTP is single use
    assert c.post("/api/auth/parent/verify-otp", json={"request_id": rid, "code": code}).status_code == 401

    kids = c.get("/api/parent/students").json()["students"]
    assert {k["roll_number"] for k in kids} == {"6A01", "8A03"}
    other = parent_login(app_env, "9840011002", "6A02").get("/api/parent/students").json()["students"][0]["id"]
    assert c.get(f"/api/parent/students/{other}/profile").status_code == 404          # IDOR blocked
    assert c.get(f"/api/files/students/{other}/photo").status_code == 404
    assert c.get("/api/teacher/profile").status_code == 403                            # role check

    sid = kids[0]["id"]
    for path in ("attendance/overview", "attendance/daily", "attendance/weekly", "attendance/monthly",
                 "attendance/yearly", "attendance/history", "fees", "payments", "balance-history", "academic-records"):
        assert c.get(f"/api/parent/students/{sid}/{path}").status_code == 200, path
    fees = c.get(f"/api/parent/students/{sid}/fees").json()
    assert fees["ledger_reconciled"] is True
    ledger = c.get(f"/api/parent/students/{sid}/balance-history").json()
    assert ledger["chain_consistent"] and ledger["closing_balance"] == fees["balance_amount"]
    pay = next(p for p in c.get(f"/api/parent/students/{sid}/payments").json()["payments"] if p["receipt_available"])
    pdf = c.get(f"/api/parent/payments/{pay['id']}/receipt")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/parent/students").status_code == 401


def test_teacher_attendance_marking(app_env):
    c = teacher_login(app_env, "T1001")
    me = c.get("/api/auth/me").json()
    assert me["role"] == "teacher" and me["session"]["type"] in ("morning", "afternoon", "extended")
    # T1001's periods on the last two working days were left unmarked by the seed.
    from datetime import timedelta

    from app.utils.timeutils import today_local

    day, slot = today_local(), None
    for back in range(1, 8):
        d = (today_local() - timedelta(days=back)).isoformat()
        slots = c.get(f"/api/teacher/attendance/slots?date={d}").json()
        free = [s for s in slots["slots"] if not s["is_marked"]]
        if free:
            day, slot = d, free[0]
            break
    assert slot, "expected an unmarked T1001 slot in the last week"
    sheet = c.get(f"/api/teacher/attendance/sheet?date={day}&section_id={slot['section_id']}&period_id={slot['period_id']}").json()
    records = [{"student_id": s["student_id"], "status": "leave" if s["leave_status"] == "approved" else "present"}
               for s in sheet["students"]]
    records[-1] = {"student_id": records[-1]["student_id"], "status": "absent", "absence_reason": "fever"}
    body = {"date": day, "section_id": slot["section_id"], "period_id": slot["period_id"], "records": records}
    assert c.post("/api/teacher/attendance", json=body).status_code == 201
    assert c.post("/api/teacher/attendance", json=body).status_code == 409             # duplicate blocked
    # a period that is not T1001's
    other = {**body, "period_id": slot["period_id"] % 7 + 1}
    assert c.post("/api/teacher/attendance", json=other).status_code in (400, 403, 409)
    assert c.get("/api/teacher/analytics/class").status_code == 200
    assert c.get("/api/teacher/analytics/export").content[:2] == b"PK"


def test_leave_approval_converts_absences(app_env):
    c = teacher_login(app_env, "T1001")
    pending = c.get("/api/teacher/leave-requests?status=pending").json()["requests"]
    meera = next(lv for lv in pending if lv["roll_number"] == "6A07")
    r = c.post(f"/api/teacher/leave-requests/{meera['id']}/decision", json={"action": "approved", "remarks": "Get well soon"})
    assert r.status_code == 200 and r.json()["attendance_rows_updated"] > 0
    again = c.post(f"/api/teacher/leave-requests/{meera['id']}/decision", json={"action": "approved"})
    assert again.status_code == 409
    # T1005 is not the class teacher of 6A
    other = teacher_login(app_env, "T1005")
    aditi = next(lv for lv in pending if lv["roll_number"] == "6A01")
    assert other.post(f"/api/teacher/leave-requests/{aditi['id']}/decision",
                      json={"action": "approved"}).status_code == 403


def test_substitute_flow(app_env):
    sub = teacher_login(app_env, "T1008")
    assignments = sub.get("/api/teacher/substitute/assignments").json()["assignments"]
    open_one = next(a for a in assignments if a["can_submit"])
    sheet = sub.get(f"/api/teacher/substitute/assignments/{open_one['assignment_id']}/sheet").json()
    recs = [{"student_id": s["student_id"], "status": "leave" if s["leave_status"] == "approved" else "present"}
            for s in sheet["students"]]
    r = sub.post(f"/api/teacher/substitute/assignments/{open_one['assignment_id']}/submissions", json={"records": recs})
    assert r.status_code == 201, r.text
    sid = r.json()["submission_id"]
    assert sub.post(f"/api/teacher/substitute/submissions/{sid}/approve").status_code == 403   # not responsible

    reg = teacher_login(app_env, "T1002")
    pend = reg.get("/api/teacher/substitute/approvals?status=pending").json()["submissions"]
    assert any(p["submission_id"] == sid for p in pend)
    assert reg.post(f"/api/teacher/substitute/submissions/{sid}/approve").status_code == 200
    assert reg.post(f"/api/teacher/substitute/submissions/{sid}/approve").status_code == 409   # no double finalisation
    other = next(p for p in pend if p["submission_id"] != sid)
    assert reg.post(f"/api/teacher/substitute/submissions/{other['submission_id']}/reject",
                    json={"reason": "Count mismatch with register"}).status_code == 200
    detail = reg.get(f"/api/teacher/substitute/submissions/{other['submission_id']}").json()
    assert detail["status"] == "rejected" and detail["audit_trail"][-1]["action"] == "rejected"


def test_student_management_requires_totp_and_class_teacher(app_env):
    c = teacher_login(app_env, "T1001")
    sections = c.get("/api/teacher/sections").json()["class_teacher_sections"]
    payload = {"totp_code": "000000", "full_name": "Test Student", "roll_number": "6A99", "admission_number": "SVM-T-1",
               "date_of_birth": "2015-04-01", "gender": "Female", "section_id": sections[0]["id"],
               "parent_name": "Test Parent", "parent_mobile": "9840099999", "parent_email": "test.parent@example.com",
               "address": "1, Test Street, Chennai", "reason": "New admission for testing"}
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (60, 60), "brown").save(buf, format="PNG")

    def post(p):
        return c.post("/api/teacher/manage/students", data={"payload": json.dumps(p)},
                      files={"photo": ("p.png", buf.getvalue(), "image/png")})

    assert post(payload).status_code == 403                                   # bad TOTP
    r = post({**payload, "totp_code": totp_code("T1001")})
    assert r.status_code == 201, r.text
    new_id = r.json()["id"]
    fee = c.get("/api/teacher/manage/students?q=Test").json()["students"][0]
    assert fee["parent_email"] == "test.parent@example.com"
    r = c.post(f"/api/teacher/manage/students/{new_id}/deactivate",
               json={"totp_code": totp_code("T1001"), "reason": "Transferred to another school", "confirm": True})
    assert r.status_code == 200 and r.json()["status"] == "inactive"
    history = c.get(f"/api/teacher/manage/students/{new_id}/history").json()["history"]
    assert [h["action"] for h in history] == ["deactivate", "create"]
    # non-class-teacher cannot manage students
    t5 = teacher_login(app_env, "T1005")
    assert t5.get("/api/teacher/manage/students").json()["students"] == []


def test_salary_and_directory(app_env):
    c = teacher_login(app_env, "T1003")
    sal = c.get("/api/teacher/salary").json()["salaries"]
    assert sal and all(s["teacher_code"] == "T1003" for s in sal)
    pdf = c.get(f"/api/teacher/salary/{sal[-1]['id']}/slip")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    other = teacher_login(app_env, "T1001").get("/api/teacher/salary").json()["salaries"][0]["id"]
    assert c.get(f"/api/teacher/salary/{other}").status_code == 404           # cannot read others' salary
    directory = c.get("/api/teacher/students/directory?q=aditi").json()["students"]
    assert directory and set(directory[0]) == {"id", "full_name", "roll_number", "class_label", "photo_url",
                                               "parent_name", "parent_mobile", "parent_email", "address"}
