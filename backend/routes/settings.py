# backend/routes/settings.py

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.school import School
from backend.schemas.settings import (
    ClassesUpdate,
    FeeSettingsUpdate,
    HolidaysUpdate,
    ParentPortalSettingsResponse,
    ParentPortalSettingsUpdate,
    SchoolSettingsResponse,
    SchoolSettingsUpdate,
)
from backend.utils.rbac import require_roles
from backend.utils.storage import get_signed_url, upload_school_file

router = APIRouter(prefix="/settings", tags=["settings"])


def _get_school_or_404(db: Session, school_id: int) -> School:
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return school


# =============== SCHOOL SETTINGS ===============

@router.get("/school", response_model=SchoolSettingsResponse)
def get_school_settings(
    token: dict = Depends(require_roles(["admin", "teacher", "parent", "staff", "student"])),
    db: Session = Depends(get_db),
):
    """Get school settings for the current user's school."""
    return _get_school_or_404(db, token["school_id"])


@router.put("/school", response_model=SchoolSettingsResponse)
def update_school_settings(
    payload: SchoolSettingsUpdate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Update school settings (Admin only)."""
    school = _get_school_or_404(db, token["school_id"])

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(school, field, value)

    db.commit()
    db.refresh(school)
    return school


# =============== CLASSES ===============

@router.get("/classes")
def get_active_classes(
    token: dict = Depends(require_roles(["admin", "teacher", "parent", "staff", "student"])),
    db: Session = Depends(get_db),
):
    """Get list of active classes from school settings."""
    school = _get_school_or_404(db, token["school_id"])

    classes = school.active_classes.split(",") if school.active_classes else []
    classes = [c.strip() for c in classes if c.strip()]

    return {
        "classes": classes,
        "total": len(classes),
        "working_days": school.working_days,
    }


@router.put("/classes")
def update_classes(
    payload: ClassesUpdate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Update active classes list (Admin only)."""
    school = _get_school_or_404(db, token["school_id"])

    school.active_classes = payload.classes
    school.working_days = payload.working_days

    db.commit()
    db.refresh(school)

    return {
        "success": True,
        "message": "Classes updated",
        "classes": school.active_classes,
    }


# =============== FEE SETTINGS ===============

@router.get("/fees")
def get_fee_settings(
    token: dict = Depends(require_roles(["admin", "teacher", "parent", "staff", "student"])),
    db: Session = Depends(get_db),
):
    """Get fee structure and settings."""
    school = _get_school_or_404(db, token["school_id"])

    fee_lines = school.fee_structure.split("\n") if school.fee_structure else []
    fees = []
    for line in fee_lines:
        if ":" in line:
            class_name, amount = line.split(":", 1)
            fees.append({"class": class_name.strip(), "amount": amount.strip()})

    return {
        "fee_structure": fees,
        "fee_due_day": school.fee_due_day,
        "late_fee_percent": school.late_fee_percent,
    }


@router.put("/fees")
def update_fee_settings(
    payload: FeeSettingsUpdate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Update fee structure and settings (Admin only)."""
    school = _get_school_or_404(db, token["school_id"])

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if value is not None:
            setattr(school, field, value)

    db.commit()
    db.refresh(school)

    return {"success": True, "message": "Fee settings updated"}


# =============== HOLIDAYS ===============

@router.get("/holidays")
def get_holidays(
    token: dict = Depends(require_roles(["admin", "teacher", "parent", "staff", "student"])),
    db: Session = Depends(get_db),
):
    """Get school holidays."""
    school = _get_school_or_404(db, token["school_id"])

    holiday_lines = school.holidays.split("\n") if school.holidays else []
    holidays = []
    for line in holiday_lines:
        if " (" in line:
            holiday_date, reason = line.split(" (", 1)
            holidays.append({"date": holiday_date.strip(), "reason": reason.rstrip(")").strip()})

    return {"holidays": holidays, "total": len(holidays)}


@router.put("/holidays")
def update_holidays(
    payload: HolidaysUpdate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Update school holidays (Admin only)."""
    school = _get_school_or_404(db, token["school_id"])

    school.holidays = payload.holidays

    db.commit()
    db.refresh(school)

    return {"success": True, "message": "Holidays updated"}


# =============== ROLE-BASED ACCESS ===============

@router.get("/user-role")
def get_user_role(
    token: dict = Depends(require_roles(["admin", "teacher", "parent", "staff", "student"])),
):
    """Get current user's role and permissions."""
    role_permissions = {
        "admin": ["view-all", "edit-all", "delete-all", "export", "settings", "reports", "manage-users"],
        "teacher": ["view-own-class", "mark-attendance", "enter-grades", "message-parents", "view-reports"],
        "parent": ["view-own-child", "message-teacher", "pay-fees"],
        "staff": ["view-basic", "data-entry"],
        "student": ["view-own-profile"],
    }

    role = token.get("role", "staff")
    permissions = role_permissions.get(role, [])

    return {
        "user_id": token.get("user_id"),
        "role": role,
        "school_id": token.get("school_id"),
        "permissions": permissions,
    }


# ==================== PARENT PORTAL SETTINGS ====================

@router.get("/parent-portal", response_model=ParentPortalSettingsResponse)
def get_parent_portal_settings(
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    school = db.query(School).filter(School.id == token["school_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return school


@router.put("/parent-portal", response_model=ParentPortalSettingsResponse)
def update_parent_portal_settings(
    payload: ParentPortalSettingsUpdate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    school = db.query(School).filter(School.id == token["school_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(school, key, value)

    db.commit()
    db.refresh(school)
    return school


# ==================== BACKGROUND IMAGE (portal-wide) ====================

@router.post("/background-image")
def upload_background_image(
    file: UploadFile = File(...),
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    school = db.query(School).filter(School.id == token["school_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    path = upload_school_file(file, token["school_id"], subfolder="background")
    school.background_image_url = path
    db.commit()

    return {"message": "Background image updated.", "url": get_signed_url(path, expires_in=3600)}


@router.delete("/background-image")
def remove_background_image(
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    school = db.query(School).filter(School.id == token["school_id"]).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    school.background_image_url = None
    db.commit()
    return {"message": "Background image removed."}


@router.get("/background-image")
def get_background_image(
    token: dict = Depends(require_roles(["admin", "teacher", "parent"])),
    db: Session = Depends(get_db),
):
    """
    Returns a signed URL for the school's background image, or null if none
    is set. Callers should cache this for the session — it's called once per
    portal page load, and the signed URL is valid for an hour.
    """
    school = db.query(School).filter(School.id == token["school_id"]).first()
    if not school or not school.background_image_url:
        return {"url": None}
    return {"url": get_signed_url(school.background_image_url, expires_in=3600)}