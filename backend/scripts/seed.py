from __future__ import annotations

import random
import shutil
from collections import defaultdict
from datetime import date, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import insert, text

from app.core.config import get_settings
from app.core.permissions import PERMISSIONS, ROLES
from app.core.security import hash_password
from app.db import mongo
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import (
    AcademicYear, Attendance, AttendanceApproval, AttendanceSubmission, AttendanceSubmissionItem, FeeAdjustment,
    FeeBalanceHistory, FeePayment, FeeReceipt, FeeStructure, LeaveApproval, LeaveRequest, Parent, ParentStudent,
    Period, Permission, Role, RolePermission, SalaryDeduction, SalaryPayment, School, SchoolCalendar, SchoolClass,
    Section, Student, StudentAcademicRecord, StudentChangeHistory, StudentFeeRecord, Subject, SubstituteAssignment,
    Teacher, TeacherAssignment, TeacherClassAssignment, TeacherSalary, TeacherSubjectAssignment, Timetable,
    UserAccount,
)
from app.services.calendar_service import daterange, default_day_type
from app.utils.timeutils import today_local, utcnow
from scripts.avatars import place_photo

R = random.Random(2026)
TEACHER_PASSWORD = "Teacher@2026"
D = Decimal
TWO = Decimal("0.01")

SUBJECTS = [("ENG", "English"), ("MAT", "Mathematics"), ("SCI", "Science"), ("SST", "Social Science"),
            ("TAM", "Tamil"), ("CSC", "Computer Science"), ("PED", "Physical Education")]
TEACHERS = [
    # code, name, designation, qualification, subject, joined, basic
    ("T1001", "Lakshmi Narayanan", "PG Assistant – Mathematics", "M.Sc., B.Ed.", "MAT", date(2012, 6, 4), 42000),
    ("T1002", "Anitha Joseph", "BT Assistant – English", "M.A., B.Ed.", "ENG", date(2015, 6, 1), 36000),
    ("T1003", "Mohammed Irfan", "BT Assistant – Science", "M.Sc., B.Ed.", "SCI", date(2016, 6, 6), 35000),
    ("T1004", "Priya Raman", "BT Assistant – Social Science", "M.A., B.Ed.", "SST", date(2014, 6, 2), 36500),
    ("T1005", "Suresh Kumar", "Tamil Pandit", "M.A. (Tamil), B.Ed.", "TAM", date(2011, 6, 6), 38000),
    ("T1006", "Deepa Krishnan", "Computer Instructor", "MCA", "CSC", date(2019, 6, 3), 30000),
    ("T1007", "Arun Prakash", "Physical Education Director", "M.P.Ed.", "PED", date(2017, 6, 5), 31000),
    ("T1008", "Kavitha Subramanian", "Assistant Teacher (Substitute Pool)", "B.Sc., B.Ed.", None, date(2022, 6, 6), 26000),
]
SECTIONS = [("Grade 6", 6, "A", "Room 12"), ("Grade 6", 6, "B", "Room 13"), ("Grade 7", 7, "A", "Room 21"),
            ("Grade 8", 8, "A", "Room 31")]
CLASS_TEACHERS = {0: "T1001", 1: "T1002", 2: "T1003", 3: "T1004"}
STUDENTS = {
    0: [("Aditi Ramesh", "F"), ("Arjun Selvam", "M"), ("Bhavya Srinivasan", "F"), ("Dhruv Natarajan", "M"),
        ("Ishita Chandran", "F"), ("Kavin Murugan", "M"), ("Meera Balaji", "F"), ("Nikhil Varadhan", "M"),
        ("Pooja Elango", "F"), ("Rohan Thomas", "M")],
    1: [("Ananya Gopal", "F"), ("Ashwin Raj", "M"), ("Diya Mahesh", "F"), ("Harish Kannan", "M"),
        ("Janani Prakash", "F"), ("Lokesh Sundar", "M"), ("Nandhini Ravi", "F"), ("Pranav Iyer", "M"),
        ("Sanjana Mohan", "F"), ("Vishal Anand", "M")],
    2: [("Akash Pillai", "M"), ("Bhuvana Shankar", "F"), ("Charan Dev", "M"), ("Divya Rajan", "F"),
        ("Gautham Menon", "M"), ("Harini Sekar", "F"), ("Kiran Xavier", "M"), ("Lavanya Kumar", "F"),
        ("Varun Mohan", "M"), ("Yamini Krishnan", "F")],
    3: [("Abinaya Raghu", "F"), ("Barath Kumar", "M"), ("Karthik Ramesh", "M"), ("Deepika Arul", "F"),
        ("Farhan Ali", "M"), ("Gayathri Venkat", "F"), ("Hari Prasad", "M"), ("Keerthana Siva", "F"),
        ("Naveen Babu", "M"), ("Shruthi Vasan", "F")],
}
FAMILIES = {  # shared parents (siblings)
    "Ramesh Venkatesan": ["6A01", "8A03"],
    "Mohan Krishnaswamy": ["6B09", "7A09"],
}
SURNAMES = ["Venkatesan", "Raghavan", "Subramanian", "Rajagopal", "Sundaram", "Natarajan", "Shanmugam",
            "Krishnan", "Pandian", "Arumugam", "Swaminathan", "Govindan"]
LOCALITIES = ["Anna Nagar", "Kilpauk", "Aminjikarai", "Shenoy Nagar", "Mogappair", "Villivakkam",
              "Arumbakkam", "Koyambedu", "Kolathur", "Ayanavaram"]
