"""Role and permission catalogue (seeded into the roles/permissions tables)."""

PERMISSIONS: dict[str, str] = {
    # parent
    "parent.students.view": "View linked students' profiles",
    "parent.attendance.view": "View linked students' attendance",
    "parent.leave.manage": "Submit and track leave requests for linked students",
    "parent.fees.view": "View fee details, payments and receipts of linked students",
    # teacher
    "teacher.profile.view": "View own teacher profile",
    "attendance.mark": "Mark official attendance for own timetable slots",
    "attendance.correct": "Correct official attendance for own slots with a reason",
    "attendance.reports.view": "View attendance analytics for authorised sections",
    "attendance.substitute.submit": "Submit temporary attendance for assigned substitute slots",
    "attendance.substitute.approve": "Approve/reject temporary attendance for own responsibilities",
    "leave.approve": "Approve or reject leave requests for class-teacher sections",
    "students.manage": "Add, update and deactivate students in class-teacher sections (TOTP required)",
    "students.directory.view": "View emergency contact details of students in authorised sections",
    "salary.view.own": "View own salary details and slips",
    # future management portal
    "attendance.substitute.approve_any": "Approve temporary attendance when the responsible teacher is unavailable",
    "fees.manage": "Manage fee structures, payments and adjustments",
    "salary.manage": "Manage salary structures and payments",
    "school.configure": "Configure academic years, holidays, classes and assignments",
}

ROLES: dict[str, dict] = {
    "parent": {
        "name": "Parent / Guardian",
        "description": "Parent portal user authenticated via OTP",
        "permissions": [p for p in PERMISSIONS if p.startswith("parent.")],
    },
    "teacher": {
        "name": "Teacher",
        "description": "Teacher portal user authenticated via password + TOTP",
        "permissions": [
            "teacher.profile.view",
            "attendance.mark",
            "attendance.correct",
            "attendance.reports.view",
            "attendance.substitute.submit",
            "attendance.substitute.approve",
            "leave.approve",
            "students.manage",
            "students.directory.view",
            "salary.view.own",
        ],
    },
    "school_admin": {
        "name": "School Administrator",
        "description": "Reserved for the future School Management Portal (no UI in this version)",
        "permissions": [
            "attendance.substitute.approve_any",
            "fees.manage",
            "salary.manage",
            "school.configure",
            "attendance.reports.view",
            "leave.approve",
        ],
    },
}
