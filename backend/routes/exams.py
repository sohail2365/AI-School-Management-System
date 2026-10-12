"""
Exam / Datesheet endpoints.
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.school import School
from backend.models.exam import Exam, ExamEntry
from backend.auth import require_roles   # ← apne auth helper ka correct path

router = APIRouter(prefix="/exams", tags=["exams"])


# ==================== SCHEMAS ====================
class EntryIn(BaseModel):
    subject: str
    exam_date: date
    exam_time: str | None = None
    day: str | None = None
    total_marks: int | None = None
    sort_order: int | None = 0


class EntryOut(BaseModel):
    id: int
    class_name: str
    subject: str
    exam_date: date
    exam_time: str | None
    day: str | None
    total_marks: int | None
    sort_order: int

    class Config:
        from_attributes = True


class ExamCreate(BaseModel):
    name: str
    notes: str | None = None


class ExamUpdate(BaseModel):
    name: str | None = None
    notes: str | None = None


# ==================== HELPERS ====================
def _get_exam_or_404(db: Session, exam_id: int, school_id: int) -> Exam:
    exam = db.query(Exam).filter(
        Exam.id == exam_id, Exam.school_id == school_id
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


def _auto_day(d: date) -> str:
    return d.strftime("%A")


# ==================== ENDPOINTS ====================

@router.get("")
def list_exams(
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """List all exams for the school with entry counts."""
    school_id = token["school_id"]
    exams = db.query(Exam).filter(Exam.school_id == school_id).order_by(Exam.created_at.desc()).all()

    result = []
    for ex in exams:
        classes = sorted({e.class_name for e in ex.entries})
        result.append({
            "id": ex.id,
            "name": ex.name,
            "notes": ex.notes,
            "created_at": ex.created_at.isoformat() if ex.created_at else None,
            "classes": classes,
            "entry_count": len(ex.entries),
        })
    return result


@router.post("")
def create_exam(
    payload: ExamCreate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Create a new exam."""
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Exam name required")

    ex = Exam(
        school_id=token["school_id"],
        name=name,
        notes=(payload.notes or None),
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return {"id": ex.id, "name": ex.name, "message": "Exam created"}


@router.put("/{exam_id}")
def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    ex = _get_exam_or_404(db, exam_id, token["school_id"])
    if payload.name is not None:
        n = payload.name.strip()
        if not n:
            raise HTTPException(status_code=422, detail="Exam name cannot be empty")
        ex.name = n
    if payload.notes is not None:
        ex.notes = payload.notes
    db.commit()
    return {"id": ex.id, "message": "Exam updated"}


@router.delete("/{exam_id}")
def delete_exam(
    exam_id: int,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    ex = _get_exam_or_404(db, exam_id, token["school_id"])
    db.delete(ex)
    db.commit()
    return {"message": "Exam deleted"}


# ==================== ENTRIES ====================

@router.get("/{exam_id}/entries")
def list_entries(
    exam_id: int,
    class_name: str | None = None,
    token: dict = Depends(require_roles(["admin", "teacher"])),
    db: Session = Depends(get_db),
):
    """List entries for one exam (optionally filter by class)."""
    ex = _get_exam_or_404(db, exam_id, token["school_id"])
    q = db.query(ExamEntry).filter(ExamEntry.exam_id == ex.id)
    if class_name:
        q = q.filter(ExamEntry.class_name == class_name)
    entries = q.order_by(ExamEntry.exam_date, ExamEntry.sort_order).all()

    return {
        "exam": {"id": ex.id, "name": ex.name, "notes": ex.notes},
        "entries": [
            {
                "id": e.id,
                "class_name": e.class_name,
                "subject": e.subject,
                "exam_date": e.exam_date.isoformat(),
                "exam_time": e.exam_time,
                "day": e.day or _auto_day(e.exam_date),
                "total_marks": e.total_marks,
                "sort_order": e.sort_order,
            } for e in entries
        ],
    }


@router.post("/{exam_id}/entries")
def bulk_add_entries(
    exam_id: int,
    class_name: str,
    entries: list[EntryIn],
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Replace all entries for a class in this exam (bulk save)."""
    ex = _get_exam_or_404(db, exam_id, token["school_id"])
    cls = (class_name or "").strip()
    if not cls:
        raise HTTPException(status_code=422, detail="class_name required")
    if not entries:
        raise HTTPException(status_code=422, detail="No entries provided")

    # Delete existing entries for this class in this exam
    db.query(ExamEntry).filter(
        ExamEntry.exam_id == ex.id,
        ExamEntry.class_name == cls,
    ).delete(synchronize_session=False)

    # Insert new
    for idx, e in enumerate(entries):
        subject = (e.subject or "").strip()
        if not subject:
            continue
        db.add(ExamEntry(
            exam_id=ex.id,
            class_name=cls,
            subject=subject,
            exam_date=e.exam_date,
            exam_time=(e.exam_time or None),
            day=(e.day or _auto_day(e.exam_date)),
            total_marks=e.total_marks,
            sort_order=e.sort_order if e.sort_order is not None else idx,
        ))

    db.commit()
    return {"message": f"{len(entries)} entries saved for Class {cls}"}


@router.delete("/entries/{entry_id}")
def delete_entry(
    entry_id: int,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    entry = db.query(ExamEntry).join(Exam).filter(
        ExamEntry.id == entry_id,
        Exam.school_id == token["school_id"],
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return {"message": "Entry deleted"}