STREETS = ["2nd Main Road", "Gandhi Street", "Lake View Road", "Temple Street", "Park Avenue", "School Road",
           "Bharathi Salai", "Nehru Street", "Kamaraj Road", "Market Street"]
BLOOD = ["A+", "B+", "O+", "AB+", "O+", "B+", "A-", "O-", "B-"]
ABSENCE_REASONS = (["fever"] * 30 + ["uninformed"] * 25 + ["personal"] * 15 + ["medical_appointment"] * 10
                   + ["family_function"] * 10 + ["other"] * 10)


def m(value) -> Decimal:
    return D(value).quantize(TWO, rounding=ROUND_HALF_UP)


# =============================================================================== calendar
def academic_bounds(today: date) -> tuple[int, date, date]:
    y = today.year if today.month >= 6 else today.year - 1
    return y, date(y, 6, 1), date(y + 1, 4, 30)


def calendar_entries(y: int) -> dict[date, tuple[str, str]]:
    e: dict[date, tuple[str, str]] = {}
    for offset in range(11):  # June .. April
        yy, mm = (y, 6 + offset) if offset < 7 else (y + 1, offset - 6)
        sats = [d for d in daterange(date(yy, mm, 1), date(yy, mm, 28) + timedelta(days=3))
                if d.month == mm and d.isoweekday() == 6]
        for idx, label in ((1, "Second Saturday"), (3, "Fourth Saturday")):
            if idx < len(sats):
                e[sats[idx]] = ("school_holiday", label)
    fixed = [
        (date(y, 8, 15), "school_holiday", "Independence Day"),
        (date(y, 10, 2), "school_holiday", "Gandhi Jayanti"),
        (date(y + 1, 1, 26), "school_holiday", "Republic Day"),
        (date(y, 9, 4), "festival_holiday", "Krishna Jayanthi"),
        (date(y, 9, 14), "festival_holiday", "Vinayagar Chathurthi"),
        (date(y, 10, 19), "festival_holiday", "Ayudha Pooja"),
        (date(y, 10, 20), "festival_holiday", "Vijaya Dasami"),
        (date(y, 11, 9), "festival_holiday", "Deepavali"),
        (date(y, 12, 25), "festival_holiday", "Christmas"),
        (date(y + 1, 1, 14), "festival_holiday", "Bhogi"),
        (date(y + 1, 1, 15), "festival_holiday", "Pongal"),
        (date(y + 1, 1, 16), "festival_holiday", "Thiruvalluvar Day"),
        (date(y + 1, 4, 14), "festival_holiday", "Tamil New Year"),
        (date(y, 7, 17), "management_holiday", "Holiday declared by management – Sports Day compensation"),
        (date(y, 11, 13), "management_holiday", "Holiday declared by management – heavy rain"),
    ]
    for d in daterange(date(y, 9, 26), date(y, 10, 4)):
        e[d] = ("school_holiday", "Quarterly examination holidays")
    for d in daterange(date(y, 12, 24), date(y + 1, 1, 1)):
        e[d] = ("school_holiday", "Half-yearly holidays")
    for d, t, title in fixed:
        e[d] = (t, title)
    # A Saturday normally off, declared a working day to compensate for the rain holiday.
    nov_sats = [d for d in daterange(date(y, 11, 1), date(y, 11, 30)) if d.isoweekday() == 6]
    e[nov_sats[1]] = ("working", "Compensatory working day (for rain holiday)")
    return e


# =============================================================================== main
def wipe(db) -> None:
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    db.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    db.commit()
    photos = get_settings().upload_dir / "photos"
    if photos.exists():
        shutil.rmtree(photos)
    docs = get_settings().upload_dir / "documents"
    if docs.exists():
        shutil.rmtree(docs)


