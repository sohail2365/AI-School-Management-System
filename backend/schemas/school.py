from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional


# ==================== AUTH — REGISTER ====================

class SchoolRegisterRequest(BaseModel):
    """Payload for POST /auth/register — creates a new school + admin user."""
    school_name: str
    email: EmailStr
    password: str = Field(..., min_length=8)
    admin_name: str
    phone: Optional[str] = None
    city: Optional[str] = None


# ==================== SCHOOL CREATE (super-admin route) ====================

class SchoolCreate(BaseModel):
    """Payload for POST /schools — creates a bare school record (no admin user)."""
    name: str = Field(..., min_length=2, max_length=150)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=20)
    city: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = None
    principal_name: Optional[str] = Field(default=None, max_length=100)


# ==================== SCHOOL PROFILE ====================

class SchoolProfileOut(BaseModel):
    """School profile returned to clients (from /schools/profile, etc.)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    principal_name: Optional[str] = None


class SchoolProfileUpdate(BaseModel):
    """Payload for PUT /settings/school (partial update)."""
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None