from datetime import date as dt_date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.attendance import Attendance
from backend.models.fee import Fee
from backend.models.grade import Grade
from backend.models.parent_message import ParentMessage
from backend.models.school import School
from backend.models.student import Student
from backend.models.student_document import StudentDocument
from backend.models.test_record import TestRecord
from backend.schemas.attendance import AttendanceOut
from backend.schemas.fee import FeeOut
from backend.schemas.grade import GradeOut
from backend.schemas.student import StudentOut
from backend.schemas.student_document import StudentDocumentOut
from backend.schemas.test_record import TestRecordOut
from backend.utils.rbac import require_roles
from backend.utils.storage import get_signed_url

router = APIRouter(prefix="/parent", tags=["parent-portal"])


def _my_child(token: dict, db: Session) -> Student:
    """
    Resolves the ONE student linked to the logged-in parent's account.
    Every route below depends on this — it is what keeps a parent's access
    limited to their own child, regardless of what student_id (if any) they
    might try to pass. There is currently one child per parent account (a
    parent with multiple kids at the school gets one login per the auto-
    provisioning logic, so this covers the common case cleanly).
    """
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
