from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.fee import Fee, FeeStatus
from backend.models.payment import Payment
from backend.models.student import Student
from backend.schemas.fee import FeeCreate, FeeOut, FeeUpdate, FifoPaymentRequest
from backend.schemas.payment import PaymentCreate, PaymentOut
from backend.utils.rbac import require_roles

router = APIRouter(prefix="/fees", tags=["fees"])


class BulkFeeCreate(BaseModel):
    class_name: str = Field(min_length=1, max_length=20)
    fee_name: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    due_date: date | None = None
    month: str | None = Field(default=None, max_length=20)
    skip_if_exists: bool = True


class BulkFeeResult(BaseModel):
    created_count: int
    skipped_count: int
    created_fee_ids: list[int]


def _recalculate_fee(fee: Fee) -> None:
    fee.due_amount = round(fee.amount - fee.paid_amount, 2)
    if fee.paid_amount <= 0:
        fee.status = FeeStatus.pending
    elif fee.paid_amount < fee.amount:
        fee.status = FeeStatus.partial
    else:
        fee.status = FeeStatus.paid
        fee.due_amount = 0.0


@router.get("", response_model=list[FeeOut])
def list_fees(
    status: str | None = None,
    class_name: str | None = None,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    query = db.query(Fee).filter(Fee.school_id == token["school_id"])
    if status:
        try:
            status_enum = FeeStatus(status)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid status. Use pending, partial or paid")
        query = query.filter(Fee.status == status_enum)
    if class_name:
        sids = [r.id for r in db.query(Student.id).filter(
            Student.school_id == token["school_id"],
            Student.class_name == class_name,
        ).all()]
        if not sids:
            return []
        query = query.filter(Fee.student_id.in_(sids))
    return query.order_by(Fee.id.desc()).all()


@router.get("/student/{student_id}", response_model=list[FeeOut])
def get_student_fees(
    student_id: int,
    token: dict = Depends(require_roles(["admin", "teacher", "parent", "student"])),
    db: Session = Depends(get_db),
):
    return (
        db.query(Fee)
        .filter(Fee.school_id == token["school_id"], Fee.student_id == student_id)
        .order_by(Fee.id.desc())
        .all()
    )


@router.get("/pending", response_model=list[FeeOut])
def get_pending_fees(
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    return (
        db.query(Fee)
        .filter(Fee.school_id == token["school_id"], Fee.status != FeeStatus.paid)
        .order_by(Fee.id.desc())
        .all()
    )


@router.get("/class-summary")
def class_fee_summary(
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """
    Read-only breakdown of fee collection per class. Purely additive —
    does not touch any existing fee logic.
    """
    fees = db.query(Fee).filter(Fee.school_id == token["school_id"]).all()
    if not fees:
        return []

    student_ids = {f.student_id for f in fees}
    students = (
        db.query(Student)
        .filter(Student.school_id == token["school_id"], Student.id.in_(student_ids))
        .all()
    )
    class_by_student = {s.id: (s.class_name or "Unassigned") for s in students}

    classes: dict[str, dict] = {}
    for fee in fees:
        class_name = class_by_student.get(fee.student_id, "Unassigned")
        if class_name not in classes:
            classes[class_name] = {
                "class_name": class_name,
                "student_ids": set(),
                "total_amount": 0.0,
                "total_paid": 0.0,
                "total_due": 0.0,
                "overdue_count": 0,
            }
        entry = classes[class_name]
        entry["student_ids"].add(fee.student_id)
        entry["total_amount"] = round(entry["total_amount"] + fee.amount, 2)
        entry["total_paid"] = round(entry["total_paid"] + fee.paid_amount, 2)
        entry["total_due"] = round(entry["total_due"] + fee.due_amount, 2)
        if fee.status != FeeStatus.paid and fee.due_amount > 0:
            entry["overdue_count"] += 1

    result = []
    for entry in classes.values():
        result.append(
            {
                "class_name": entry["class_name"],
                "student_count": len(entry["student_ids"]),
                "total_amount": entry["total_amount"],
                "total_paid": entry["total_paid"],
                "total_due": entry["total_due"],
                "overdue_count": entry["overdue_count"],
                "collection_rate": round((entry["total_paid"] / entry["total_amount"]) * 100, 2)
                if entry["total_amount"]
                else 0.0,
            }
        )

    result.sort(key=lambda c: c["total_due"], reverse=True)
    return result


@router.get("/family-summary")
def family_fee_summary(
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """
    Groups outstanding dues by guardian phone number so siblings under the
    same contact get ONE combined reminder instead of one message per child.
    Students without a phone number on file are excluded (nothing to send to).
    """
    fees = (
        db.query(Fee)
        .filter(Fee.school_id == token["school_id"], Fee.status != FeeStatus.paid, Fee.due_amount > 0)
        .all()
    )
    if not fees:
        return []

    student_ids = {f.student_id for f in fees}
    students = (
        db.query(Student)
        .filter(Student.school_id == token["school_id"], Student.id.in_(student_ids))
        .all()
    )
    students_by_id = {s.id: s for s in students}

    families: dict[str, dict] = {}
    for fee in fees:
        student = students_by_id.get(fee.student_id)
        if not student or not student.phone:
            continue

        phone = student.phone
        if phone not in families:
            families[phone] = {
                "phone": phone,
                "father_name": student.father_name,
                "students": {},
                "total_due": 0.0,
            }

        family = families[phone]
        if student.id not in family["students"]:
            family["students"][student.id] = {
                "student_id": student.id,
                "name": student.name,
                "class_name": student.class_name,
                "due_amount": 0.0,
                "fees": [],
            }

        entry = family["students"][student.id]
        entry["due_amount"] = round(entry["due_amount"] + fee.due_amount, 2)
        entry["fees"].append({"fee_name": fee.fee_name, "due_amount": fee.due_amount, "due_date": fee.due_date})
        family["total_due"] = round(family["total_due"] + fee.due_amount, 2)

    result = []
    for family in families.values():
        family["students"] = list(family["students"].values())
        result.append(family)

    result.sort(key=lambda f: f["total_due"], reverse=True)
    return result


@router.post("/bulk-generate", response_model=BulkFeeResult, status_code=status.HTTP_201_CREATED)
def bulk_generate_fees(
    payload: BulkFeeCreate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    students = (
        db.query(Student)
        .filter(Student.school_id == token["school_id"], Student.class_name == payload.class_name)
        .all()
    )
    if not students:
        raise HTTPException(status_code=404, detail="No students found in this class")

    created_ids: list[int] = []
    skipped = 0

    for student in students:
        if payload.skip_if_exists:
            existing = (
                db.query(Fee)
                .filter(
                    Fee.school_id == token["school_id"],
                    Fee.student_id == student.id,
                    Fee.fee_name == payload.fee_name,
                    Fee.month == payload.month,
                )
                .first()
            )
            if existing:
                skipped += 1
                continue

        fee = Fee(
            school_id=token["school_id"],
            student_id=student.id,
            fee_name=payload.fee_name,
            amount=payload.amount,
            due_date=payload.due_date,
            paid_amount=0.0,
            due_amount=payload.amount,
            month=payload.month,
            status=FeeStatus.pending,
        )
        db.add(fee)
        db.flush()
        created_ids.append(fee.id)

    db.commit()
    return BulkFeeResult(created_count=len(created_ids), skipped_count=skipped, created_fee_ids=created_ids)


@router.post("", response_model=FeeOut, status_code=status.HTTP_201_CREATED)
def create_fee(
    payload: FeeCreate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    student = (
        db.query(Student)
        .filter(Student.id == payload.student_id, Student.school_id == token["school_id"])
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    fee = Fee(
        school_id=token["school_id"],
        student_id=payload.student_id,
        fee_name=payload.fee_name,
        amount=payload.amount,
        due_date=payload.due_date,
        paid_amount=0.0,
        due_amount=payload.amount,
        month=payload.month,
        fee_type=payload.fee_type,   # ✅ NEW
        status=FeeStatus.pending,
    )
    db.add(fee)
    db.commit()
    db.refresh(fee)
    return fee


@router.put("/{fee_id}", response_model=FeeOut)
def update_fee(
    fee_id: int,
    payload: FeeUpdate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    fee = db.query(Fee).filter(Fee.id == fee_id, Fee.school_id == token["school_id"]).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(fee, key, value)

    _recalculate_fee(fee)
    db.commit()
    db.refresh(fee)
    return fee


@router.delete("/{fee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fee(
    fee_id: int,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    fee = db.query(Fee).filter(Fee.id == fee_id, Fee.school_id == token["school_id"]).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")

    db.delete(fee)
    db.commit()


@router.post("/{fee_id}/payment", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def record_payment(
    fee_id: int,
    payload: PaymentCreate,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    fee = db.query(Fee).filter(Fee.id == fee_id, Fee.school_id == token["school_id"]).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")

    if payload.amount_paid > fee.due_amount:
        raise HTTPException(status_code=422, detail="Payment cannot exceed due amount")

    payment = Payment(
        school_id=token["school_id"],
        fee_id=fee_id,
        amount_paid=payload.amount_paid,
        payment_date=payload.payment_date,
        payment_method=payload.payment_method,
        receipt_number=payload.receipt_number,
    )
    db.add(payment)

    fee.paid_amount = round(fee.paid_amount + payload.amount_paid, 2)
    _recalculate_fee(fee)

    db.commit()
    db.refresh(payment)
    return payment


@router.get("/report")
def fee_collection_report(
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    fees = db.query(Fee).filter(Fee.school_id == token["school_id"]).all()
    total = round(sum(f.amount for f in fees), 2)
    paid = round(sum(f.paid_amount for f in fees), 2)
    due = round(total - paid, 2)

    return {
        "school_id": token["school_id"],
        "total_fee_amount": total,
        "total_paid": paid,
        "total_due": due,
        "collection_rate": round((paid / total) * 100, 2) if total else 0.0,
    }

# ==================== ✅ NEW: STUDENT FEE STATEMENT ====================

@router.get("/students-summary")
def class_students_fee_summary(
    class_name: str,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """
    List of students in a class with fee summary.
    Used for the class fee view — instead of raw fee rows, show student cards/rows.
    """
    students = (
        db.query(Student)
        .filter(Student.school_id == token["school_id"], Student.class_name == class_name)
        .all()
    )
    if not students:
        return []

    student_ids = [s.id for s in students]
    fees = (
        db.query(Fee)
        .filter(Fee.school_id == token["school_id"], Fee.student_id.in_(student_ids))
        .all()
    )

    by_student: dict[int, list[Fee]] = {}
    for f in fees:
        by_student.setdefault(f.student_id, []).append(f)

    def sort_key(s):
        try:
            return (s.class_name or "", int(str(s.roll_number).strip()))
        except (ValueError, TypeError):
            return (s.class_name or "", 999999)

    students = sorted(students, key=sort_key)

    result = []
    for s in students:
        fs = by_student.get(s.id, [])
        total = round(sum(f.amount for f in fs), 2)
        paid = round(sum(f.paid_amount for f in fs), 2)
        pending = round(total - paid, 2)
        pending_count = sum(1 for f in fs if f.status != FeeStatus.paid and f.due_amount > 0)
        result.append({
            "id": s.id,
            "name": s.name,
            "father_name": s.father_name,
            "roll_number": s.roll_number,
            "class_name": s.class_name,
            "phone": s.phone,
            "total_amount": total,
            "total_paid": paid,
            "total_pending": pending,
            "pending_count": pending_count,
            "is_clear": pending <= 0,
        })
    return result


@router.get("/student/{student_id}/statement")
def get_student_statement(
    student_id: int,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """
    Full fee statement for a single student:
    - student info
    - summary (total, paid, pending)
    - all fees (frontend groups by month/type)
    - payment history
    """
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.school_id == token["school_id"])
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    fees = (
        db.query(Fee)
        .filter(Fee.school_id == token["school_id"], Fee.student_id == student_id)
        .order_by(Fee.created_at.desc(), Fee.id.desc())
        .all()
    )

    fee_ids = [f.id for f in fees]
    payments: list[Payment] = []
    if fee_ids:
        payments = (
            db.query(Payment)
            .filter(Payment.school_id == token["school_id"], Payment.fee_id.in_(fee_ids))
            .order_by(Payment.payment_date.desc(), Payment.id.desc())
            .all()
        )

    total_amount = round(sum(f.amount for f in fees), 2)
    total_paid = round(sum(f.paid_amount for f in fees), 2)
    total_pending = round(total_amount - total_paid, 2)

    def fee_dict(f: Fee):
        return {
            "id": f.id,
            "fee_name": f.fee_name,
            "fee_type": f.fee_type or "monthly",
            "month": f.month,
            "amount": f.amount,
            "paid_amount": f.paid_amount,
            "due_amount": f.due_amount,
            "due_date": f.due_date.isoformat() if f.due_date else None,
            "status": f.status.value if hasattr(f.status, "value") else str(f.status),
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }

    return {
        "student": {
            "id": student.id,
            "name": student.name,
            "father_name": student.father_name,
            "class_name": student.class_name,
            "roll_number": student.roll_number,
            "phone": student.phone,
            "photo_url": student.photo_url,
        },
        "summary": {
            "total_amount": total_amount,
            "total_paid": total_paid,
            "total_pending": total_pending,
        },
        "current_month": date.today().strftime("%Y-%m"),
        "fees": [fee_dict(f) for f in fees],
        "payments": [
            {
                "id": p.id,
                "fee_id": p.fee_id,
                "amount_paid": p.amount_paid,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "payment_method": p.payment_method,
                "receipt_number": p.receipt_number,
            }
            for p in payments
        ],
    }


@router.post("/student/{student_id}/record-payment")
def record_payment_fifo(
    student_id: int,
    payload: FifoPaymentRequest,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """
    Record a payment that auto-applies FIFO across the student's pending fees.
    Oldest (by due_date, then id) cleared first.
    """
    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.school_id == token["school_id"])
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    pending_fees = (
        db.query(Fee)
        .filter(
            Fee.school_id == token["school_id"],
            Fee.student_id == student_id,
            Fee.status != FeeStatus.paid,
            Fee.due_amount > 0,
        )
        .order_by(Fee.due_date.asc().nullslast(), Fee.id.asc())
        .all()
    )
    if not pending_fees:
        raise HTTPException(status_code=422, detail="No pending fees to apply payment")

    total_pending = round(sum(f.due_amount for f in pending_fees), 2)
    if payload.amount > total_pending:
        raise HTTPException(
            status_code=422,
            detail=f"Payment Rs. {payload.amount} exceeds total pending Rs. {total_pending}",
        )

    remaining = round(payload.amount, 2)
    applied: list[dict] = []
    payment_date = payload.payment_date or date.today()

    for fee in pending_fees:
        if remaining <= 0:
            break
        pay_now = round(min(remaining, fee.due_amount), 2)

        payment = Payment(
            school_id=token["school_id"],
            fee_id=fee.id,
            amount_paid=pay_now,
            payment_date=payment_date,
            payment_method=payload.payment_method,
            receipt_number=payload.receipt_number,
        )
        db.add(payment)

        fee.paid_amount = round(fee.paid_amount + pay_now, 2)
        _recalculate_fee(fee)

        applied.append({
            "fee_id": fee.id,
            "fee_name": fee.fee_name,
            "fee_type": fee.fee_type,
            "amount_applied": pay_now,
            "new_status": fee.status.value if hasattr(fee.status, "value") else str(fee.status),
        })
        remaining = round(remaining - pay_now, 2)

    db.commit()

    return {
        "total_paid": payload.amount,
        "applied_to": applied,
        "remaining_after": round(total_pending - payload.amount, 2),
    }