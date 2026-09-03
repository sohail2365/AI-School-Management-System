from datetime import date
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.attendance import Attendance
from backend.models.fee import Fee, FeeStatus
from backend.models.grade import Grade
from backend.models.payment import Payment
from backend.models.school import School
from backend.models.student import Student
from backend.models.user import User, UserRole
from backend.schemas.student import StudentCreate, StudentCreateResponse, StudentOut, StudentUpdate
from backend.utils.jwt_handler import verify_token
from backend.utils.password import hash_password
from backend.utils.rbac import require_roles

router = APIRouter(prefix="/students", tags=["students"])


def _parse_class_fee(school: School, class_name: str) -> float | None:
    """
    Reads the school's class-wise fee structure (stored as lines like
    "Class 1:1500") and returns the fee for the given class, or None if that
    class has no fee configured. Matching is case-insensitive and ignores
    surrounding spaces so "1", "Class 1", "class 1 " all behave sensibly as
    long as they match how the admin wrote it in Settings.
    """
    if not school.fee_structure or not class_name:
        return None
    target = class_name.strip().lower()
    for line in school.fee_structure.split("\n"):
        if ":" not in line:
            continue
        cls, amount = line.split(":", 1)
        if cls.strip().lower() == target:
            try:
                value = float(amount.strip())
                return value if value > 0 else None
            except ValueError:
                return None
    return None


def _auto_create_fee_for_student(db: Session, school: School, student: Student) -> None:
    """
    When a student is added, if their class has a fee configured in the
    school's fee structure, create this month's fee row automatically so the
    admin doesn't have to add it by hand. Silent no-op when no fee is set for
    that class — never blocks student creation.
    """
    amount = _parse_class_fee(school, student.class_name)
    if amount is None:
        return

    current_month = date.today().strftime("%Y-%m")

    # Don't double-create if a fee for this student + month already exists.
    already = (
        db.query(Fee)
        .filter(
            Fee.school_id == school.id,
            Fee.student_id == student.id,
            Fee.month == current_month,
        )
        .first()
    )
    if already:
        return

    due_day = school.fee_due_day or 10
    try:
        due = date(date.today().year, date.today().month, min(due_day, 28))
    except ValueError:
        due = None

    fee = Fee(
        school_id=school.id,
        student_id=student.id,
        fee_name=f"Monthly Fee - {current_month}",
        amount=amount,
        due_amount=amount,
        paid_amount=0.0,
        due_date=due,
        month=current_month,
        status=FeeStatus.pending,
    )
    db.add(fee)


def _auto_create_parent_login(db: Session, school: School, student: Student) -> str | None:
    """
    When a student is created/updated with a parent_email set, auto-provision
    a Parent Portal login for that email (if one doesn't already exist) and
    link it to this student via Student.parent_user_id.

    Returns the ONE-TIME temporary password if a new login was just created,
    so the caller can hand it back to the admin — same pattern as teacher
    login creation. Returns None if no login was created (already existed,
    or no parent_email set) — never blocks student creation on failure.
    """
    if not student.parent_email:
        return None
    if student.parent_user_id:
        return None  # already linked, don't recreate

    # A parent with multiple kids at the same school should get ONE login,
    # not one per child — reuse an existing account with this email if found.
    existing_user = (
        db.query(User)
        .filter(User.email == student.parent_email, User.school_id == school.id)
        .first()
    )
    if existing_user:
        student.parent_user_id = existing_user.id
        return None  # login already existed, no new password to report

    temp_password = secrets.token_urlsafe(9)
    user = User(
        school_id=school.id,
        username=student.parent_email.split("@")[0],
        email=student.parent_email,
        password_hash=hash_password(temp_password),
        full_name=f"Parent of {student.name}",
        role=UserRole.parent,
        is_active=True,
    )
    db.add(user)
    db.flush()  # get user.id before linking

    student.parent_user_id = user.id
    return temp_password


@router.get("", response_model=list[StudentOut])
def list_students(
    class_name: str | None = Query(default=None, alias="class"),
    search: str | None = None,
    token: dict = Depends(require_roles(["admin", "teacher", "parent"])),
    db: Session = Depends(get_db),
):
    query = db.query(Student).filter(Student.school_id == token["school_id"])

    if class_name:
        query = query.filter(Student.class_name == class_name)
    if search:
        query = query.filter(Student.name.ilike(f"%{search}%"))

    return query.order_by(Student.id.desc()).all()


