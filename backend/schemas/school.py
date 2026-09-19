from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


# ---------- School Profile ----------

class SchoolProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    principal_name: Optional[str] = None


class SchoolProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None


# ---------- Background Image ----------

class BackgroundImageResponse(BaseModel):
    url: Optional[str] = None
    enabled: bool = False
    has_image: bool = False
    overlay: int = 82


class BackgroundOverlayUpdate(BaseModel):
    """Payload for POST /settings/background-image/overlay"""
    overlay: int = Field(..., ge=40, le=95, description="Overlay intensity, 40-95")


# ---------- Fees Settings ----------

class FeeStructureItem(BaseModel):
    class_name: str
    amount: float


class FeesSettingsResponse(BaseModel):
    fee_due_day: Optional[int] = None
    fee_structure: list[FeeStructureItem] = []


class FeesSettingsUpdate(BaseModel):
    fee_due_day: Optional[int] = None
    fee_structure: Optional[str] = None  # "1:1500\n2:1800" format


# ---------- Parent Portal Settings ----------

class ParentPortalSettingsResponse(BaseModel):
    parent_portal_enabled: bool = True
    parent_show_attendance: bool = True
    parent_show_grades: bool = True
    parent_show_fees: bool = True
    parent_show_documents: bool = False
    parent_allow_messages: bool = True
    payment_info: Optional[str] = None


class ParentPortalSettingsUpdate(BaseModel):
    parent_portal_enabled: Optional[bool] = None
    parent_show_attendance: Optional[bool] = None
    parent_show_grades: Optional[bool] = None
    parent_show_fees: Optional[bool] = None
    parent_show_documents: Optional[bool] = None
    parent_allow_messages: Optional[bool] = None
    payment_info: Optional[str] = None