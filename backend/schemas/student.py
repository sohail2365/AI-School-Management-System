from datetime import date, datetime
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
    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v):
        if v and v > date.today():
            raise ValueError("DOB cannot be a future date")
        return v


    # =========================
    # VALIDATION: GENDER (FIXED BUG)
    # =========================
    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        if v is None:
            return None

        v = str(v).strip().lower()

        if v in ["male", "female", "other"]:
            return v

        # Normalize invalid frontend values like:
        # "Not Specified", "N/A", etc.
        return None


# =========================
# CREATE SCHEMA
# =========================
class StudentCreate(StudentBase):
    pass


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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StudentCreateResponse(StudentOut):
    # Set only when this request just auto-provisioned a NEW parent login
    # (i.e. parent_email was set and no login existed for it yet). The admin
    # must copy this now — it is never retrievable again after this response.
    parent_temp_password: Optional[str] = None