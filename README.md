# Sri Vidya Mandir School – Attendance Management System

A working **Parent Portal** and **Teacher Portal** for school attendance, leave, fees and salary, built as a
**localhost demonstration** (shown over Google Meet). All people, numbers and payments are synthetic sample data.

| Part | Technology |
|---|---|
| Frontend | React 18 + Vite, Tailwind CSS 4, React Router, TanStack Query, Recharts, React Hook Form + Zod, lucide-react, date-fns, react-hot-toast |
| Backend | Python + FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, pyotp, qrcode, pwdlib (Argon2), PyJWT, ReportLab, openpyxl |
| Databases | **PostgreSQL** – all official data · **MongoDB** – activity logs, notification history, system events only |

Design notes, ER diagram, roles/permissions, business rules and the full API list: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## 0. Already set up on this computer

PostgreSQL 16 is installed as a portable server in `C:\Users\Ragunathan\PostgreSQL16` (no Windows service, so start
it yourself), the databases are created and the demo data is loaded. Before each demo, run these from the project folder:

```powershell
.\start-database.ps1                                            # 1. start PostgreSQL (port 5432)
cd backend; .\.venv\Scripts\python.exe -m scripts.seed          # 2. optional: refresh demo data for today
.\.venv\Scripts\uvicorn.exe app.main:app --port 8000            # 3. backend  (keep this window open)
# new window:
cd frontend; npm run dev                                        # 4. frontend → open http://localhost:5173
```

`.\stop-database.ps1` stops PostgreSQL. If PowerShell blocks the scripts, run
`powershell -ExecutionPolicy Bypass -File .\start-database.ps1`. PostgreSQL superuser: `postgres` / `postgres`
(local only). App user: `sams_user` / `sams_password`.

The sections below describe a fresh installation on another computer.

## 1. Prerequisites (Windows)

| Tool | Version | Check |
|---|---|---|
| Python | 3.11 – 3.13 | `python --version` |
| Node.js | 18+ | `node --version` |
| PostgreSQL | 14+ | `psql --version` |
| MongoDB Community | 6+ (service running) | `mongosh --eval "db.version()"` |

**Install PostgreSQL** (if missing) – either the installer from <https://www.postgresql.org/download/windows/>
or `winget install PostgreSQL.PostgreSQL.16`. Remember the password you set for the `postgres` superuser and make sure
the "postgresql-x64-16" Windows service is running. Add `C:\Program Files\PostgreSQL\16\bin` to `PATH` to use `psql`.

MongoDB only stores supplementary logs; the app keeps working (with a warning in the console) if it is not running.

## 2. One-time setup

```powershell
# --- database (run as the postgres superuser) ---------------------------------
cd backend
psql -U postgres -f scripts/setup_db.sql          # creates role sams_user + databases sams_db, sams_test

# --- backend --------------------------------------------------------------------
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m scripts.make_env                         # writes .env with fresh random secrets (skip if .env exists)
alembic upgrade head                               # creates all 43 tables
python -m scripts.seed                             # loads demo data (dates are relative to today)

# --- frontend -------------------------------------------------------------------
cd ..\frontend
npm install
copy .env.example .env                             # optional – only if the backend is not on :8000
```

If your PostgreSQL user/password differ, edit `DATABASE_URL` in `backend/.env`.

## 3. Running the demo

Two terminals:

```powershell
# Terminal 1 – backend  (http://localhost:8000, API docs at http://localhost:8000/docs)
cd backend; .\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000

# Terminal 2 – frontend (http://localhost:5173)
cd frontend
npm run dev
```

Open **http://localhost:5173**. The Vite dev server proxies `/api` to the backend, so the session cookie is same-origin.

> **Re-seed before each demo:** `python -m scripts.seed`. Attendance, pending leave, substitute duties and salary
> months are generated relative to the current date, so the most recent days always have data to show.

## 4. Demo credentials

### Parents (mobile number **or** e-mail + student roll number → OTP)

| Parent | Mobile | E-mail | Roll number(s) |
|---|---|---|---|
| Ramesh Venkatesan (father, two children) | `9840011001` | `ramesh.venkatesan@example.com` | `6A01` Aditi · `8A03` Karthik |
| Lalitha Ramesh (mother, same children) | `9840011039` | `lalitha.ramesh@example.com` | `6A01` · `8A03` |
| Mohan Krishnaswamy (two children) | `9840011019` | `mohan.krishnaswamy@example.com` | `6B09` Sanjana · `7A09` Varun |
| Any other parent | `9840011002` … `9840011038` | | the roll number of their child |

