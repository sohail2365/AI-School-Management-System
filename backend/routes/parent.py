from datetime import date as dt_date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.attendance import Attendance
from backend.models.fee import Fee
from backend.models.grade import Grade
from backend.models.parent_message import ParentMessage
from backend.models.school import School
from backend.models.student import Student
from backend.models.student_document import DocumentType, StudentDocument
from backend.models.test_record import TestRecord
from backend.schemas.attendance import AttendanceOut
from backend.schemas.fee import FeeOut
from backend.schemas.grade import GradeOut
from backend.schemas.student import StudentOut
from backend.schemas.student_document import StudentDocumentOut
from backend.schemas.test_record import TestRecordOut
from backend.utils.rbac import require_roles
from backend.utils.storage import delete_file, get_signed_url, upload_student_file

router = APIRouter(prefix="/parent", tags=["parent-portal"])


def _my_child(token: dict, db: Session) -> Student:
    """Resolves the ONE student linked to the logged-in parent's account."""
    student = (
        db.query(Student)
        .filter(Student.parent_user_id == token["user_id"], Student.school_id == token["school_id"])
        .first()
    )
    if not student:
        raise HTTPException(
            status_code=403,
            detail="No student is linked to this login. Contact your school admin.",
        )
    return student


def _my_school(token: dict, db: Session) -> School:
    school = db.query(School).filter(School.id == token["school_id"]).first()
    if not school or not school.parent_portal_enabled:
        raise HTTPException(status_code=403, detail="Parent portal is not enabled for this school.")
    return school


@router.get("/me")
def get_my_child(
    token: dict = Depends(require_roles(["parent"])),
    db: Session = Depends(get_db),
):
    school = _my_school(token, db)
    student = _my_child(token, db)
    return {
        "student": StudentOut.model_validate(student),
        "visibility": {
            "attendance": school.parent_show_attendance,
            "grades": school.parent_show_grades,
            "fees": school.parent_show_fees,
            "documents": school.parent_show_documents,
            "messages": school.parent_allow_messages,
        },
        "payment_info": school.payment_info if school.parent_show_fees else None,
    }


@router.get("/attendance", response_model=list[AttendanceOut])
def get_my_child_attendance(
    token: dict = Depends(require_roles(["parent"])),
    db: Session = Depends(get_db),
):
    school = _my_school(token, db)
    if not school.parent_show_attendance:
        raise HTTPException(status_code=403, detail="Attendance is not visible to parents at this school.")
    student = _my_child(token, db)
    return (
        db.query(Attendance)
        .filter(Attendance.school_id == token["school_id"], Attendance.student_id == student.id)
        .order_by(Attendance.date.desc())
        .limit(90)
        .all()
    )


@router.get("/grades", response_model=list[GradeOut])
def get_my_child_grades(
    token: dict = Depends(require_roles(["parent"])),
    db: Session = Depends(get_db),
):
    school = _my_school(token, db)
    if not school.parent_show_grades:
        raise HTTPException(status_code=403, detail="Grades are not visible to parents at this school.")
    student = _my_child(token, db)
    return (
        db.query(Grade)
        .filter(Grade.school_id == token["school_id"], Grade.student_id == student.id)
        .order_by(Grade.created_at.desc())
        .all()
    )


@router.get("/test-records", response_model=list[TestRecordOut])
def get_my_child_test_records(
    token: dict = Depends(require_roles(["parent"])),
    db: Session = Depends(get_db),
):
    school = _my_school(token, db)
    if not school.parent_show_grades:
        raise HTTPException(status_code=403, detail="Test records are not visible to parents at this school.")
    student = _my_child(token, db)
    return (
        db.query(TestRecord)
        .filter(TestRecord.school_id == token["school_id"], TestRecord.student_id == student.id)
        .order_by(TestRecord.created_at.desc())
        .all()
    )


@router.get("/fees", response_model=list[FeeOut])
def get_my_child_fees(
    token: dict = Depends(require_roles(["parent"])),
    db: Session = Depends(get_db),
):
    school = _my_school(token, db)
    if not school.parent_show_fees:
        raise HTTPException(status_code=403, detail="Fees are not visible to parents at this school.")
    student = _my_child(token, db)
    return (
        db.query(Fee)
        .filter(Fee.school_id == token["school_id"], Fee.student_id == student.id)
        .order_by(Fee.month.desc())
        .all()
    )