@router.get("/{student_id}", response_model=StudentOut)
def get_student(
    student_id: int,
    token: dict = Depends(require_roles(["admin", "teacher", "parent", "student"])),
    db: Session = Depends(get_db),
):
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.school_id == token["school_id"])
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.get("/{student_id}/profile")
def get_student_profile(
    student_id: int,
    token: dict = Depends(require_roles(["admin", "teacher", "parent", "student"])),
    db: Session = Depends(get_db),
):
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.school_id == token["school_id"])
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    attendance_records = (
        db.query(Attendance)
        .filter(Attendance.school_id == token["school_id"], Attendance.student_id == student_id)
        .order_by(Attendance.date.desc())
        .all()
    )
    total_marked = len(attendance_records)
    present_count = sum(1 for a in attendance_records if a.is_present)
    attendance_rate = round((present_count / total_marked) * 100, 2) if total_marked else 0.0

    grades = (
        db.query(Grade)
        .filter(Grade.school_id == token["school_id"], Grade.student_id == student_id)
        .order_by(Grade.exam_date.desc().nullslast(), Grade.id.desc())
        .all()
    )
    avg_percentage = round(sum(g.percentage for g in grades) / len(grades), 2) if grades else 0.0

    fees = (
        db.query(Fee)
        .filter(Fee.school_id == token["school_id"], Fee.student_id == student_id)
        .order_by(Fee.id.desc())
        .all()
    )
    total_fee_amount = round(sum(f.amount for f in fees), 2)
    total_paid = round(sum(f.paid_amount for f in fees), 2)
    total_due = round(total_fee_amount - total_paid, 2)

    fee_ids = [f.id for f in fees]
    payments = (
        db.query(Payment)
        .filter(Payment.school_id == token["school_id"], Payment.fee_id.in_(fee_ids))
        .order_by(Payment.payment_date.desc())
        .all()
        if fee_ids
        else []
    )

    return {
        "student": {
            "id": student.id,
            "name": student.name,
            "father_name": student.father_name,
            "mother_name": student.mother_name,
            "class_name": student.class_name,
            "roll_number": student.roll_number,
            "email": student.email,
            "phone": student.phone,
            "gender": student.gender,
            "date_of_birth": student.date_of_birth.isoformat() if student.date_of_birth else None,
            "address": student.address,
        },
        "attendance": {
            "total_marked": total_marked,
            "present": present_count,
            "absent": total_marked - present_count,
            "attendance_rate": attendance_rate,
            "recent_records": [
                {"date": a.date.isoformat(), "is_present": a.is_present, "remarks": a.remarks}
                for a in attendance_records[:15]
            ],
        },
        "grades": {
            "average_percentage": avg_percentage,
            "records": [
                {
                    "id": g.id,
                    "subject": g.subject,
                    "marks_obtained": g.marks_obtained,
                    "total_marks": g.total_marks,
                    "percentage": g.percentage,
                    "grade": g.grade,
                    "exam_date": g.exam_date.isoformat() if g.exam_date else None,
                }
                for g in grades
            ],
        },
        "fees": {
            "total_amount": total_fee_amount,
            "total_paid": total_paid,
            "total_due": total_due,
            "records": [
                {
                    "id": f.id,
                    "fee_name": f.fee_name,
                    "amount": f.amount,
                    "paid_amount": f.paid_amount,
                    "due_amount": f.due_amount,
                    "status": f.status,
                    "due_date": f.due_date.isoformat() if f.due_date else None,
                    "month": f.month,
                }
                for f in fees
            ],
            "payments": [
                {
                    "id": p.id,
                    "fee_id": p.fee_id,
                    "amount_paid": p.amount_paid,
                    "payment_date": p.payment_date.isoformat(),
                    "payment_method": p.payment_method,
                    "receipt_number": p.receipt_number,
                }
                for p in payments
            ],
        },
    }


