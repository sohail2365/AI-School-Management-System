from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.announcement import Announcement
from backend.utils.rbac import require_roles

router = APIRouter(prefix="/announcements", tags=["announcements"])


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    audience: str = Field(default="both")  # teachers | parents | both


class AnnouncementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None
    audience: str | None = None


def _validate_audience(audience: str) -> str:
    if audience not in ("teachers", "parents", "both"):
        raise HTTPException(status_code=422, detail="Audience must be: teachers, parents, or both")
    return audience


def _announcement_dict(a: Announcement) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "content": a.content,
        "audience": getattr(a, "audience", "both") or "both",
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# ==================== LIST (admin) ====================
@router.get("")
def list_announcements(
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Announcement)
        .filter(Announcement.school_id == token["school_id"])
        .order_by(Announcement.created_at.desc())
        .all()
    )
    return [_announcement_dict(a) for a in rows]


# ==================== CREATE (admin) ====================
@router.post("", status_code=status.HTTP_201_CREATED)
def create_announcement(
    payload: AnnouncementCreate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    audience = _validate_audience(payload.audience)
    a = Announcement(
        school_id=token["school_id"],
        title=payload.title,
        content=payload.content,
        audience=audience,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _announcement_dict(a)


# ==================== UPDATE (admin) ====================
@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: int,
    payload: AnnouncementUpdate,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    a = (
        db.query(Announcement)
        .filter(Announcement.id == announcement_id, Announcement.school_id == token["school_id"])
        .first()
    )
    if not a:
        raise HTTPException(status_code=404, detail="Announcement not found")

    data = payload.model_dump(exclude_unset=True)
    if "audience" in data and data["audience"]:
        data["audience"] = _validate_audience(data["audience"])
    for k, v in data.items():
        setattr(a, k, v)

    db.commit()
    db.refresh(a)
    return _announcement_dict(a)


# ==================== DELETE (admin) ====================
@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_announcement(
    announcement_id: int,
    token: dict = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    a = (
        db.query(Announcement)
        .filter(Announcement.id == announcement_id, Announcement.school_id == token["school_id"])
        .first()
    )
    if not a:
        raise HTTPException(status_code=404, detail="Announcement not found")
    db.delete(a)
    db.commit()
    return None


# ==================== TEACHER VIEW ====================
@router.get("/teacher/list")
def list_announcements_for_teacher(
    token: dict = Depends(require_roles(["teacher", "admin"])),
    db: Session = Depends(get_db),
):
    """Teacher sees only announcements targeted to teachers or 'both'."""
    rows = (
        db.query(Announcement)
        .filter(
            Announcement.school_id == token["school_id"],
            Announcement.audience.in_(["teachers", "both"]),
        )
        .order_by(Announcement.created_at.desc())
        .all()
    )
    return [_announcement_dict(a) for a in rows]


# ==================== PARENT VIEW ====================
@router.get("/parent/list")
def list_announcements_for_parent(
    token: dict = Depends(require_roles(["parent", "admin"])),
    db: Session = Depends(get_db),
):
    """Parent sees only announcements targeted to parents or 'both'."""
    rows = (
        db.query(Announcement)
        .filter(
            Announcement.school_id == token["school_id"],
            Announcement.audience.in_(["parents", "both"]),
        )
        .order_by(Announcement.created_at.desc())
        .all()
    )
    return [_announcement_dict(a) for a in rows]