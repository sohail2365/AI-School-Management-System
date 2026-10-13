from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator


VALID_FEE_TYPES = {"monthly", "admission", "additional", "other"}


class FeeCreate(BaseModel):
    student_id: int = Field(gt=0)
    fee_name: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    due_date: date | None = None
    month: str | None = Field(default=None, max_length=20)
    fee_type: str = Field(default="monthly", max_length=20)

    @field_validator("fee_type")
    @classmethod
    def validate_fee_type(cls, v):
        if v not in VALID_FEE_TYPES:
            raise ValueError(f"fee_type must be one of {sorted(VALID_FEE_TYPES)}")
        return v


class FeeUpdate(BaseModel):
    fee_name: str | None = Field(default=None, min_length=1, max_length=100)
    amount: float | None = Field(default=None, gt=0)
    due_date: date | None = None
    month: str | None = Field(default=None, max_length=20)
    fee_type: str | None = Field(default=None, max_length=20)


class FeeOut(BaseModel):
    id: int
    school_id: int
    student_id: int
    fee_name: str | None = None
    amount: float
    due_date: date | None = None
    paid_amount: float
    due_amount: float
    month: str | None = None
    fee_type: str = "monthly"
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FifoPaymentRequest(BaseModel):
    amount: float = Field(gt=0)
    payment_method: str = Field(default="cash", max_length=30)
    payment_date: date | None = None
    receipt_number: str | None = Field(default=None, max_length=50)