@router.get("/documents", response_model=list[StudentDocumentOut])
def get_my_child_documents(
    token: dict = Depends(require_roles(["parent"])),
    db: Session = Depends(get_db),
):
    school = _my_school(token, db)
    if not school.parent_show_documents:
        raise HTTPException(status_code=403, detail="Documents are not visible to parents at this school.")
    student = _my_child(token, db)
    return (
        db.query(StudentDocument)
        .filter(StudentDocument.school_id == token["school_id"], StudentDocument.student_id == student.id)
        .order_by(StudentDocument.created_at.desc())
        .all()
    )


@router.get("/documents/{document_id}/url")
def get_my_child_document_url(
    document_id: int,
    token: dict = Depends(require_roles(["parent"])),
    db: Session = Depends(get_db),
):
    school = _my_school(token, db)
    if not school.parent_show_documents:
        raise HTTPException(status_code=403, detail="Documents are not visible to parents at this school.")
    student = _my_child(token, db)
    doc = (
        db.query(StudentDocument)
        .filter(
            StudentDocument.id == document_id,
            StudentDocument.student_id == student.id,
            StudentDocument.school_id == token["school_id"],
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"url": get_signed_url(doc.file_url), "expires_in_seconds": 3600}


# ==================== MESSAGES (parent <-> school) ====================

@router.get("/messages")
def get_my_messages(
    token: dict = Depends(require_roles(["parent"])),
    db: Session = Depends(get_db),
):
    school = _my_school(token, db)
    if not school.parent_allow_messages:
        raise HTTPException(status_code=403, detail="Messaging is not enabled at this school.")
    student = _my_child(token, db)
    messages = (
        db.query(ParentMessage)
        .filter(ParentMessage.school_id == token["school_id"], ParentMessage.student_id == student.id)
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


@router.post("/messages", status_code=status.HTTP_201_CREATED)
def send_my_message(
    message: str,
    token: dict = Depends(require_roles(["parent"])),
    db: Session = Depends(get_db),
):
    school = _my_school(token, db)
    if not school.parent_allow_messages:
        raise HTTPException(status_code=403, detail="Messaging is not enabled at this school.")
    if not message or not message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    student = _my_child(token, db)
    msg = ParentMessage(
        school_id=token["school_id"],
        student_id=student.id,
        sender_user_id=token["user_id"],
        sender_role="parent",
        message=message.strip()[:2000],
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "created_at": msg.created_at.isoformat()}


# ==================== PARENT: DOCUMENT UPLOAD ====================
# Parent apne bachche ke documents upload aur delete kar sakta hai.
# Security: _my_child() se verify hota hai ke student parent ka bachcha hai.
# Storage: Same helper as admin/teacher (works on Vercel via cloud storage).

@router.post(
    "/documents/upload",
    response_model=StudentDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def parent_upload_document(
    doc_type: str = Query(..., description="id_card | b_form | test_paper | profile_photo | other"),
    label: str | None = Query(default=None, max_length=150),
    file: UploadFile = File(...),
    token: dict = Depends(require_roles(["parent"])),
    db: Session = Depends(get_db),
):
    """
    Parent apne bachche ka document upload karein.
    Uses same cloud storage helper as admin/teacher document upload.
    """
    school = _my_school(token, db)
    if not school.parent_show_documents:
        raise HTTPException(status_code=403, detail="Documents are not enabled for parents at this school.")

    # Verify parent owns this student
    student = _my_child(token, db)

    # Validate doc_type using same enum as student-documents
    try:
        parsed_type = DocumentType(doc_type)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="doc_type must be one of: id_card, b_form, test_paper, profile_photo, other",
        )

    # ✅ Use SAME cloud storage helper as admin/teacher
    path = upload_student_file(file, token["school_id"], student.id, subfolder=parsed_type.value)

    doc = StudentDocument(
        school_id=token["school_id"],
        student_id=student.id,
        doc_type=parsed_type,
        file_url=path,
        file_name=file.filename,
        label=label,
        uploaded_by_user_id=token.get("user_id"),
    )
    db.add(doc)

    # Profile photo also updates the canonical card photo (same as admin flow)
    if parsed_type == DocumentType.profile_photo:
        student.photo_url = path

    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def parent_delete_document(
    document_id: int,
    token: dict = Depends(require_roles(["parent"])),
    db: Session = Depends(get_db),
):
    """Parent apne bachche ka document delete kar sake."""
    school = _my_school(token, db)
    if not school.parent_show_documents:
        raise HTTPException(status_code=403, detail="Documents are not enabled for parents.")

    student = _my_child(token, db)

    doc = (
        db.query(StudentDocument)
        .filter(
            StudentDocument.id == document_id,
            StudentDocument.student_id == student.id,
            StudentDocument.school_id == token["school_id"],
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # ✅ Use SAME cloud delete helper
    delete_file(doc.file_url)
    db.delete(doc)
    db.commit()
    return None