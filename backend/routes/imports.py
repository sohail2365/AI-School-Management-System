"""
Bulk CSV import — students (Phase 1). Handles Excel-exported CSVs with
BOM, mixed case headers, and common date formats (YYYY-MM-DD, DD-MM-YYYY,
DD/MM/YYYY). Duplicate roll numbers in the same class are skipped instead
of erroring the whole import.

Read-only with respect to existing data — only inserts, never updates or
deletes. Safe to re-run: duplicates are skipped, not double-inserted.
"""
import csv
import io
import secrets
from datetime import datetime, date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.school import School
from backend.models.student import Student, Gender
from backend.models.user import User, UserRole
from backend.utils.password import hash_password
from backend.utils.rbac import require_roles

router = APIRouter(prefix="/imports", tags=["imports"])


def _parse_date(value: str):
    """Try common date formats; return None if unparseable."""
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


@router.post("/students")
async def bulk_import_students(
    file: UploadFile = File(...),
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Only .csv files are allowed.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    # Handle BOM (Excel adds one), fall back to latin-1 for odd encoding
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1", errors="replace")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV has no header row.")

    # Normalize header names: "Father Name" / "father-name" / "FATHER_NAME"
    # all become "father_name" so users can export from Excel and re-upload
    # without having to clean up the header row.
    field_map = {}
    for original in reader.fieldnames:
        key = (original or "").strip().lower().replace(" ", "_").replace("-", "_")
        field_map[key] = original

    required = ["name", "class_name", "roll_number"]
    # Accept "class" as alias for "class_name" and "roll" for "roll_number"
    if "class_name" not in field_map and "class" in field_map:
        field_map["class_name"] = field_map["class"]
    if "roll_number" not in field_map and "roll" in field_map:
        field_map["roll_number"] = field_map["roll"]

    missing = [r for r in required if r not in field_map]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required columns: {', '.join(missing)}. "
                   f"Required at minimum: name, class_name, roll_number.",
        )

    school = db.query(School).filter(School.id == token["school_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")

    created = 0
    skipped = 0
    parents_created = 0
    errors = []

    def get(row, key):
        original = field_map.get(key)
        if not original:
            return ""
        return (row.get(original) or "").strip()

    for row_num, row in enumerate(reader, start=2):  # Row 1 = header
        try:
            name = get(row, "name")
            class_name = get(row, "class_name")
            roll_number = get(row, "roll_number")

            if not name or not class_name or not roll_number:
                errors.append(f"Row {row_num}: name, class_name, roll_number are required")
                skipped += 1
                continue

            # Skip duplicates silently (same class + roll)
            exists = (
                db.query(Student)
                .filter(
                    Student.school_id == token["school_id"],
                    Student.class_name == class_name,
                    Student.roll_number == roll_number,
                )
                .first()
            )
            if exists:
                errors.append(f"Row {row_num}: Roll {roll_number} already exists in class {class_name}")
                skipped += 1
                continue

            gender_raw = get(row, "gender").lower()
            gender = None
            if gender_raw in ("male", "female", "other"):
                gender = Gender(gender_raw)

            student = Student(
                school_id=token["school_id"],
                name=name,
                class_name=class_name,
                roll_number=roll_number,
                father_name=get(row, "father_name") or None,
                mother_name=get(row, "mother_name") or None,
                gender=gender,
                date_of_birth=_parse_date(get(row, "date_of_birth") or get(row, "dob")),
                phone=get(row, "phone") or None,
                email=get(row, "email") or None,
                parent_email=get(row, "parent_email") or None,
                address=get(row, "address") or None,
            )
            db.add(student)
            db.flush()

            # Auto-create parent portal login if parent_email set and new
            if student.parent_email:
                existing_parent = (
                    db.query(User)
                    .filter(
                        User.email == student.parent_email,
                        User.school_id == token["school_id"],
                    )
                    .first()
                )
                if existing_parent:
                    student.parent_user_id = existing_parent.id
                else:
                    parent_user = User(
                        school_id=token["school_id"],
                        username=student.parent_email.split("@")[0],
                        email=student.parent_email,
                        password_hash=hash_password(secrets.token_urlsafe(9)),
                        full_name=f"Parent of {student.name}",
                        role=UserRole.parent,
                        is_active=True,
                    )
                    db.add(parent_user)
                    db.flush()
                    student.parent_user_id = parent_user.id
                    parents_created += 1

            created += 1
        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)[:120]}")
            skipped += 1

    db.commit()

    return {
        "success": True,
        "created": created,
        "skipped": skipped,
        "parents_created": parents_created,
        "errors": errors[:25],  # cap response size
    }