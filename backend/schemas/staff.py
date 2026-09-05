from datetime import date, datetime
from pydantic import BaseModel, Field


class StaffCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    designation: str = Field(min_length=2, max_length=100)
    role: str | None = Field(default="teacher", max_length=20)
    email: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    subject: str | None = Field(default=None, max_length=100)
    class_assigned: str | None = Field(default=None, max_length=20)
    salary: float = Field(ge=0, default=0.0)
    joining_date: date | None = None
    address: str | None = None


class StaffUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    designation: str | None = Field(default=None, min_length=2, max_length=100)
    role: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    subject: str | None = Field(default=None, max_length=100)
    class_assigned: str | None = Field(default=None, max_length=20)
    salary: float | None = Field(default=None, ge=0)
    joining_date: date | None = None
    address: str | None = None
    status: str | None = None


class StaffOut(BaseModel):
    id: int
    school_id: int
    user_id: int | None = None
    login_active: bool | None = None
    name: str
    designation: str
    role: str
    email: str | None = None
    phone: str | None = None
    subject: str | None = None
    class_assigned: str | None = None
    salary: float
    joining_date: date | None = None
    address: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StaffAttendanceCreate(BaseModel):
    staff_id: int = Field(gt=0)
    date: date
    is_present: bool = True
    remarks: str | None = Field(default=None, max_length=255)


class StaffAttendanceUpdate(BaseModel):
    is_present: bool | None = None
    remarks: str | None = Field(default=None, max_length=255)


class StaffAttendanceOut(BaseModel):
    id: int
    school_id: int
    staff_id: int
    date: date
    is_present: bool
    remarks: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StaffSalaryPaymentCreate(BaseModel):
    staff_id: int = Field(gt=0)
    month: str = Field(min_length=2, max_length=20)
    amount_paid: float = Field(gt=0)
    payment_date: date | None = None
    payment_method: str | None = Field(default=None, max_length=50)


class StaffSalaryPaymentOut(BaseModel):
    id: int
    school_id: int
    staff_id: int
    month: str
    amount_paid: float
    payment_date: date
    payment_method: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True