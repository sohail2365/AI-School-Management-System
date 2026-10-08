from datetime import date as dt_date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.attendance import Attendance
from backend.models.student import Student
from backend.schemas.attendance import AttendanceCreate, AttendanceOut, AttendanceUpdate
from backend.utils.rbac import require_roles

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("/register/{class_name}")
def attendance_register(
    class_name: str,
    month: str,  # format: YYYY-MM
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """
    Class-wise monthly attendance register: every student in the class as
    rows, every day of the month as columns (P/A/blank). Built for printing
    the traditional paper register format schools are used to.
    """
    try:
        year, mon = month.split("-")
        year, mon = int(year), int(mon)
        if not (1 <= mon <= 12):
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=400, detail="Month must be in YYYY-MM format")

    students = (
        db.query(Student)
        .filter(Student.school_id == token["school_id"], Student.class_name == class_name)
        .order_by(Student.roll_number)
        .all()
    )
    if not students:
        raise HTTPException(status_code=404, detail="No students found in this class")

    # Month boundaries
    month_start = dt_date(year, mon, 1)
    month_end = dt_date(year + 1, 1, 1) if mon == 12 else dt_date(year, mon + 1, 1)
    days_in_month = (month_end - month_start).days

    student_ids = [s.id for s in students]
    records = (
        db.query(Attendance)
        .filter(
            Attendance.school_id == token["school_id"],
            Attendance.student_id.in_(student_ids),
            Attendance.date >= month_start,
            Attendance.date < month_end,
        )
        .all()
    )

    # student_id -> {day_number: is_present}
    by_student: dict[int, dict[int, bool]] = {}
    for r in records:
        by_student.setdefault(r.student_id, {})[r.date.day] = r.is_present

    rows = []
    for s in students:
        day_map = by_student.get(s.id, {})
        present_count = sum(1 for v in day_map.values() if v)
        marked_count = len(day_map)
        rows.append({
            "student_id": s.id,
            "name": s.name,
            "roll_number": s.roll_number,
            "days": {str(d): day_map.get(d) for d in range(1, days_in_month + 1)},
            "present_count": present_count,
            "absent_count": marked_count - present_count,
        })

    return {
        "class_name": class_name,
        "month": month,
        "days_in_month": days_in_month,
        "students": rows,
    }

