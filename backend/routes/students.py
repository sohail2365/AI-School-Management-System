from datetime import date
import secrets
import json
import re
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
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


# ==================== HELPERS ====================
def _to_title_case(text: str | None) -> str | None:
    """Convert text to Title Case safely."""
    if not text:
        return text
    return " ".join(word.capitalize() for word in str(text).split())


def _serialize_custom_fields(data: dict | None) -> str | None:
    """Convert dict to JSON string."""
    if data is None:
        return None
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return None


def _deserialize_custom_fields(data: str | None) -> dict | None:
    """Convert JSON string to dict."""
    if not data:
        return None
    try:
        return json.loads(data)
    except Exception:
        return None


def _parse_class_fee(school: School, class_name: str) -> float | None:
    """Reads school's class-wise fee structure."""
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
    """Auto-create this month's fee for the student based on class fee structure."""
    amount = _parse_class_fee(school, student.class_name)
    if amount is None:
        return
    _auto_create_fee_for_student_with_amount(db, school, student, amount)


def _auto_create_fee_for_student_with_amount(
    db: Session, school: School, student: Student, amount: float
) -> None:
    """Auto-create this month's fee with a specific amount."""
    if amount <= 0:
        return

    current_month = date.today().strftime("%Y-%m")

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
    """Auto-provision parent portal login for parent_email."""
    if not student.parent_email:
        return None
    if student.parent_user_id:
        return None

    existing_user = (
        db.query(User)
        .filter(User.email == student.parent_email, User.school_id == school.id)
        .first()
    )
    if existing_user:
        student.parent_user_id = existing_user.id
        return None

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
    db.flush()

    student.parent_user_id = user.id
    return temp_password


# ==================== LIST + CLASS SUMMARY ====================
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

    students = query.all()

    # ✅ Sort by class (natural) → roll number (numeric)
    def _sort_key(s):
        cls_parts = re.split(r"(\d+)", s.class_name or "")
        cls_key = tuple(int(p) if p.isdigit() else p.lower() for p in cls_parts if p)
        try:
            roll_key = int(str(s.roll_number).strip())
        except (ValueError, TypeError):
            roll_key = 999999
        return (cls_key, roll_key)

    return sorted(students, key=_sort_key)