**OTP:** the 6-digit code is printed in the **backend terminal** and, because `ENABLE_DEMO_OTP_INBOX=true`, the OTP
screen has a clearly-labelled *Demo message inbox* button that shows the simulated SMS. Codes are random, expire after
5 minutes, allow 5 attempts and can be resent after 30 seconds.

### Teachers (Teacher ID or e-mail + password → Google Authenticator)

Password for every demo teacher: **`Teacher@2026`**

| ID | Name | Role in the demo |
|---|---|---|
| `T1001` | Lakshmi Narayanan | Mathematics, **class teacher 6-A** – mark attendance, approve leave (Meera, Aditi), add/remove students in 6-A |
| `T1002` | Anitha Joseph | English, **class teacher 6-B** – **approves substitute submissions** for her periods |
| `T1003` | Mohammed Irfan | Science, class teacher 7-A |
| `T1004` | Priya Raman | Social Science, class teacher 8-A |
| `T1005` | Suresh Kumar | Tamil – subject teacher only (shows that non-class-teachers cannot manage students) |
| `T1006` | Deepa Krishnan | Computer Science – also covers a Tamil period as substitute |
| `T1007` | Arun Prakash | Physical Education |
| `T1008` | Kavitha Subramanian | **Substitute pool** – marks temporary attendance for T1002's classes |

E-mail login also works, e.g. `lakshmi.t1001@srividyamandir.example`.

**Google Authenticator:** the first sign-in of each teacher shows a QR code – scan it with Google Authenticator
(**+ → Scan a QR code**) and enter the 6-digit code. Later sign-ins just ask for the code. Each code can be used once,
so for an add/update/remove-student action right after signing in, wait for the next code.

Presenter helpers (run in the backend terminal; never exposed through the API):

```powershell
python -m scripts.totp_tool status          # who has enrolled
python -m scripts.totp_tool code T1001      # print the current code if no phone is at hand
python -m scripts.totp_tool reset T1001     # show the QR code again at next login
```

### Teacher session windows

Configured in `backend/.env` (school timezone `Asia/Kolkata`):

```
SCHOOL_OPEN_TIME=08:00   LUNCH_BREAK_START=12:30   LUNCH_BREAK_END=13:15   SCHOOL_CLOSING_TIME=16:30
ALLOW_OFF_HOURS_TEACHER_LOGIN=true   OFF_HOURS_SESSION_MINUTES=60
```

A morning login ends at the lunch break; signing in again starts an afternoon session that ends at closing time. The
backend rejects expired sessions on every request; the header shows the remaining time. For evening demos, logins
outside school hours get a 60-minute "demo session" (set `ALLOW_OFF_HOURS_TEACHER_LOGIN=false` to forbid them).
**To demonstrate expiry**, set `LUNCH_BREAK_START` (or `SCHOOL_CLOSING_TIME`) a few minutes ahead, restart the
backend and sign in.

## 5. Suggested demo walkthrough (≈15 min)

1. **Landing page** – school information and the two portal entries.
2. **Parent** `9840011001` + `6A01` → OTP (demo inbox) → switch between Aditi and Karthik in the header.
   * Student Details → Attendance: weekly/monthly/yearly charts, period-wise daily table (✓ / ✕), holidays never absent,
     approved vs pending leave.
   * Leave Information → submit a leave request (optionally attach a PDF).
   * Payment & Receipts → fee categories, overdue vs balance, payment history (including a failed payment), balance
     ledger, download a PDF receipt.
   * History → filter by dates; previous-year records.
3. **Teacher `T1008`** → Substitute Approval → *Temporary attendance* → mark one of the duties → submitted for approval.
4. **Teacher `T1002`** → Substitute Approval → *Approvals* → review the photos/summary → approve one, reject the other
   with a reason → audit trail.
5. **Teacher `T1001`** → Attendance → choose a recent date → the timetable shows unmarked periods → mark the class →
   try again (duplicate is refused) → correct a single record with a reason.
   * Leave requests → approve Meera's pending leave (her absences become approved leave).
   * Reports & analytics → class/student reports, top absentees, repeated absences, monthly summary, Excel export.
   * Add & Remove Students → add a student (photo + authenticator code), then deactivate with a reason; history is kept.
   * Student Details → emergency contacts search · Salary → history, penalties, PDF salary slip.
