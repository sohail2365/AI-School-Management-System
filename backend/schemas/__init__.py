from .school import (
    SchoolCreate,
    SchoolRegisterRequest,
    SchoolProfileOut,
    SchoolProfileUpdate,
)
from .user import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RefreshResponse,
    ResetPasswordRequest,
)
from .student import StudentCreate, StudentCreateResponse, StudentUpdate, StudentOut
from .grade import GradeCreate, GradeUpdate, GradeOut
from .attendance import AttendanceCreate, AttendanceOut, AttendanceUpdate
from .fee import FeeCreate, FeeUpdate, FeeOut
from .payment import PaymentCreate, PaymentOut
from .announcement import AnnouncementCreate, AnnouncementOut, AnnouncementUpdate
from .settings import (
    BackgroundOverlayUpdate,
    ClassesUpdate,
    FeeSettingsUpdate,
    HolidaysUpdate,
    ParentPortalSettingsResponse,
    ParentPortalSettingsUpdate,
    SchoolSettingsResponse,
    SchoolSettingsUpdate,
)
from .staff import (
    StaffCreate,
    StaffOut,
    StaffUpdate,
    StaffAttendanceCreate,
    StaffAttendanceOut,
    StaffAttendanceUpdate,
    StaffSalaryPaymentCreate,
    StaffSalaryPaymentOut,
)
from .test_record import TestRecordCreate, TestRecordOut, TestRecordUpdate
from .student_document import StudentDocumentOut

__all__ = [
    # school
    "SchoolCreate",
    "SchoolRegisterRequest",
    "SchoolProfileOut",
    "SchoolProfileUpdate",
    # user
    "AuthResponse",
    "ForgotPasswordRequest",
    "LoginRequest",
    "RefreshRequest",
    "RefreshResponse",
    "ResetPasswordRequest",
    # student
    "StudentCreate",
    "StudentCreateResponse",
    "StudentUpdate",
    "StudentOut",
    # grade
    "GradeCreate",
    "GradeUpdate",
    "GradeOut",
    # attendance
    "AttendanceCreate",
    "AttendanceOut",
    "AttendanceUpdate",
    # fee
    "FeeCreate",
    "FeeUpdate",
    "FeeOut",
    # payment
    "PaymentCreate",
    "PaymentOut",
    # announcement
    "AnnouncementCreate",
    "AnnouncementOut",
    "AnnouncementUpdate",
    # settings
    "BackgroundOverlayUpdate",
    "ClassesUpdate",
    "FeeSettingsUpdate",
    "HolidaysUpdate",
    "ParentPortalSettingsResponse",
    "ParentPortalSettingsUpdate",
    "SchoolSettingsResponse",
    "SchoolSettingsUpdate",
    # staff
    "StaffCreate",
    "StaffOut",
    "StaffUpdate",
    "StaffAttendanceCreate",
    "StaffAttendanceOut",
    "StaffAttendanceUpdate",
    "StaffSalaryPaymentCreate",
    "StaffSalaryPaymentOut",
    # test record
    "TestRecordCreate",
    "TestRecordOut",
    "TestRecordUpdate",
    # document
    "StudentDocumentOut",
]