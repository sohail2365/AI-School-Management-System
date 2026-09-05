import secrets
from datetime import date as dt_date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.staff import Staff, StaffAttendance, StaffRole, StaffSalaryPayment, StaffStatus
from backend.models.user import User, UserRole
from backend.schemas.staff import (
    StaffAttendanceCreate,
    StaffAttendanceOut,
    StaffAttendanceUpdate,
    StaffCreate,
    StaffOut,
    StaffSalaryPaymentCreate,
    StaffSalaryPaymentOut,
    StaffUpdate,
)
from backend.utils.password import hash_password
from backend.utils.rbac import require_roles

router = APIRouter(prefix="/staff", tags=["staff"])


def _parse_staff_role(value: str) -> StaffRole:
    try:
        return StaffRole(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid role. Use admin, teacher or staff")


# ==================== STAFF CRUD ====================

@router.get("", response_model=list[StaffOut])
def list_staff(
    designation: str | None = None,
    role: str | None = None,
    class_assigned: str | None = None,
    search: str | None = None,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    query = db.query(Staff).filter(Staff.school_id == token["school_id"])
    if designation:
        query = query.filter(Staff.designation == designation)
    if role:
        query = query.filter(Staff.role == _parse_staff_role(role))
    if class_assigned:
        query = query.filter(Staff.class_assigned == class_assigned)
    if search:
        query = query.filter(Staff.name.ilike(f"%{search}%"))
    results = query.order_by(Staff.id.desc()).all()

    # Attach login_active (from the linked User row) without touching the
    # Staff model itself — plain instance attribute, never committed.
    user_ids = [s.user_id for s in results if s.user_id]
    if user_ids:
        active_map = {
            u.id: u.is_active
            for u in db.query(User).filter(User.id.in_(user_ids))
        }
        for s in results:
            s.login_active = active_map.get(s.user_id) if s.user_id else None

    return results


@router.get("/{staff_id}", response_model=StaffOut)
def get_staff(
    staff_id: int,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    staff = db.query(Staff).filter(Staff.id == staff_id, Staff.school_id == token["school_id"]).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return staff


@router.post("", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
def create_staff(
    payload: StaffCreate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    staff = Staff(
        school_id=token["school_id"],
        name=payload.name,
        designation=payload.designation,
        role=_parse_staff_role(payload.role) if payload.role else StaffRole.teacher,
        email=payload.email,
        phone=payload.phone,
        subject=payload.subject,
        class_assigned=payload.class_assigned,
        salary=payload.salary,
        joining_date=payload.joining_date,
        address=payload.address,
        status=StaffStatus.active,
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.put("/{staff_id}", response_model=StaffOut)
def update_staff(
    staff_id: int,
    payload: StaffUpdate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    staff = db.query(Staff).filter(Staff.id == staff_id, Staff.school_id == token["school_id"]).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"]:
        try:
            data["status"] = StaffStatus(data["status"])
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid status. Use active or inactive")
    if "role" in data and data["role"]:
        data["role"] = _parse_staff_role(data["role"])

    for key, value in data.items():
        setattr(staff, key, value)

    db.commit()
    db.refresh(staff)
    return staff


@router.delete("/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_staff(
    staff_id: int,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    staff = db.query(Staff).filter(Staff.id == staff_id, Staff.school_id == token["school_id"]).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    db.delete(staff)
    db.commit()
    return None


# ==================== TEACHER PORTAL LOGIN ====================

@router.post("/{staff_id}/create-login", status_code=status.HTTP_201_CREATED)
def create_teacher_login(
    staff_id: int,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """
    Creates (or resets) portal login access for a staff member, so they can
    sign in to the Teacher Portal. Requires the staff record to have an
    email set. Returns a one-time temporary password — the admin must share
    this with the teacher; it is NOT stored anywhere retrievable afterwards.
    """
    staff = db.query(Staff).filter(Staff.id == staff_id, Staff.school_id == token["school_id"]).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    if not staff.email:
        raise HTTPException(
            status_code=422,
            detail="This staff member has no email on file. Add one before creating a login.",
        )

    temp_password = secrets.token_urlsafe(9)  # readable-ish, ~12 chars

    if staff.user_id:
        # Login already exists — reset the password instead of creating a duplicate user.
        user = db.query(User).filter(User.id == staff.user_id).first()
        if not user:
            staff.user_id = None  # orphaned link, fall through to create a fresh one
        else:
            user.password_hash = hash_password(temp_password)
            user.is_active = True
            db.commit()
            return {
                "message": "Password reset for existing teacher login.",
                "email": user.email,
                "temporary_password": temp_password,
            }

    existing_user = db.query(User).filter(User.email == staff.email).first()
    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="A login with this email already exists for a different account.",
        )

    user_role = UserRole.teacher if staff.role == StaffRole.teacher else UserRole.staff
    user = User(
        school_id=token["school_id"],
        username=staff.email.split("@")[0],
        email=staff.email,
        password_hash=hash_password(temp_password),
        full_name=staff.name,
        role=user_role,
        is_active=True,
    )
    db.add(user)
    db.flush()

    staff.user_id = user.id
    db.commit()

    return {
        "message": "Teacher portal login created.",
        "email": user.email,
        "temporary_password": temp_password,
    }


# ==================== STAFF ATTENDANCE ====================

@router.get("/attendance/list", response_model=list[StaffAttendanceOut])
def list_staff_attendance(
    date: dt_date | None = None,
    staff_id: int | None = None,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    query = db.query(StaffAttendance).filter(StaffAttendance.school_id == token["school_id"])
    if date:
        query = query.filter(StaffAttendance.date == date)
    if staff_id:
        query = query.filter(StaffAttendance.staff_id == staff_id)
    return query.order_by(StaffAttendance.date.desc(), StaffAttendance.id.desc()).all()


@router.post("/attendance", response_model=StaffAttendanceOut, status_code=status.HTTP_201_CREATED)
def mark_staff_attendance(
    payload: StaffAttendanceCreate,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    if payload.date > dt_date.today():
        raise HTTPException(status_code=422, detail="Attendance can only be marked for current or past dates")

    staff = (
        db.query(Staff)
        .filter(Staff.id == payload.staff_id, Staff.school_id == token["school_id"])
        .first()
    )
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    existing = (
        db.query(StaffAttendance)
        .filter(
            StaffAttendance.school_id == token["school_id"],
            StaffAttendance.staff_id == payload.staff_id,
            StaffAttendance.date == payload.date,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Attendance already marked for this date")

    record = StaffAttendance(
        school_id=token["school_id"],
        staff_id=payload.staff_id,
        date=payload.date,
        is_present=payload.is_present,
        remarks=payload.remarks,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.put("/attendance/{attendance_id}", response_model=StaffAttendanceOut)
def update_staff_attendance(
    attendance_id: int,
    payload: StaffAttendanceUpdate,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    record = (
        db.query(StaffAttendance)
        .filter(StaffAttendance.id == attendance_id, StaffAttendance.school_id == token["school_id"])
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(record, key, value)

    db.commit()
    db.refresh(record)
    return record


@router.delete("/attendance/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_staff_attendance(
    attendance_id: int,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    record = (
        db.query(StaffAttendance)
        .filter(StaffAttendance.id == attendance_id, StaffAttendance.school_id == token["school_id"])
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    db.delete(record)
    db.commit()
    return None


# ==================== STAFF SALARY ====================

@router.get("/salary/list", response_model=list[StaffSalaryPaymentOut])
def list_salary_payments(
    staff_id: int | None = None,
    month: str | None = None,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    query = db.query(StaffSalaryPayment).filter(StaffSalaryPayment.school_id == token["school_id"])
    if staff_id:
        query = query.filter(StaffSalaryPayment.staff_id == staff_id)
    if month:
        query = query.filter(StaffSalaryPayment.month == month)
    return query.order_by(StaffSalaryPayment.id.desc()).all()


# ✅ NEW: Server-computed paid/remaining/status per staff for a given month.
# Sums ALL payments for that staff+month (supports partial payments) and
# subtracts from staff.salary to get the true remaining amount.
@router.get("/salary/summary")
def salary_summary(
    month: str,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    staff_members = db.query(Staff).filter(Staff.school_id == token["school_id"]).all()
    payments = (
        db.query(StaffSalaryPayment)
        .filter(StaffSalaryPayment.school_id == token["school_id"], StaffSalaryPayment.month == month)
        .all()
    )

    paid_by_staff: dict[int, float] = {}
    last_payment_date_by_staff: dict[int, str] = {}
    for p in payments:
        paid_by_staff[p.staff_id] = round(paid_by_staff.get(p.staff_id, 0.0) + p.amount_paid, 2)
        existing_date = last_payment_date_by_staff.get(p.staff_id)
        if not existing_date or p.payment_date.isoformat() > existing_date:
            last_payment_date_by_staff[p.staff_id] = p.payment_date.isoformat()

    summary = []
    for s in staff_members:
        total_paid = paid_by_staff.get(s.id, 0.0)
        remaining = round(s.salary - total_paid, 2)
        if remaining <= 0:
            salary_status = "paid"
            remaining = 0.0
        elif total_paid > 0:
            salary_status = "partial"
        else:
            salary_status = "pending"

        summary.append({
            "staff_id": s.id,
            "name": s.name,
            "designation": s.designation,
            "salary": s.salary,
            "total_paid": total_paid,
            "remaining": remaining,
            "status": salary_status,
            "last_payment_date": last_payment_date_by_staff.get(s.id),
        })

    return summary


@router.post("/salary/pay", response_model=StaffSalaryPaymentOut, status_code=status.HTTP_201_CREATED)
def pay_salary(
    payload: StaffSalaryPaymentCreate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    staff = (
        db.query(Staff)
        .filter(Staff.id == payload.staff_id, Staff.school_id == token["school_id"])
        .first()
    )
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    # ✅ FIX: Sum existing payments for this staff+month instead of blocking
    # after the first one — this is what enables partial payments + a
    # correctly shrinking "remaining" amount.
    already_paid = (
        db.query(StaffSalaryPayment)
        .filter(
            StaffSalaryPayment.school_id == token["school_id"],
            StaffSalaryPayment.staff_id == payload.staff_id,
            StaffSalaryPayment.month == payload.month,
        )
        .all()
    )
    total_already_paid = round(sum(p.amount_paid for p in already_paid), 2)
    remaining = round(staff.salary - total_already_paid, 2)

    if remaining <= 0:
        raise HTTPException(status_code=409, detail="Salary already fully paid for this month")

    if payload.amount_paid > remaining:
        raise HTTPException(
            status_code=422,
            detail=f"Payment cannot exceed remaining amount (Rs. {remaining})"
        )

    payment = StaffSalaryPayment(
        school_id=token["school_id"],
        staff_id=payload.staff_id,
        month=payload.month,
        amount_paid=payload.amount_paid,
        payment_date=payload.payment_date or dt_date.today(),
        payment_method=payload.payment_method,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@router.delete("/salary/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_salary_payment(
    payment_id: int,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    payment = (
        db.query(StaffSalaryPayment)
        .filter(StaffSalaryPayment.id == payment_id, StaffSalaryPayment.school_id == token["school_id"])
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Salary payment record not found")

    db.delete(payment)
    db.commit()
    return None


# ==================== BLOCK / UNBLOCK TEACHER LOGIN ====================
# Purely additive: toggles the existing User.is_active flag, which
# backend/routes/auth.py's login() already checks and rejects on. No
# existing logic changed — this just exposes an admin-facing switch for it.

@router.post("/{staff_id}/toggle-login")
def toggle_teacher_login(
    staff_id: int,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Blocks (or unblocks) a staff member's portal login without deleting the account."""
    staff = db.query(Staff).filter(Staff.id == staff_id, Staff.school_id == token["school_id"]).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    if not staff.user_id:
        raise HTTPException(status_code=422, detail="This staff member has no portal login to block.")

    user = db.query(User).filter(User.id == staff.user_id, User.school_id == token["school_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Linked login not found")

    user.is_active = not user.is_active
    db.commit()

    return {
        "message": f"Login {'unblocked' if user.is_active else 'blocked'} for {staff.name}.",
        "is_active": user.is_active,
    }