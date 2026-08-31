from datetime import date as dt_date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.attendance import Attendance
from backend.models.grade import Grade
from backend.models.staff import Staff
from backend.models.student import Student
from backend.models.test_record import TestRecord, TestTermType
from backend.schemas.attendance import AttendanceOut
from backend.schemas.grade import GradeOut
from backend.schemas.student import StudentOut
from backend.schemas.test_record import TestRecordOut
from backend.utils.rbac import require_roles
from backend.utils.storage import upload_student_file

router = APIRouter(prefix="/teacher", tags=["teacher-portal"])


def _current_teacher(token: dict, db: Session) -> Staff:
    """
    Resolves the Staff record for whoever is logged in, and confirms they
    actually have a class assigned. Every route below depends on this — it
    is what keeps a teacher's access limited to their own class, since the
    JWT alone only proves role="teacher", not WHICH class.
    """
    staff = (
        db.query(Staff)
        .filter(Staff.user_id == token["user_id"], Staff.school_id == token["school_id"])
        .first()
    )
    if not staff:
        raise HTTPException(
            status_code=403,
            detail="No staff profile is linked to this login. Contact your school admin.",
        )
    if not staff.class_assigned:
        raise HTTPException(
            status_code=403,
            detail="No class is assigned to you yet. Contact your school admin.",
        )
    return staff


def _class_student_ids(db: Session, school_id: int, class_name: str) -> list[int]:
    return [
        s.id
        for s in db.query(Student.id).filter(
            Student.school_id == school_id, Student.class_name == class_name
        )
    ]


@router.get("/me")
def get_my_class(
    token: dict = Depends(require_roles(["teacher"])),
    db: Session = Depends(get_db),
):
    staff = _current_teacher(token, db)
    return {
        "staff_id": staff.id,
        "name": staff.name,
        "subject": staff.subject,
        "class_assigned": staff.class_assigned,
    }


@router.get("/students", response_model=list[StudentOut])
def get_my_students(
    token: dict = Depends(require_roles(["teacher"])),
    db: Session = Depends(get_db),
):
    staff = _current_teacher(token, db)
    return (
        db.query(Student)
        .filter(Student.school_id == token["school_id"], Student.class_name == staff.class_assigned)
        .order_by(Student.roll_number)
        .all()
    )


def _assert_student_in_my_class(db: Session, token: dict, staff: Staff, student_id: int) -> Student:
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.school_id == token["school_id"])
        .first()
    )
    if not student or student.class_name != staff.class_assigned:
        raise HTTPException(
            status_code=403,
            detail="You can only manage students in your own assigned class.",
        )
    return student


# ==================== ATTENDANCE (own class only) ====================

@router.get("/attendance", response_model=list[AttendanceOut])
def get_my_class_attendance(
    date: dt_date | None = None,
    token: dict = Depends(require_roles(["teacher"])),
    db: Session = Depends(get_db),
):
    staff = _current_teacher(token, db)
    student_ids = _class_student_ids(db, token["school_id"], staff.class_assigned)

    query = db.query(Attendance).filter(
        Attendance.school_id == token["school_id"], Attendance.student_id.in_(student_ids)
    )
    if date:
        query = query.filter(Attendance.date == date)
    return query.order_by(Attendance.date.desc()).all()


@router.post("/attendance", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def mark_my_class_attendance(
    student_id: int = Form(...),
    date: dt_date = Form(...),
    is_present: bool = Form(...),
    remarks: str | None = Form(default=None),
    token: dict = Depends(require_roles(["teacher"])),
    db: Session = Depends(get_db),
):
    staff = _current_teacher(token, db)
    _assert_student_in_my_class(db, token, staff, student_id)

    if date > dt_date.today():
        raise HTTPException(status_code=422, detail="Attendance can only be marked for current or past dates")

    existing = (
        db.query(Attendance)
        .filter(
            Attendance.school_id == token["school_id"],
            Attendance.student_id == student_id,
            Attendance.date == date,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Attendance already marked for this date")

    record = Attendance(
        school_id=token["school_id"],
        student_id=student_id,
        date=date,
        is_present=is_present,
        remarks=remarks,
        marked_by_user_id=token["user_id"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ==================== GRADES (own class only) ====================

@router.get("/grades", response_model=list[GradeOut])
def get_my_class_grades(
    token: dict = Depends(require_roles(["teacher"])),
    db: Session = Depends(get_db),
):
    staff = _current_teacher(token, db)
    student_ids = _class_student_ids(db, token["school_id"], staff.class_assigned)
    return (
        db.query(Grade)
        .filter(Grade.school_id == token["school_id"], Grade.student_id.in_(student_ids))
        .order_by(Grade.created_at.desc())
        .all()
    )


@router.post("/grades", response_model=GradeOut, status_code=status.HTTP_201_CREATED)
def add_my_class_grade(
    student_id: int = Form(...),
    subject: str = Form(...),
    marks_obtained: float = Form(...),
    total_marks: float = Form(default=100),
    exam_date: dt_date | None = Form(default=None),
    token: dict = Depends(require_roles(["teacher"])),
    db: Session = Depends(get_db),
):
    staff = _current_teacher(token, db)
    _assert_student_in_my_class(db, token, staff, student_id)

    percentage = round((marks_obtained / total_marks) * 100, 2) if total_marks > 0 else 0.0
    record = Grade(
        school_id=token["school_id"],
        student_id=student_id,
        subject=subject,
        marks_obtained=marks_obtained,
        total_marks=total_marks,
        percentage=percentage,
        teacher_id=token["user_id"],
        exam_date=exam_date,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ==================== TEST RECORDS with photo (own class only) ====================

@router.post("/test-records", response_model=TestRecordOut, status_code=status.HTTP_201_CREATED)
def add_my_class_test_record(
    student_id: int = Form(...),
    term_type: str = Form(...),
    period: str = Form(...),
    subject: str = Form(...),
    marks_obtained: float = Form(...),
    total_marks: float = Form(default=100),
    remarks: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    token: dict = Depends(require_roles(["teacher"])),
    db: Session = Depends(get_db),
):
    staff = _current_teacher(token, db)
    _assert_student_in_my_class(db, token, staff, student_id)

    try:
        parsed_term = TestTermType(term_type.strip().lower())
    except ValueError:
        raise HTTPException(status_code=422, detail="term_type must be 'monthly' or 'annual'")

    image_path = None
    if image is not None:
        image_path = upload_student_file(
            image, token["school_id"], student_id, subfolder=f"test_records/{parsed_term.value}"
        )

    percentage = round((marks_obtained / total_marks) * 100, 2) if total_marks > 0 else 0.0
    record = TestRecord(
        school_id=token["school_id"],
        student_id=student_id,
        term_type=parsed_term,
        period=period.strip(),
        subject=subject.strip(),
        marks_obtained=marks_obtained,
        total_marks=total_marks,
        percentage=percentage,
        remarks=remarks,
        image_url=image_path,
        recorded_by_user_id=token["user_id"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/test-records", response_model=list[TestRecordOut])
def get_my_class_test_records(
    token: dict = Depends(require_roles(["teacher"])),
    db: Session = Depends(get_db),
):
    staff = _current_teacher(token, db)
    student_ids = _class_student_ids(db, token["school_id"], staff.class_assigned)
    return (
        db.query(TestRecord)
        .filter(TestRecord.school_id == token["school_id"], TestRecord.student_id.in_(student_ids))
        .order_by(TestRecord.created_at.desc())
        .all()
    )
