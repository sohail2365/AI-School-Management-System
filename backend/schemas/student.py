from datetime import date, datetime
import json
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional


# =========================
# BASE SCHEMA
# =========================
class StudentBase(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    roll_number: str = Field(min_length=1, max_length=50)
    class_name: str = Field(min_length=1, max_length=20)

    date_of_birth: Optional[date] = None
    gender: Optional[str] = None

    father_name: Optional[str] = Field(default=None, max_length=150)
    mother_name: Optional[str] = Field(default=None, max_length=150)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=20)
    address: Optional[str] = None
    parent_email: Optional[EmailStr] = None

    # ✅ NEW FIELDS
    admission_date: Optional[date] = None
    b_form_number: Optional[str] = Field(default=None, max_length=50)
    admission_fee: Optional[float] = None
    monthly_fee_override: Optional[float] = None

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v):
        if v and v > date.today():
            raise ValueError("DOB cannot be a future date")
        return v

    @field_validator("admission_date")
    @classmethod
    def validate_admission_date(cls, v):
        if v and v > date.today():
            raise ValueError("Admission date cannot be in the future")
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        if v is None:
            return None
        v = str(v).strip().lower()
        if v in ["male", "female", "other"]:
            return v
        return None


# =========================
# CREATE SCHEMA
# =========================
class StudentCreate(StudentBase):
    custom_fields_data: Optional[dict] = None


# =========================
# UPDATE SCHEMA
# =========================
class StudentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    roll_number: Optional[str] = Field(default=None, min_length=1, max_length=50)
    class_name: Optional[str] = Field(default=None, min_length=1, max_length=20)

    date_of_birth: Optional[date] = None
    gender: Optional[str] = None

    father_name: Optional[str] = Field(default=None, max_length=150)
    mother_name: Optional[str] = Field(default=None, max_length=150)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=20)
    address: Optional[str] = None
    parent_email: Optional[EmailStr] = None

    # ✅ NEW FIELDS
    admission_date: Optional[date] = None
    b_form_number: Optional[str] = Field(default=None, max_length=50)
    admission_fee: Optional[float] = None
    monthly_fee_override: Optional[float] = None
    custom_fields_data: Optional[dict] = None

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        if v is None:
            return None
        v = str(v).strip().lower()
        if v in ["male", "female", "other"]:
            return v
        return None


# =========================
# RESPONSE SCHEMA
# =========================
class StudentOut(StudentBase):
    id: int
    school_id: int
    user_id: Optional[int] = None
    parent_user_id: Optional[int] = None
    photo_url: Optional[str] = None

    # ✅ NEW FIELDS
    custom_fields_data: Optional[dict] = None

    created_at: datetime
    updated_at: datetime

    @field_validator("custom_fields_data", mode="before")
    @classmethod
    def parse_custom_fields(cls, v):
        """Convert JSON string from DB into dict for frontend."""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return None
        return None

    class Config:
        from_attributes = True


class StudentCreateResponse(StudentOut):
    parent_temp_password: Optional[str] = None