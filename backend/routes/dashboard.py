from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.attendance import Attendance
from backend.models.fee import Fee, FeeStatus
from backend.models.grade import Grade
from backend.models.payment import Payment
from backend.models.staff import Staff
from backend.models.student import Student
from backend.models.student_document import StudentDocument
from backend.models.test_record import TestRecord
from backend.models.user import User
from backend.utils.rbac import require_roles

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard_summary(
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    school_id = token["school_id"]

    students = db.query(Student).filter(Student.school_id == school_id).count()
    fees = db.query(Fee).filter(Fee.school_id == school_id).all()
    grades = db.query(Grade).filter(Grade.school_id == school_id).all()

    total_fee = round(sum(f.amount for f in fees), 2)
    total_paid = round(sum(f.paid_amount for f in fees), 2)
    avg_grade = round(sum(g.percentage for g in grades) / len(grades), 2) if grades else 0.0

    return {
        "school_id": school_id,
        "total_students": students,
        "fees_total": total_fee,
        "fees_collected": total_paid,
        "fees_due": round(total_fee - total_paid, 2),
        "average_percentage": avg_grade,
    }


@router.get("/attendance-today")
def attendance_today(
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    today = date.today()
    records = (
        db.query(Attendance)
        .filter(Attendance.school_id == token["school_id"], Attendance.date == today)
        .all()
    )
    total = len(records)
    present = sum(1 for r in records if r.is_present)

    return {
        "date": today.isoformat(),
        "total_marked": total,
        "present": present,
        "absent": total - present,
    }


@router.get("/metrics")
def dashboard_metrics(
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """Get dashboard metrics for professional dashboard"""
    school_id = token["school_id"]

    # Total students
    total_students = db.query(Student).filter(Student.school_id == school_id).count()
    
    # Fees data
    fees = db.query(Fee).filter(Fee.school_id == school_id).all()
    total_fees_amount = round(sum(f.amount for f in fees), 2)
    total_fees_paid = round(sum(f.paid_amount for f in fees), 2)
    total_fees_due = round(total_fees_amount - total_fees_paid, 2)
    pending_fees_count = sum(1 for f in fees if f.paid_amount < f.amount)
    
    # Attendance data
    attendance_records = db.query(Attendance).filter(Attendance.school_id == school_id).all()
    attendance_rate = 0.0
    if attendance_records:
        present_count = sum(1 for a in attendance_records if a.is_present)
        attendance_rate = round((present_count / len(attendance_records)) * 100, 2)
    
    return {
        "total_students": total_students,
        "total_fees_amount": total_fees_amount,
        "total_fees_due": total_fees_due,
        "total_fees_paid": total_fees_paid,
        "pending_fees_count": pending_fees_count,
        "attendance_rate": attendance_rate,
    }


@router.get("/daily-digest")
def daily_digest(
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    school_id = token["school_id"]
    today = date.today()

    total_students = db.query(Student).filter(Student.school_id == school_id).count()

    today_attendance = (
        db.query(Attendance)
        .filter(Attendance.school_id == school_id, Attendance.date == today)
        .all()
    )
    marked = len(today_attendance)
    present = sum(1 for a in today_attendance if a.is_present)
    absent = marked - present
    attendance_rate_today = round((present / marked) * 100, 2) if marked else None

    fees = db.query(Fee).filter(Fee.school_id == school_id).all()
    total_due = round(sum(f.due_amount for f in fees), 2)
    overdue_count = sum(1 for f in fees if f.status != FeeStatus.paid and f.due_amount > 0)

    payments_today = (
        db.query(Payment)
        .filter(Payment.school_id == school_id, Payment.payment_date == today)
        .all()
    )
    collected_today = round(sum(p.amount_paid for p in payments_today), 2)

    return {
        "date": today.isoformat(),
        "total_students": total_students,
        "attendance": {
            "marked": marked,
            "present": present,
            "absent": absent,
            "not_marked": total_students - marked if total_students >= marked else 0,
            "attendance_rate_today": attendance_rate_today,
        },
        "fees": {
            "collected_today": collected_today,
            "total_outstanding": total_due,
            "overdue_count": overdue_count,
        },
    }


@router.get("/recent-activities")
def recent_activities(
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    school_id = token["school_id"]

    latest_students = (
        db.query(Student)
        .filter(Student.school_id == school_id)
        .order_by(Student.created_at.desc())
        .limit(5)
        .all()
    )
    latest_fees = (
        db.query(Fee)
        .filter(Fee.school_id == school_id)
        .order_by(Fee.updated_at.desc())
        .limit(5)
        .all()
    )

    return {
        "students": [
            {"id": s.id, "name": s.name, "created_at": s.created_at.isoformat()}
            for s in latest_students
        ],
        "fees": [
            {"id": f.id, "fee_name": f.fee_name, "updated_at": f.updated_at.isoformat()}
            for f in latest_fees
        ],
    }


@router.get("/teacher-activity")
def recent_teacher_activity(
    limit: int = Query(default=20, ge=1, le=100),
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """
    Combines attendance marks, grades, test records, and document uploads
    made by TEACHERS (not the admin themselves) into one recent-activity
    feed, newest first. Admin-only — lets the admin see what teachers have
    been doing without hunting through each section separately.
    """
    school_id = token["school_id"]

    # Map of user_id -> display name, scoped to this school's teacher staff,
    # so the feed shows "Miss Sara" instead of a raw user id.
    teacher_names = {
        s.user_id: s.name
        for s in db.query(Staff).filter(Staff.school_id == school_id, Staff.user_id.isnot(None))
    }
    student_names = {s.id: s.name for s in db.query(Student).filter(Student.school_id == school_id)}

    if not teacher_names:
        return {"activities": []}

    teacher_user_ids = list(teacher_names.keys())
    events = []

    for a in (
        db.query(Attendance)
        .filter(Attendance.school_id == school_id, Attendance.marked_by_user_id.in_(teacher_user_ids))
        .order_by(Attendance.created_at.desc())
        .limit(limit)
    ):
        events.append({
            "id": a.id,
            "type": "attendance",
            "teacher": teacher_names.get(a.marked_by_user_id, "Unknown"),
            "student": student_names.get(a.student_id, "Unknown"),
            "detail": f"Marked {'Present' if a.is_present else 'Absent'} for {a.date.isoformat()}",
            "at": a.created_at,
        })

    for g in (
        db.query(Grade)
        .filter(Grade.school_id == school_id, Grade.teacher_id.in_(teacher_user_ids))
        .order_by(Grade.created_at.desc())
        .limit(limit)
    ):
        events.append({
            "id": g.id,
            "type": "grade",
            "teacher": teacher_names.get(g.teacher_id, "Unknown"),
            "student": student_names.get(g.student_id, "Unknown"),
            "detail": f"Added {g.subject} grade: {g.marks_obtained}/{g.total_marks}",
            "at": g.created_at,
        })

    for t in (
        db.query(TestRecord)
        .filter(TestRecord.school_id == school_id, TestRecord.recorded_by_user_id.in_(teacher_user_ids))
        .order_by(TestRecord.created_at.desc())
        .limit(limit)
    ):
        events.append({
            "id": t.id,
            "type": "test_record",
            "teacher": teacher_names.get(t.recorded_by_user_id, "Unknown"),
            "student": student_names.get(t.student_id, "Unknown"),
            "detail": f"Added {t.term_type.value} test record: {t.subject} ({t.marks_obtained}/{t.total_marks})"
            + (" with photo" if t.image_url else ""),
            "at": t.created_at,
        })

    for d in (
        db.query(StudentDocument)
        .filter(StudentDocument.school_id == school_id, StudentDocument.uploaded_by_user_id.in_(teacher_user_ids))
        .order_by(StudentDocument.created_at.desc())
        .limit(limit)
    ):
        events.append({
            "id": d.id,
            "student_id": d.student_id,
            "type": "document",
            "teacher": teacher_names.get(d.uploaded_by_user_id, "Unknown"),
            "student": student_names.get(d.student_id, "Unknown"),
            "detail": f"Uploaded {d.doc_type.value.replace('_', ' ')}",
            "at": d.created_at,
        })

    events.sort(key=lambda e: e["at"], reverse=True)
    events = events[:limit]
    for e in events:
        e["at"] = e["at"].isoformat()

    return {"activities": events}