@router.get("/classes-summary")
def students_classes_summary(
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """List of classes with student count — for class grid view."""
    rows = (
        db.query(Student.class_name, func.count(Student.id).label("student_count"))
        .filter(Student.school_id == token["school_id"])
        .group_by(Student.class_name)
        .all()
    )

    def _sort_key(name):
        parts = re.split(r"(\d+)", name or "")
        return [int(p) if p.isdigit() else p.lower() for p in parts if p]

    rows = sorted(rows, key=lambda r: _sort_key(r.class_name))
    return [
        {"class_name": r.class_name, "student_count": r.student_count}
        for r in rows
    ]


# ==================== AUTO ROLL NUMBER ====================
@router.get("/next-roll")
def get_next_roll_number(
    class_name: str = Query(..., alias="class"),
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """Auto-generate next roll number for a class (continuous: 1, 2, 3...)."""
    if not class_name:
        raise HTTPException(status_code=422, detail="Class name required")

    students = (
        db.query(Student.roll_number)
        .filter(
            Student.school_id == token["school_id"],
            Student.class_name == class_name,
        )
        .all()
    )

    numeric_rolls = []
    for (rn,) in students:
        try:
            numeric_rolls.append(int(str(rn).strip()))
        except (ValueError, TypeError):
            continue

    next_roll = (max(numeric_rolls) + 1) if numeric_rolls else 1

    return {
        "class_name": class_name,
        "next_roll_number": str(next_roll),
        "existing_count": len(numeric_rolls),
    }


# ==================== GET ONE ====================
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
            # ✅ NEW
            "admission_date": student.admission_date.isoformat() if student.admission_date else None,
            "b_form_number": student.b_form_number,
            "admission_fee": student.admission_fee,
            "monthly_fee_override": student.monthly_fee_override,
            "custom_fields_data": _deserialize_custom_fields(student.custom_fields_data),
            "photo_url": student.photo_url,
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


# ==================== CREATE ====================
@router.post("", response_model=StudentCreateResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()

    # ✅ Title Case all text fields
    for field in ["name", "father_name", "mother_name", "class_name", "address"]:
        if field in data and data[field]:
            data[field] = _to_title_case(data[field])

    # Normalize gender
    if "gender" in data and data["gender"] not in ["male", "female", "other"]:
        data["gender"] = None

    if payload.date_of_birth and payload.date_of_birth > date.today():
        raise HTTPException(status_code=422, detail="DOB cannot be a future date")

    if payload.admission_date and payload.admission_date > date.today():
        raise HTTPException(status_code=422, detail="Admission date cannot be in the future")

    # ✅ B-Form uniqueness
    if data.get("b_form_number"):
        existing_bform = (
            db.query(Student)
            .filter(
                Student.school_id == token["school_id"],
                Student.b_form_number == data["b_form_number"].strip(),
            )
            .first()
        )
        if existing_bform:
            raise HTTPException(
                status_code=409,
                detail="Ye B-Form number already registered hai kisi aur student ke saath",
            )

    # ✅ Roll number uniqueness in class
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

    # ✅ Serialize custom_fields_data
    custom_data = data.pop("custom_fields_data", None)
    serialized = _serialize_custom_fields(custom_data)

    student = Student(
        school_id=token["school_id"],
        custom_fields_data=serialized,
        **data,
    )
    db.add(student)
    db.flush()

    school = db.query(School).filter(School.id == token["school_id"]).first()
    parent_temp_password = None
    if school:
        # Admission fee as separate record
        if student.admission_fee and student.admission_fee > 0:
            admission_fee = Fee(
                school_id=school.id,
                student_id=student.id,
                fee_name="Admission Fee",
                amount=student.admission_fee,
                due_amount=student.admission_fee,
                paid_amount=0.0,
                due_date=date.today(),
                month=date.today().strftime("%Y-%m"),
                status=FeeStatus.pending,
            )
            db.add(admission_fee)

        # Monthly fee
        if student.monthly_fee_override and student.monthly_fee_override > 0:
            _auto_create_fee_for_student_with_amount(db, school, student, student.monthly_fee_override)
        else:
            _auto_create_fee_for_student(db, school, student)

        parent_temp_password = _auto_create_parent_login(db, school, student)

    db.commit()
    db.refresh(student)

    result = StudentCreateResponse.model_validate(student)
    result.custom_fields_data = _deserialize_custom_fields(student.custom_fields_data)
    result.parent_temp_password = parent_temp_password
    return result


# ==================== UPDATE ====================
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

    # ✅ Title Case text fields
    for field in ["name", "father_name", "mother_name", "class_name", "address"]:
        if field in data and data[field]:
            data[field] = _to_title_case(data[field])

    # ✅ Normalize gender
    if "gender" in data and data["gender"] not in ["male", "female", "other"]:
        data["gender"] = None

    if "date_of_birth" in data and data["date_of_birth"] and data["date_of_birth"] > date.today():
        raise HTTPException(status_code=422, detail="DOB cannot be a future date")

    # ✅ B-Form uniqueness (excluding self)
    if "b_form_number" in data and data["b_form_number"]:
        existing_bform = (
            db.query(Student)
            .filter(
                Student.school_id == token["school_id"],
                Student.b_form_number == data["b_form_number"].strip(),
                Student.id != student_id,
            )
            .first()
        )
        if existing_bform:
            raise HTTPException(status_code=409, detail="B-Form already registered")

    # ✅ Roll number uniqueness
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

    # ✅ Handle custom_fields_data
    if "custom_fields_data" in data:
        custom_val = data.pop("custom_fields_data")
        student.custom_fields_data = _serialize_custom_fields(custom_val)

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
    result.custom_fields_data = _deserialize_custom_fields(student.custom_fields_data)
    result.parent_temp_password = parent_temp_password
    return result


# ==================== DELETE ====================
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


# ==================== MESSAGING ====================
@router.get("/messages/threads")
def get_all_message_threads(
    class_name: str | None = Query(default=None),
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
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


# ==================== PARENT LOGIN MANAGEMENT ====================
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