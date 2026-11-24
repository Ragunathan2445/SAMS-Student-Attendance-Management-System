"""Import every model so SQLAlchemy metadata (and Alembic) sees all tables."""
from app.models.attendance import (  # noqa: F401
    Attendance,
    AttendanceApproval,
    AttendanceCorrection,
    AttendanceSubmission,
    AttendanceSubmissionItem,
    SubstituteAssignment,
)
from app.models.audit import AuditLog, StudentChangeHistory  # noqa: F401
from app.models.auth import (  # noqa: F401
    ParentOTP,
    Permission,
    Role,
    RolePermission,
    TeacherTOTP,
    UserAccount,
    UserSession,
)
from app.models.fees import (  # noqa: F401
    FeeAdjustment,
    FeeBalanceHistory,
    FeePayment,
    FeeReceipt,
    FeeStructure,
    StudentFeeRecord,
)
from app.models.leave import LeaveApproval, LeaveRequest  # noqa: F401
from app.models.people import (  # noqa: F401
    Parent,
    ParentStudent,
    Student,
    StudentAcademicRecord,
    StudentDocument,
    Teacher,
    TeacherAssignment,
    TeacherClassAssignment,
    TeacherSubjectAssignment,
)
from app.models.salary import SalaryDeduction, SalaryPayment, TeacherSalary  # noqa: F401
from app.models.school import (  # noqa: F401
    AcademicYear,
    Period,
    School,
    SchoolCalendar,
    SchoolClass,
    Section,
    Subject,
    Timetable,
)