@router.post("", response_model=StudentCreateResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()

    # ✅ FIX: normalize gender safely
    if "gender" in data and data["gender"] not in ["male", "female", "other"]:
        data["gender"] = None
    if payload.date_of_birth and payload.date_of_birth > date.today():
        raise HTTPException(status_code=422, detail="DOB cannot be a future date")

    exists = (
        db.query(Student)
        .filter(
            Student.school_id == token["school_id"],
            Student.class_name == payload.class_name,
            Student.roll_number == payload.roll_number,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="Roll number already exists in this class")

    student = Student(
        school_id=token["school_id"],
        **data,
    )
    db.add(student)
    db.flush()  # get student.id before creating the linked fee

    # Auto-assign this month's fee based on the class fee structure (if set).
    school = db.query(School).filter(School.id == token["school_id"]).first()
    parent_temp_password = None
    if school:
        _auto_create_fee_for_student(db, school, student)
        parent_temp_password = _auto_create_parent_login(db, school, student)

    db.commit()
    db.refresh(student)

    result = StudentCreateResponse.model_validate(student)
    result.parent_temp_password = parent_temp_password
    return result


@router.put("/{student_id}", response_model=StudentCreateResponse)
def update_student(
    student_id: int,
    payload: StudentUpdate,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.school_id == token["school_id"])
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    data = payload.model_dump(exclude_unset=True)

    if "date_of_birth" in data and data["date_of_birth"] and data["date_of_birth"] > date.today():
        raise HTTPException(status_code=422, detail="DOB cannot be a future date")

    if "roll_number" in data or "class_name" in data:
        check_class_name = data.get("class_name", student.class_name)
        check_roll_number = data.get("roll_number", student.roll_number)
        duplicate = (
            db.query(Student)
            .filter(
                Student.school_id == token["school_id"],
                Student.class_name == check_class_name,
                Student.roll_number == check_roll_number,
                Student.id != student_id,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Roll number already exists in this class")

    for key, value in data.items():
        setattr(student, key, value)

    parent_temp_password = None
    if "parent_email" in data and data["parent_email"]:
        school = db.query(School).filter(School.id == token["school_id"]).first()
        if school:
            parent_temp_password = _auto_create_parent_login(db, school, student)

    db.commit()
    db.refresh(student)

    result = StudentCreateResponse.model_validate(student)
    result.parent_temp_password = parent_temp_password
    return result


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: int,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.school_id == token["school_id"])
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    db.delete(student)
    db.commit()
    return None


@router.get("/{student_id}/report")
def student_report(
    student_id: int,
    token: dict = Depends(require_roles(["admin", "teacher", "parent", "student"])),
    db: Session = Depends(get_db),
):
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.school_id == token["school_id"])
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return {
        "student_id": student.id,
        "name": student.name,
        "class_name": student.class_name,
        "message": "Detailed report endpoint ready for grades/attendance aggregation",
    }


# ==================== ADMIN/TEACHER SIDE OF PARENT MESSAGING ====================

@router.get("/messages/threads")
def get_all_message_threads(
    class_name: str | None = Query(default=None),
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """One row per student with a message, newest message first — powers the admin's inbox list."""
    from backend.models.parent_message import ParentMessage

    query = db.query(Student).filter(Student.school_id == token["school_id"])
    if class_name:
        query = query.filter(Student.class_name == class_name)

    threads = []
    for s in query.all():
        last = (
            db.query(ParentMessage)
            .filter(ParentMessage.school_id == token["school_id"], ParentMessage.student_id == s.id)
            .order_by(ParentMessage.created_at.desc())
            .first()
        )
        if last:
            threads.append({
                "student_id": s.id,
                "student_name": s.name,
                "class_name": s.class_name,
                "last_message": last.message,
                "last_sender_role": last.sender_role,
                "last_at": last.created_at.isoformat(),
            })
    threads.sort(key=lambda t: t["last_at"], reverse=True)
    return threads


@router.get("/{student_id}/messages")
def get_student_messages(
    student_id: int,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    from backend.models.parent_message import ParentMessage

    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.school_id == token["school_id"])
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    messages = (
        db.query(ParentMessage)
        .filter(ParentMessage.school_id == token["school_id"], ParentMessage.student_id == student_id)
        .order_by(ParentMessage.created_at.asc())
        .all()
    )
    return [
        {
            "id": m.id,
            "sender_role": m.sender_role,
            "message": m.message,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


@router.post("/{student_id}/messages", status_code=status.HTTP_201_CREATED)
def send_student_message(
    student_id: int,
    message: str,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    from backend.models.parent_message import ParentMessage

    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.school_id == token["school_id"])
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if not message or not message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    msg = ParentMessage(
        school_id=token["school_id"],
        student_id=student_id,
        sender_user_id=token["user_id"],
        sender_role="staff",
        message=message.strip()[:2000],
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "created_at": msg.created_at.isoformat()}


# ==================== ADMIN: PARENT LOGIN MANAGEMENT ====================
# Passwords are hashed, never stored in plaintext — so there is no "view the
# current password" action. Admin can RESET (issue a new one-time temp
# password, same pattern as teacher logins) or REMOVE the login entirely.

@router.post("/{student_id}/reset-parent-password")
def reset_parent_password(
    student_id: int,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.school_id == token["school_id"])
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if not student.parent_user_id:
        raise HTTPException(status_code=422, detail="No parent login exists for this student yet.")

    user = db.query(User).filter(User.id == student.parent_user_id, User.school_id == token["school_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Linked parent login not found")

    temp_password = secrets.token_urlsafe(9)
    user.password_hash = hash_password(temp_password)
    user.is_active = True
    db.commit()

    return {
        "message": f"Password reset for parent login ({user.email}).",
        "email": user.email,
        "temporary_password": temp_password,
    }


@router.delete("/{student_id}/parent-login", status_code=status.HTTP_204_NO_CONTENT)
def remove_parent_login(
    student_id: int,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Deactivates and unlinks the parent login for this student. Does not delete the student's own data."""
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.school_id == token["school_id"])
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if not student.parent_user_id:
        raise HTTPException(status_code=422, detail="No parent login exists for this student.")

    user = db.query(User).filter(User.id == student.parent_user_id, User.school_id == token["school_id"]).first()
    if user:
        user.is_active = False
    student.parent_user_id = None
    db.commit()
    return None
