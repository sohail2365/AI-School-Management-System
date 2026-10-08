from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.fee import Fee, FeeStatus
from backend.models.payment import Payment
from backend.models.student import Student
from backend.schemas.fee import FeeCreate, FeeOut, FeeUpdate
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