# ==================== CLASS-WISE NAVIGATION ====================
# ==================== CLASS-WISE NAVIGATION ====================
@router.get("/classes-summary")
def attendance_classes_summary(
    date: dt_date | None = None,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """Per-class attendance snapshot for a given date (defaults to today)."""
    import re
    from sqlalchemy import func

    target_date = date or dt_date.today()

    class_rows = (
        db.query(Student.class_name, func.count(Student.id).label("student_count"))
        .filter(Student.school_id == token["school_id"])
        .group_by(Student.class_name)
        .all()
    )

    attendance_rows = (
        db.query(Attendance)
        .filter(
            Attendance.school_id == token["school_id"],
            Attendance.date == target_date,
        )
        .all()
    )

    student_ids = {a.student_id for a in attendance_rows}
    students_map = {}
    if student_ids:
        pairs = (
            db.query(Student.id, Student.class_name)
            .filter(
                Student.school_id == token["school_id"],
                Student.id.in_(student_ids),
            )
            .all()
        )
        students_map = {sid: cname for sid, cname in pairs}

    per_class = {}
    for a in attendance_rows:
        cls = students_map.get(a.student_id)
        if cls is None:
            continue
        entry = per_class.setdefault(cls, {"marked": 0, "present": 0})
        entry["marked"] += 1
        if a.is_present:
            entry["present"] += 1

    def _sort_key(name):
        parts = re.split(r"(\d+)", name or "")
        return [int(p) if p.isdigit() else p.lower() for p in parts if p]

    result = []
    for row in sorted(class_rows, key=lambda r: _sort_key(r.class_name)):
        stats = per_class.get(row.class_name, {"marked": 0, "present": 0})
        marked = stats["marked"]
        present = stats["present"]
        result.append({
            "class_name": row.class_name,
            "student_count": row.student_count,
            "marked_count": marked,
            "present_count": present,
            "absent_count": marked - present,
            "attendance_rate": round((present / marked) * 100, 2) if marked else 0.0,
        })
    return result

@router.get("", response_model=list[AttendanceOut])
def list_attendance(
    date: dt_date | None = None,
    student_id: int | None = None,
    class_name: str | None = None,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    query = db.query(Attendance).filter(Attendance.school_id == token["school_id"])
    if date:
        query = query.filter(Attendance.date == date)
    if student_id:
        query = query.filter(Attendance.student_id == student_id)
    if class_name:
        sids = [r.id for r in db.query(Student.id).filter(
            Student.school_id == token["school_id"],
            Student.class_name == class_name,
        ).all()]
        if not sids:
            return []
        query = query.filter(Attendance.student_id.in_(sids))
    return query.order_by(Attendance.date.desc(), Attendance.id.desc()).all()

@router.get("/date/{date}", response_model=list[AttendanceOut])
def get_attendance_by_date(
    date: dt_date,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    return (
        db.query(Attendance)
        .filter(Attendance.school_id == token["school_id"], Attendance.date == date)
        .order_by(Attendance.id.desc())
        .all()
    )


@router.get("/student/{student_id}", response_model=list[AttendanceOut])
def get_student_attendance(
    student_id: int,
    token: dict = Depends(require_roles(["admin", "teacher", "parent", "student"])),
    db: Session = Depends(get_db),
):
    return (
        db.query(Attendance)
        .filter(
            Attendance.school_id == token["school_id"],
            Attendance.student_id == student_id,
        )
        .order_by(Attendance.date.desc())
        .all()
    )


@router.post("", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def mark_attendance(
    payload: AttendanceCreate,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    if payload.date > dt_date.today():
        raise HTTPException(
            status_code=422,
            detail="Attendance can only be marked for current or past dates",
        )

    student = (
        db.query(Student)
        .filter(
            Student.id == payload.student_id,
            Student.school_id == token["school_id"],
        )
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    existing = (
        db.query(Attendance)
        .filter(
            Attendance.school_id == token["school_id"],
            Attendance.student_id == payload.student_id,
            Attendance.date == payload.date,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Attendance already marked for this date")

    record = Attendance(
        school_id=token["school_id"],
        student_id=payload.student_id,
        date=payload.date,
        is_present=payload.is_present,
        remarks=payload.remarks,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ✅ NEW: Update an existing attendance record. Purely additive.
@router.put("/{attendance_id}", response_model=AttendanceOut)
def update_attendance(
    attendance_id: int,
    payload: AttendanceUpdate,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    record = (
        db.query(Attendance)
        .filter(Attendance.id == attendance_id, Attendance.school_id == token["school_id"])
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


# ✅ NEW: Delete an attendance record. Purely additive.
@router.delete("/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(
    attendance_id: int,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    record = (
        db.query(Attendance)
        .filter(Attendance.id == attendance_id, Attendance.school_id == token["school_id"])
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    db.delete(record)
    db.commit()
    return None


@router.get("/report/{student_id}")
def attendance_report_student(
    student_id: int,
    token: dict = Depends(require_roles(["admin", "teacher", "parent", "student"])),
    db: Session = Depends(get_db),
):
    records = (
        db.query(Attendance)
        .filter(
            Attendance.school_id == token["school_id"],
            Attendance.student_id == student_id,
        )
        .all()
    )
    total = len(records)
    present = sum(1 for r in records if r.is_present)
    percentage = round((present / total) * 100, 2) if total else 0.0

    return {
        "student_id": student_id,
        "total_days": total,
        "present_days": present,
        "attendance_percentage": percentage,
        "absent_dates": [r.date.isoformat() for r in records if not r.is_present],
    }


@router.get("/class/{class_name}/report")
def attendance_report_class(
    class_name: str,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    students = (
        db.query(Student)
        .filter(
            Student.school_id == token["school_id"],
            Student.class_name == class_name,
        )
        .all()
    )

    result = []
    for s in students:
        records = (
            db.query(Attendance)
            .filter(
                Attendance.school_id == token["school_id"],
                Attendance.student_id == s.id,
            )
            .all()
        )
        total = len(records)
        present = sum(1 for r in records if r.is_present)
        pct = round((present / total) * 100, 2) if total else 0.0
        result.append(
            {
                "student_id": s.id,
                "student_name": s.name,
                "attendance_percentage": pct,
            }
        )

    return {"class_name": class_name, "students": result}