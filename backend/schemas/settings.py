from pydantic import BaseModel, Field


class SchoolSettingsUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = None
    principal_name: str | None = Field(default=None, max_length=100)
    active_classes: str | None = None  # "KG,Class 1,Class 2,..."
    working_days: int | None = Field(default=None, ge=1, le=7)
    fee_structure: str | None = None
    fee_due_day: int | None = Field(default=None, ge=1, le=31)
    late_fee_percent: int | None = Field(default=None, ge=0, le=100)
    holidays: str | None = None


class SchoolSettingsResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str | None = None
    address: str | None = None
    principal_name: str | None = None
    active_classes: str | None = None
    working_days: int
    fee_structure: str | None = None
    fee_due_day: int
    late_fee_percent: int
    holidays: str | None = None

    class Config:
        from_attributes = True


class ClassesUpdate(BaseModel):
    classes: str = Field(default="", description="Comma-separated list of class names")
    working_days: int = Field(default=5, ge=1, le=7)


class FeeSettingsUpdate(BaseModel):
    fee_structure: str | None = None
    fee_due_day: int | None = Field(default=None, ge=1, le=31)
    late_fee_percent: int | None = Field(default=None, ge=0, le=100)


class HolidaysUpdate(BaseModel):
    holidays: str = Field(default="", description='Newline-separated "YYYY-MM-DD (Reason)" entries')


class ParentPortalSettingsUpdate(BaseModel):
    parent_portal_enabled: bool | None = None
    parent_show_attendance: bool | None = None
    parent_show_grades: bool | None = None
    parent_show_fees: bool | None = None
    parent_show_documents: bool | None = None
    parent_allow_messages: bool | None = None
    payment_info: str | None = None


class ParentPortalSettingsResponse(BaseModel):
    parent_portal_enabled: bool
    parent_show_attendance: bool
    parent_show_grades: bool
    parent_show_fees: bool
    parent_show_documents: bool
    parent_allow_messages: bool
    payment_info: str | None = None

    class Config:
        from_attributes = True