def run() -> None:
    settings = get_settings()
    today = today_local()
    y, ay_start, ay_end = academic_bounds(today)
    db = SessionLocal()
    print(f"Seeding demo data (today = {today}, academic year {y}-{str(y + 1)[2:]}) …")
    wipe(db)

    # ------------------------------------------------------------------ roles & permissions
    perms = {code: Permission(code=code, description=desc) for code, desc in PERMISSIONS.items()}
    db.add_all(perms.values())
    roles = {}
    for code, spec in ROLES.items():
        roles[code] = Role(code=code, name=spec["name"], description=spec["description"])
        db.add(roles[code])
    db.flush()
    for code, spec in ROLES.items():
        for p in spec["permissions"]:
            db.add(RolePermission(role_id=roles[code].id, permission_id=perms[p].id))

    # ------------------------------------------------------------------ school & structure
    school = School(
        code="SVM", name="Sri Vidya Mandir School", tagline="Learning with discipline, growing with values",
        about=("Sri Vidya Mandir School is a co-educational CBSE-pattern school serving families in and around "
               "Anna Nagar since 1998. We combine strong academics with sports, arts and community service, in "
               "small sections where every teacher knows every child by name."),
        highlights="Classes 1 to 12, CBSE pattern\nSmall sections of under 40 students\nSmart classrooms and "
                   "computer lab\nSchool bus service across West Chennai\nSports, music and eco clubs",
        address="No. 14, Lake View Road, Anna Nagar West, Chennai – 600 040, Tamil Nadu",
        phone="+91 44 2600 1234", email="office@srividyamandir.example", website="www.srividyamandir.example",
        established_year=1998, affiliation="Demo school – CBSE pattern (sample data)",
        principal_name="Dr. R. Meenakshi",
    )
    db.add(school)
    db.flush()
    ay = AcademicYear(school_id=school.id, name=f"{y}-{str(y + 1)[2:]}", start_date=ay_start, end_date=ay_end,
                      is_current=True, saturday_is_working=True)
    db.add(ay)
    db.flush()
    cal = calendar_entries(y)
    for d, (t, title) in sorted(cal.items()):
        if ay_start <= d <= ay_end:
            db.add(SchoolCalendar(academic_year_id=ay.id, date=d, day_type=t, title=title))

    def day_type(d: date) -> str:
        return cal[d][0] if d in cal else default_day_type(ay, d)[0]

    subjects = {}
    for code, name in SUBJECTS:
        subjects[code] = Subject(school_id=school.id, code=code, name=name)
        db.add(subjects[code])
    times = [(time(8, 30), time(9, 15)), (time(9, 15), time(10, 0)), (time(10, 15), time(11, 0)),
             (time(11, 0), time(11, 45)), (time(11, 45), time(12, 30)), (time(13, 15), time(14, 0)),
             (time(14, 0), time(14, 45))]
    periods = []
    for i, (s, e) in enumerate(times, start=1):
        p = Period(school_id=school.id, period_number=i, start_time=s, end_time=e)
        db.add(p)
        periods.append(p)
    classes, sections = {}, []
    for cname, grade, sname, room in SECTIONS:
        if cname not in classes:
            classes[cname] = SchoolClass(school_id=school.id, name=cname, grade_level=grade)
            db.add(classes[cname])
            db.flush()
        sec = Section(class_id=classes[cname].id, name=sname, room=room)
        db.add(sec)
        sections.append(sec)
    db.flush()

    # ------------------------------------------------------------------ teachers
    teachers: dict[str, Teacher] = {}
    pw_hash = hash_password(TEACHER_PASSWORD)
    for i, (code, name, desig, qual, subj, joined, _) in enumerate(TEACHERS):
        acct = UserAccount(role_id=roles["teacher"].id, username=code, password_hash=pw_hash, is_active=True)
        db.add(acct)
        db.flush()
        first = name.split()[0].lower()
        rel = f"photos/teacher_{code}.jpg"
        place_photo(f"teacher_{code}", name, settings.upload_dir / rel)
        t = Teacher(school_id=school.id, user_account_id=acct.id, employee_code=code, full_name=name,
                    email=f"{first}.{code.lower()}@srividyamandir.example", mobile=f"94440{20101 + i}",
                    designation=desig, qualification=qual, date_of_joining=joined, photo_path=rel, is_active=True)
        db.add(t)
        teachers[code] = t
    db.flush()
    subject_teacher = {subj: teachers[code] for code, _, _, _, subj, _, _ in TEACHERS if subj}

    for s_idx, sec in enumerate(sections):
        for subj, t in subject_teacher.items():
            db.add(TeacherSubjectAssignment(teacher_id=t.id, academic_year_id=ay.id, subject_id=subjects[subj].id,
                                            section_id=sec.id))
            db.add(TeacherClassAssignment(teacher_id=t.id, academic_year_id=ay.id, section_id=sec.id))
        db.add(TeacherAssignment(teacher_id=teachers[CLASS_TEACHERS[s_idx]].id, academic_year_id=ay.id,
                                 assignment_type="class_teacher", section_id=sec.id,
                                 description=f"Class teacher of {SECTIONS[s_idx][0]} – {SECTIONS[s_idx][2]}"))
    db.add(TeacherAssignment(teacher_id=teachers["T1008"].id, academic_year_id=ay.id,
                             assignment_type="substitute_pool", description="Covers classes of absent teachers"))
    db.add(TeacherAssignment(teacher_id=teachers["T1007"].id, academic_year_id=ay.id, assignment_type="coordinator",
                             description="Sports & co-curricular coordinator"))

    # ------------------------------------------------------------------ timetable (rotating)
    subj_codes = [c for c, _ in SUBJECTS]
    slots: dict[tuple[int, int, int], Timetable] = {}   # (section_idx, dow, period_no) -> slot
    for s_idx, sec in enumerate(sections):
        for dow in range(1, 7):
            n = 7 if dow <= 5 else 4
            for p in range(n):
                code = subj_codes[(p + 2 * s_idx + dow) % 7]
                slot = Timetable(academic_year_id=ay.id, section_id=sec.id, day_of_week=dow,
                                 period_id=periods[p].id, subject_id=subjects[code].id,
                                 teacher_id=subject_teacher[code].id)
                db.add(slot)
                slots[(s_idx, dow, p + 1)] = slot
    db.flush()
    teacher_busy = {(sl.teacher_id, dow, pn) for (_, dow, pn), sl in slots.items()}

    # ------------------------------------------------------------------ parents & students
    parent_role = roles["parent"].id
    parents_by_name: dict[str, Parent] = {}
    students: dict[str, Student] = {}
    student_section_idx: dict[str, int] = {}
    mobile_seq = iter(range(11001, 11999))

    def make_parent(full_name: str, relation: str, address: str, occupation: str) -> Parent:
        mobile = f"98400{next(mobile_seq)}"
        email = (full_name.lower().replace(" ", ".") + "@example.com")
        acct = UserAccount(role_id=parent_role, username=email, password_hash=None, is_active=True)
        db.add(acct)
        db.flush()
        p = Parent(school_id=school.id, user_account_id=acct.id, full_name=full_name, relation_type=relation,
                   mobile=mobile, email=email, address=address, occupation=occupation)
        db.add(p)
        db.flush()
        return p

    occupations = ["Software Engineer", "Teacher", "Bank Officer", "Business Owner", "Doctor", "Accountant",
                   "Civil Engineer", "Government Employee", "Pharmacist", "Architect"]
    for s_idx, roster in STUDENTS.items():
        grade = SECTIONS[s_idx][1]
        for n, (name, g) in enumerate(roster, start=1):
            roll = f"{grade}{SECTIONS[s_idx][2]}{n:02d}"
            first, last = name.split()[0], name.split()[-1]
            address = f"No. {R.randint(3, 98)}, {R.choice(STREETS)}, {R.choice(LOCALITIES)}, Chennai – 6000{R.randint(10, 99)}"
            family = next((fam for fam, rolls in FAMILIES.items() if roll in rolls), None)
            parent_name = family
            while parent_name is None or (not family and parent_name in parents_by_name):
                parent_name = f"{last} {R.choice(SURNAMES)}"
            if family and parent_name in parents_by_name:
                parent = parents_by_name[parent_name]
                address = parent.address
            else:
                parent = make_parent(parent_name, "Father", address, R.choice(occupations))
                parents_by_name[parent_name] = parent
            dob = date(y - grade - 5, R.randint(1, 12), R.randint(1, 28))
            admitted = date(R.choice([y - grade + 1, y - grade + 2, y - 2, y - 1]), 6, R.randint(1, 10))
            if roll == "7A07":
                admitted = ay_start + timedelta(days=70)  # mid-year admission
            rel = f"photos/student_{roll}.jpg"
            place_photo(f"student_{roll}", name, settings.upload_dir / rel)
            st = Student(
                school_id=school.id, academic_year_id=ay.id, section_id=sections[s_idx].id, roll_number=roll,
                admission_number=f"SVM-{admitted.year}-{1000 + s_idx * 50 + n:04d}", full_name=name,
                date_of_birth=dob, gender="Male" if g == "M" else "Female", blood_group=R.choice(BLOOD),
                address=address, contact_number=None if grade < 8 else f"7550{R.randint(100000, 999999)}",
                photo_path=rel, uses_school_bus=R.random() < 0.6, admission_date=admitted, status="active",
            )
            db.add(st)
            db.flush()
            db.add(ParentStudent(parent_id=parent.id, student_id=st.id, relationship_label="Father", is_primary=True))
            students[roll] = st
            student_section_idx[roll] = s_idx
    # Second guardian for the demo family (can log in separately).
    mother = make_parent("Lalitha Ramesh", "Mother", parents_by_name["Ramesh Venkatesan"].address, "Chartered Accountant")
    for roll in FAMILIES["Ramesh Venkatesan"]:
        db.add(ParentStudent(parent_id=mother.id, student_id=students[roll].id, relationship_label="Mother", is_primary=False))
    students["8A03"].uses_school_bus = True
    db.flush()

    # previous academic year records
    for roll, st in students.items():
        grade = SECTIONS[student_section_idx[roll]][1]
        if st.admission_date and st.admission_date >= ay_start:
            continue
        pct = D(R.randint(6800, 9650)) / 100
        grade_letter = "A1" if pct >= 91 else "A2" if pct >= 81 else "B1" if pct >= 71 else "B2"
        db.add(StudentAcademicRecord(
            student_id=st.id, academic_year_name=f"{y - 1}-{str(y)[2:]}", class_name=f"Grade {grade - 1}",
            section_name=SECTIONS[student_section_idx[roll]][2], overall_grade=grade_letter, percentage=pct,
            attendance_percentage=D(R.randint(8800, 9900)) / 100, result="Promoted",
            remarks=R.choice(["Consistent performer", "Active in sports", "Good improvement in Mathematics",
                              "Participates well in class", "Needs to improve handwriting"])))

    # ------------------------------------------------------------------ working-day helpers
    past_working = [d for d in daterange(ay_start, today - timedelta(days=1)) if day_type(d) == "working"]
    future_working = [d for d in daterange(today, ay_end) if day_type(d) == "working"]

    if len(past_working) < 45 or len(future_working) < 12:
        raise SystemExit("Seed expects at least 45 elapsed and 12 remaining working days in the academic year.")

    def wd(n: int) -> date:  # n-th working day before today
        return past_working[-n]

    def fwd(n: int) -> date:  # n-th working day from today (today counts as 1 if working)
        return future_working[n - 1]

    # ------------------------------------------------------------------ leave requests
    leave_specs = [
        # roll, start, end, reason, status, description, remarks, teacher(code)
        ("8A03", wd(30), wd(28), "fever", "approved", "Viral fever, doctor advised three days of rest.",
         "Get well soon. Approved.", "T1004"),
        ("6A01", wd(15), wd(15), "medical_appointment", "approved", "Dental appointment in the morning.",
         "Approved.", "T1001"),
        ("6B05", wd(40), wd(39), "family_function", "approved", "Cousin's wedding in Madurai.", "Approved.", "T1002"),
        ("8A05", wd(20), wd(20), "personal", "rejected", "Personal travel.",
         "Travel during the unit-test week is not permitted. Marked as absent.", "T1004"),
        ("6A07", wd(3), wd(2), "fever", "pending", "Fever and cold since Monday night.", None, None),
        ("6A01", fwd(6), fwd(7), "family_function", "pending", "Grandparents' 60th wedding anniversary in Trichy.",
         None, None),
        ("7A09", fwd(3), fwd(3), "medical_appointment", "pending", "Eye check-up at Sankara Nethralaya.", None, None),
    ]
    leaves_by_roll: dict[str, list[LeaveRequest]] = defaultdict(list)
    for roll, s, e, reason, status, desc, remarks, tcode in leave_specs:
        st = students[roll]
        parent = db.get(Parent, db.scalar(text("SELECT parent_id FROM parent_students WHERE student_id=:s AND is_primary"),
                                          {"s": st.id}))
        lv = LeaveRequest(student_id=st.id, parent_id=parent.id, start_date=s, end_date=e, reason=reason,
                          description=desc, status=status, teacher_remarks=remarks,
                          decided_by_teacher_id=teachers[tcode].id if tcode else None,
                          decided_at=utcnow() - timedelta(days=(today - s).days) if tcode else None)
        db.add(lv)
        db.flush()
        if tcode:
            db.add(LeaveApproval(leave_request_id=lv.id, action=status, acted_by_teacher_id=teachers[tcode].id,
                                 remarks=remarks))
        leaves_by_roll[roll].append(lv)

    # ------------------------------------------------------------------ substitute assignments
    t_reg, t_sub = teachers["T1002"], teachers["T1008"]

    def slots_of(teacher: Teacher, d: date):
        return sorted([(k, sl) for k, sl in slots.items() if sl.teacher_id == teacher.id and k[1] == d.isoweekday()],
                      key=lambda kv: kv[0][2])

    sub_assignments: list[tuple[SubstituteAssignment, str | None]] = []  # (assignment, planned submission status)

    def assign(d: date, key, sl: Timetable, substitute: Teacher, reason: str, planned: str | None):
        a = SubstituteAssignment(academic_year_id=ay.id, date=d, timetable_id=sl.id, section_id=sl.section_id,
                                 period_id=sl.period_id, regular_teacher_id=sl.teacher_id,
                                 substitute_teacher_id=substitute.id, responsible_teacher_id=sl.teacher_id,
                                 reason=reason, assigned_by="School office (demo seed)")
        db.add(a)
        sub_assignments.append((a, planned))

    plan = [(wd(6), "approved"), (wd(5), "rejected"), (wd(1), "pending"), (wd(2), None)]
    for d, planned in plan:
        day_slots = slots_of(t_reg, d)
        if day_slots:
            key, sl = day_slots[0]
            assign(d, key, sl, t_sub, f"{t_reg.full_name} on casual leave", planned)
    for n in range(1, 11):
        if n > len(future_working):
            break
        d = fwd(n)
        for key, sl in slots_of(t_reg, d)[:2]:
            assign(d, key, sl, t_sub, f"{t_reg.full_name} attending CBSE training", None)
    # A regular teacher can also substitute in a free period (T1006 covers a Tamil period).
    for n in range(1, 4):
        if n > len(future_working):
            break
        d = fwd(n)
        for key, sl in slots_of(teachers["T1005"], d):
            if (teachers["T1006"].id, d.isoweekday(), key[2]) not in teacher_busy:
                assign(d, key, sl, teachers["T1006"], "Tamil Pandit on medical leave", None)
                break
    db.flush()
    skipped_slots = {(a.date, a.timetable_id) for a, planned in sub_assignments if planned != "approved" and a.date < today}
    # Recent T1001 periods left unmarked so attendance marking can be demonstrated on any day.
    for n in (1, 2):
        for key, sl in slots_of(teachers["T1001"], wd(n)):
            skipped_slots.add((wd(n), sl.id))

    # ------------------------------------------------------------------ attendance
    print("  generating attendance …")
    forced: dict[str, dict[date, tuple[str, str | None]]] = defaultdict(dict)
    for roll, lvs in leaves_by_roll.items():
        for lv in lvs:
            for d in daterange(lv.start_date, min(lv.end_date, today - timedelta(days=1))):
                if day_type(d) != "working":
                    continue
                if lv.status == "approved":
                    forced[roll][d] = ("leave", None)
                elif lv.status == "pending":
                    forced[roll][d] = ("absent", "informed_leave")
                else:
                    forced[roll][d] = ("absent", "personal")
    for d in (wd(10), wd(9), wd(25)):
        forced["6A08"][d] = ("absent", "uninformed")
    for d in (wd(12), wd(11), wd(8)):
        forced["8A02"][d] = ("absent", "fever")
    for d in (wd(4), wd(18)):
        forced["7A05"][d] = ("absent", "uninformed")

    absence_rate = {roll: R.choice([0.02, 0.03, 0.035, 0.04, 0.05, 0.06]) for roll in students}
    absence_rate.update({"6A08": 0.09, "8A02": 0.08, "7A05": 0.1, "6B02": 0.07})
    rows = []
    status_by_day: dict[tuple[str, date], tuple[str, str | None, int | None]] = {}
    for roll, st in students.items():
        s_idx = student_section_idx[roll]
        streak = 0
        streak_reason = None
        for d in past_working:
            if st.admission_date and d < st.admission_date:
                continue
            if d in forced[roll]:
                status, reason = forced[roll][d]
                partial_from = None
            elif streak > 0:
                status, reason, partial_from = "absent", streak_reason, None
                streak -= 1
            else:
                r = R.random()
                if r < absence_rate[roll]:
                    status, reason, partial_from = "absent", R.choice(ABSENCE_REASONS), None
                    if reason == "fever" and R.random() < 0.35:
                        streak, streak_reason = R.randint(1, 2), "fever"
                elif r < absence_rate[roll] + 0.012:
                    status, reason, partial_from = "absent", "medical_appointment", R.choice([4, 5, 6])
                else:
                    status, reason, partial_from = "present", None, None
            status_by_day[(roll, d)] = (status, reason, partial_from)
            n_periods = 7 if d.isoweekday() <= 5 else 4
            for pn in range(1, n_periods + 1):
                sl = slots[(s_idx, d.isoweekday(), pn)]
                if (d, sl.id) in skipped_slots:
                    continue
                p_status, p_reason = status, reason
                if partial_from is not None:
                    p_status, p_reason = ("present", None) if pn < partial_from else ("absent", reason)
                rows.append({
                    "student_id": st.id, "section_id": st.section_id, "date": d, "period_id": sl.period_id,
                    "timetable_id": sl.id, "subject_id": sl.subject_id, "status": p_status,
                    "absence_reason": p_reason if p_status == "absent" else None, "remarks": None,
                    "marked_by_teacher_id": sl.teacher_id, "source": "regular", "submission_id": None,
                })
    db.flush()

    # substitute submissions (past)
    for a, planned in sub_assignments:
        if planned is None:
            continue
        s_idx = next(i for i, sec in enumerate(sections) if sec.id == a.section_id)
        items, counts = [], {"present": 0, "absent": 0, "leave": 0}
        for roll, st in students.items():
            if student_section_idx[roll] != s_idx or (st.admission_date and st.admission_date > a.date):
                continue
            status, reason, _ = status_by_day.get((roll, a.date), ("present", None, None))
            counts[status] += 1
            items.append(AttendanceSubmissionItem(student_id=st.id, status=status,
                                                  absence_reason=reason if status == "absent" else None))
        sub = AttendanceSubmission(
            substitute_assignment_id=a.id, substitute_teacher_id=a.substitute_teacher_id,
            substitute_teacher_name=t_sub.full_name, responsible_teacher_id=a.responsible_teacher_id,
            section_id=a.section_id, class_name=SECTIONS[s_idx][0], section_name=SECTIONS[s_idx][2], date=a.date,
            period_id=a.period_id, timetable_id=a.timetable_id, present_count=counts["present"],
            absent_count=counts["absent"], leave_count=counts["leave"], status=planned, items=items,
        )
        db.add(sub)
        db.flush()
        if planned in ("approved", "rejected"):
            sub.decided_at = utcnow() - timedelta(days=(today - a.date).days)
            sub.decided_by_teacher_id = a.responsible_teacher_id
            sub.decided_by_account_id = t_reg.user_account_id
            reason = None if planned == "approved" else "Count does not match the class register – I will re-check and mark it myself."
            sub.rejection_reason = reason
            db.add(AttendanceApproval(submission_id=sub.id, action=planned, acted_by_teacher_id=a.responsible_teacher_id,
                                      acted_by_account_id=t_reg.user_account_id, acted_by_role="teacher", reason=reason,
                                      records_finalized=len(items) if planned == "approved" else 0))
        if planned == "approved":
            for row in rows:
                if row["date"] == a.date and row["timetable_id"] == a.timetable_id:
                    row.update(source="substitute", submission_id=sub.id, marked_by_teacher_id=a.substitute_teacher_id)
    db.execute(insert(Attendance), rows)
    print(f"  {len(rows)} attendance records")

    # ------------------------------------------------------------------ fees
    print("  generating fees …")
    fee_plan = {6: 42000, 7: 44000, 8: 46000}
    structures: dict[str, list[FeeStructure]] = {}
    for cname, cls in classes.items():
        base = fee_plan[cls.grade_level]
        specs = [
            ("academic", "Academic Fee (Tuition)", base, date(y, 6, 15), False),
            ("term", "Term Fee – Term 1", 6500, date(y, 6, 30), False),
            ("term", "Term Fee – Term 2", 6500, date(y, 10, 15), False),
            ("term", "Term Fee – Term 3", 6500, date(y + 1, 1, 15), False),
            ("bus", "Bus Fee (annual)", 14000, date(y, 7, 10), True),
            ("extra_activity", "Extra Activity Fee (sports, music & clubs)", 4500, date(y, 8, 1), False),
            ("other", "Lab & Library Fee", 2500, date(y, 7, 31), False),
            ("other", "Examination Fee", 1800, date(y, 9, 15), False),
        ]
        structures[cname] = []
        for cat, name, amt, due, optional in specs:
            fs = FeeStructure(academic_year_id=ay.id, class_id=cls.id, category=cat, name=name, amount=m(amt),
                              due_date=due, is_optional=optional, description="Predefined by school management")
            db.add(fs)
            structures[cname].append(fs)
    db.flush()

    patterns = ["full", "full", "installments", "full", "partial", "installments", "full", "late", "installments", "partial"]
    pattern_of = {roll: patterns[i % len(patterns)] for i, roll in enumerate(sorted(students))}
    pattern_of.update({"6A01": "installments", "8A03": "partial", "8A05": "partial"})
    receipt_seq = 0
    all_payments: list[tuple] = []  # (date, student, payment, paid_to_date, balance_after)
    for roll, st in students.items():
        cname = SECTIONS[student_section_idx[roll]][0]
        pat = pattern_of[roll]
        events = []  # (date, order, kind, obj)
        opening = m(1500) if roll in ("8A05", "8A09") else m(0)
        charged_on = max(ay_start, st.admission_date or ay_start)
        records: dict[str, StudentFeeRecord] = {}
        for fs in structures[cname]:
            if fs.is_optional and not st.uses_school_bus:
                continue
            rec = StudentFeeRecord(student_id=st.id, academic_year_id=ay.id, fee_structure_id=fs.id,
                                   category=fs.category, description=fs.name, amount=fs.amount,
                                   charged_on=charged_on, due_date=fs.due_date)
            db.add(rec)
            records[fs.name] = rec
        db.flush()
        for rec in records.values():
            events.append((rec.charged_on, 1, "charge", rec))

        def pay(rec_name, amount, when: date, method=None, status="success"):
            if rec_name not in records or when > today or when < charged_on:
                return
            events.append((when, 3, "payment", (records[rec_name], m(amount), method or R.choice(
                ["upi", "upi", "net_banking", "card", "cash", "cheque"]), status)))

        acad = records["Academic Fee (Tuition)"]
        late_fine = None
        if pat == "full":
            pay(acad.description, acad.amount, date(y, 6, R.randint(3, 14)))
            pay("Term Fee – Term 1", 6500, date(y, 6, 25))
            pay("Term Fee – Term 2", 6500, date(y, 10, R.randint(5, 14)))
            pay("Bus Fee (annual)", 14000, date(y, 7, 8))
            pay("Extra Activity Fee (sports, music & clubs)", 4500, date(y, 7, 28))
            pay("Lab & Library Fee", 2500, date(y, 7, 28))
            pay("Examination Fee", 1800, date(y, 9, 10))
        elif pat == "installments":
            half = (acad.amount / 2).quantize(TWO)
            pay(acad.description, half, date(y, 6, 10))
            pay(acad.description, acad.amount - half, date(y, 9, 10))
            pay("Term Fee – Term 1", 6500, date(y, 6, 27))
            pay("Term Fee – Term 2", 6500, date(y, 10, 14))
            pay("Bus Fee (annual)", 7000, date(y, 7, 8))
            pay("Bus Fee (annual)", 7000, date(y, 11, 5))
            pay("Extra Activity Fee (sports, music & clubs)", 4500, date(y, 8, 1))
            pay("Lab & Library Fee", 2500, date(y, 7, 30))
            pay("Examination Fee", 1800, date(y, 9, 12))
        elif pat == "partial":
            first = (acad.amount * D("0.6")).quantize(D("1"))
            pay(acad.description, first, date(y, 6, 12))
            pay("Term Fee – Term 1", 6500, date(y, 7, 18))
            pay("Bus Fee (annual)", 7000, date(y, 7, 15))
            pay("Examination Fee", 1800, date(y, 9, 14))
            if roll == "8A03":
                pay("Lab & Library Fee", 2500, date(y, 8, 20), method="upi", status="failed")
                pay("Lab & Library Fee", 2500, date(y, 8, 21), method="net_banking")
        else:  # late payer → penalty
            late_fine = StudentFeeRecord(student_id=st.id, academic_year_id=ay.id, category="penalty",
                                         description="Late payment fine – Academic Fee", amount=m(500),
                                         charged_on=date(y, 7, 1), due_date=date(y, 7, 15))
            db.add(late_fine)
            db.flush()
            records[late_fine.description] = late_fine
            events.append((late_fine.charged_on, 1, "charge", late_fine))
            pay(acad.description, acad.amount, date(y, 7, 5))
            pay(late_fine.description, 500, date(y, 7, 5))
            pay("Term Fee – Term 1", 6500, date(y, 7, 5))
            pay("Term Fee – Term 2", 6500, date(y, 10, 28))
            pay("Bus Fee (annual)", 14000, date(y, 7, 20))
            pay("Extra Activity Fee (sports, music & clubs)", 4500, date(y, 8, 10))
            pay("Lab & Library Fee", 2500, date(y, 8, 10))
            pay("Examination Fee", 1800, date(y, 9, 20))

        adjustments = []
        if roll == "8A03":
            adjustments.append((date(y, 6, 1), m(-(acad.amount * D("0.10"))), "Sibling concession – 10% of academic fee", acad))
        if roll == "6A03":
            adjustments.append((date(y, 7, 15), m(-5000), "Merit scholarship (previous year topper)", acad))
        for when, amt, reason, rec in adjustments:
            adj = FeeAdjustment(student_id=st.id, academic_year_id=ay.id, student_fee_record_id=rec.id, amount=amt,
                                adjusted_on=when, reason=reason, approved_by="Principal (demo)")
            db.add(adj)
            db.flush()
            events.append((when, 2, "adjustment", adj))

        # ledger
        seq, balance, total_paid = 1, opening, m(0)
        db.add(FeeBalanceHistory(student_id=st.id, academic_year_id=ay.id, sequence=seq, entry_date=charged_on,
                                 entry_type="opening",
                                 description="Opening balance" + (" (arrears from previous year)" if opening else ""),
                                 debit=m(0), credit=m(0), balance_after=balance))
        for when, _, kind, obj in sorted(events, key=lambda e: (e[0], e[1])):
            seq += 1
            if kind == "charge":
                balance += obj.amount
                db.add(FeeBalanceHistory(student_id=st.id, academic_year_id=ay.id, sequence=seq, entry_date=when,
                                         entry_type="charge", description=f"{obj.description} charged",
                                         fee_record_id=obj.id, debit=obj.amount, credit=m(0), balance_after=balance))
            elif kind == "adjustment":
                balance += obj.amount
                db.add(FeeBalanceHistory(student_id=st.id, academic_year_id=ay.id, sequence=seq, entry_date=when,
                                         entry_type="adjustment", description=obj.reason, adjustment_id=obj.id,
                                         debit=obj.amount if obj.amount > 0 else m(0),
                                         credit=-obj.amount if obj.amount < 0 else m(0), balance_after=balance))
            else:
                rec, amount, method, status = obj
                txn = f"TXN{when.strftime('%Y%m%d')}{R.randint(100000, 999999)}"
                payment = FeePayment(student_id=st.id, academic_year_id=ay.id, student_fee_record_id=rec.id,
                                     transaction_ref=txn, payment_date=when, amount=amount, method=method,
                                     status=status, is_demo_record=True,
                                     remarks="Payment failed at bank – retried" if status == "failed" else None)
                db.add(payment)
                db.flush()
                if status != "success":
                    seq -= 1
                    continue
                balance -= amount
                total_paid += amount
                db.add(FeeBalanceHistory(student_id=st.id, academic_year_id=ay.id, sequence=seq, entry_date=when,
                                         entry_type="payment", description=f"Payment received – {rec.description}",
                                         payment_id=payment.id, debit=m(0), credit=amount, balance_after=balance))
                all_payments.append((when, st, payment, total_paid, balance))
    all_payments.sort(key=lambda p: (p[0], p[2].id))
    for when, st, payment, paid_to_date, bal in all_payments:
        receipt_seq += 1
        db.add(FeeReceipt(payment_id=payment.id, receipt_number=f"SVM/{ay.name}/R{receipt_seq:05d}",
                          total_paid_to_date=paid_to_date, balance_after=bal))
    print(f"  {len(all_payments)} payments")

    # ------------------------------------------------------------------ salaries
    print("  generating salaries …")
    months = [date(y, mth, 1) for mth in range(4, today.month + 1)] if today.year == y else \
        [date(y, mth, 1) for mth in range(4, 13)] + [date(y + 1, mth, 1) for mth in range(1, today.month + 1)]
    penalties = {("T1006", 8): ("late_arrival_penalty", "Late arrival on 3 days", 300),
                 ("T1003", 10): ("late_arrival_penalty", "Late arrival on 4 days", 500),
                 ("T1002", 7): ("other_penalty", "Report cards submitted after deadline", 250)}
    lop = {("T1007", 9): 1}
    for code, name, *_rest, basic in TEACHERS:
        t = teachers[code]
        for month_start in months:
            month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            if ay_start <= month_start:
                working = sum(1 for d in daterange(month_start, month_end) if day_type(d) == "working")
            else:
                working = 20 if month_start.month == 4 else 8
            lop_days = lop.get((code, month_start.month), 0)
            b = m(basic)
            da, hra, ta, sa = m(b * D("0.12")), m(b * D("0.20")), m(1600), m(2000)
            gross = b + da + hra + ta + sa
            deductions = [("provident_fund", "Employee PF contribution", m(b * D("0.12")), False),
                          ("professional_tax", "Professional tax", m(200), False)]
            if basic >= 36000:
                deductions.append(("income_tax", "TDS as per declaration", m(1200), False))
            if (code, month_start.month) in penalties:
                kind, desc, amt = penalties[(code, month_start.month)]
                deductions.append((kind, desc, m(amt), True))
            if lop_days:
                deductions.append(("loss_of_pay", f"Loss of pay – {lop_days} day(s)", m((b + da) / working * lop_days), True))
            penalty_total = sum((d[2] for d in deductions if d[3]), m(0))
            other_total = sum((d[2] for d in deductions if not d[3]), m(0))
            total = penalty_total + other_total
            is_current = month_start.year == today.year and month_start.month == today.month
            pay_day = month_end if not is_current else None
            sal = TeacherSalary(teacher_id=t.id, salary_month=month_start, working_days=working,
                                days_present=working - lop_days, basic_salary=b, dearness_allowance=da,
                                house_rent_allowance=hra, transport_allowance=ta, special_allowance=sa,
                                gross_salary=gross, penalty_deductions=penalty_total, other_deductions=other_total,
                                total_deductions=total, net_salary=gross - total,
                                status="processing" if is_current else "paid", payment_date=pay_day)
            db.add(sal)
            db.flush()
            for kind, desc, amt, is_pen in deductions:
                db.add(SalaryDeduction(teacher_salary_id=sal.id, deduction_type=kind, description=desc, amount=amt,
                                       is_penalty=is_pen))
            if not is_current:
                db.add(SalaryPayment(teacher_salary_id=sal.id, payment_date=pay_day, amount=sal.net_salary,
                                     method="bank_transfer", reference_number=f"SAL{month_start:%Y%m}{code}",
                                     status="success"))

    # a sample change-history row so the audit trail is not empty
    db.add(StudentChangeHistory(student_id=students["7A07"].id, action="create",
                                changes={"full_name": {"old": None, "new": students["7A07"].full_name}},
                                reason="Mid-year admission (transfer from another school)",
                                performed_by_teacher_id=teachers["T1003"].id,
                                performed_by_account_id=teachers["T1003"].user_account_id, totp_verified=True))
    db.commit()
    db.close()

    try:
        mdb = mongo.get_mongo_db()
        for coll in (mongo.ACTIVITY_LOGS, mongo.NOTIFICATION_HISTORY, mongo.SYSTEM_EVENTS):
            mdb[coll].delete_many({})
        mongo.ensure_indexes()
        mongo.log_system_event("seed", "Demo data seeded", {"date": today.isoformat(), "academic_year": ay.name})
        print("  MongoDB log collections reset")
    except Exception as exc:  # pragma: no cover
        print(f"  (MongoDB not reachable – skipped log reset: {exc.__class__.__name__})")
    print("Done.")


if __name__ == "__main__":
    engine.dispose()
    run()