6. **Teacher `T1005`** → Add & Remove Students shows "class teachers only".

## 6. Tests

```powershell
cd backend; .\.venv\Scripts\Activate.ps1
pytest                                   # unit tests – no database needed

# end-to-end API workflows against the separate test database (it is migrated and re-seeded):
$env:TEST_DATABASE_URL="postgresql+psycopg://sams_user:sams_password@localhost:5432/sams_test"
pytest
```

The integration suite covers: CSRF header, parent OTP (wrong code, single use), IDOR protection, every parent endpoint,
ledger reconciliation, receipt PDF, teacher TOTP enrolment, timetable-validated marking and duplicate prevention,
leave approval converting absences, substitute submit → approve/reject (no double finalisation), student add/deactivate
with TOTP and class-teacher scope, salary isolation and the restricted directory fields.

## 7. Project structure

```
backend/
  app/
    api/routes/        public, auth, parent, teacher, teacher_substitute, teacher_students, teacher_salary, files
    api/deps.py        session → current user, role/permission guards, parent→student IDOR guard
    core/              config, security (Argon2, HMAC OTP, Fernet, JWT challenge), errors, rate limit, permissions
    db/                SQLAlchemy session/base, MongoDB client
    middleware/        CSRF header check, security headers
    models/            school, people, auth, attendance, leave, fees, salary, audit
    repositories/      shared queries
    schemas/           Pydantic request models
    services/          attendance engine & reports, marking, substitute, leave, fees, salary, PDFs, analytics,
                       student admin, OTP/TOTP/session, audit
    utils/             time helpers, validated file storage
  alembic/             migrations (0001_initial_schema)
  scripts/             seed, make_env, totp_tool, setup_db.sql, avatars
  tests/               unit + integration tests
  uploads/             photos & leave documents (served only through authorised endpoints)
frontend/
  src/pages            landing page, parent/teacher login
  src/layouts          portal shell (sidebar, header)
  src/modules/parent   Student Details, Attendance, Leave, Payments, History
  src/modules/teacher  Teacher Details, Attendance (+ leave approvals, reports), Substitute, Manage Students,
                       Student Details, Salary
  src/components       UI primitives, attendance charts/calendar, attendance sheet
  src/services         axios client + endpoint map
  src/context          authentication context
docs/ARCHITECTURE.md
```

## 8. Security summary

Argon2 password hashing · OTP stored as HMAC, expiring, attempt-limited, single-use · TOTP with replay protection,
secrets encrypted at rest and never returned · server-side session expiry, HttpOnly SameSite cookies (no tokens in
browser storage) · CSRF header check · CORS limited to the frontend origin · per-IP login rate limits and teacher
lock-out · role permissions + data scopes on every endpoint (parents → linked students, teachers → timetable /
class-teacher sections) · Pydantic validation · ORM-parameterised queries · uploaded files type-checked by content,
size-limited, re-encoded and served only to authorised users · generic error messages · audit logs in PostgreSQL
(plus MongoDB activity feed) · no hard deletes of students, attendance or financial history.

**Demo-only switches to turn off for any real deployment:** `ENABLE_DEMO_OTP_INBOX=false`,
`ALLOW_OFF_HOURS_TEACHER_LOGIN=false`, `SESSION_COOKIE_SECURE=true` behind HTTPS, and a real SMS/e-mail provider.

## 9. Not in this version (by design)

School Management Portal (fee/salary/admission management and school configuration), real SMS/e-mail delivery,
online payments, Docker, cloud hosting. The database already contains the `school_admin` role, permissions and
tables needed to add that portal later – see section 10 of the architecture document.

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `connection refused … 5432` | Start the PostgreSQL service; check `DATABASE_URL` in `backend/.env` |
| `No current academic year is configured` | Run `alembic upgrade head` then `python -m scripts.seed` |
| Frontend says "Cannot reach the server" | Start the backend on port 8000 (or set `VITE_BACKEND_URL` in `frontend/.env`) |
| Teacher login refused outside hours | Set `ALLOW_OFF_HOURS_TEACHER_LOGIN=true` or adjust the school times |
| "Invalid or already-used authenticator code" | Wait for the next 30-second code; check the phone's clock is automatic |
| POST from Swagger `/docs` returns 403 | Add header `X-Requested-With: SAMS` (CSRF protection) – the web app sends it automatically |
| MongoDB warnings in the console | Start the MongoDB service – logs are optional, the app still works |
