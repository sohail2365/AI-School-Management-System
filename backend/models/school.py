from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    principal_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Background image (Supabase Storage path) shown across admin/teacher/
    # parent portal pages. Optional — pages fall back to the plain paper
    # background when unset.
    background_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    background_image_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Overlay intensity for portal background (40-95). Higher = more readable
    # text, lower = more visible image. Admin-adjustable via the slider in
    # Settings → Portal Background Image.
    background_overlay: Mapped[int] = mapped_column(Integer, default=82, nullable=False)

    # Platform-level control (used by the super admin panel). A deactivated
    # school can't log in at all, but its data is preserved (not deleted) —
    # use this for suspending a demo/spam signup without losing anything,
    # and reserve hard deletion for genuine cleanup.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Settings
    active_classes: Mapped[str | None] = mapped_column(Text, nullable=True)
    working_days: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Fee settings
    fee_structure: Mapped[str | None] = mapped_column(Text, nullable=True)
    fee_due_day: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    late_fee_percent: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Parent Portal — admin-controlled visibility. Each toggle gates what a
    # parent can see for their own child; default ON (most schools want
    # parents to see this), admin can turn any of them off in Settings.
    parent_portal_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    parent_show_attendance: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    parent_show_grades: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    parent_show_fees: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    parent_show_documents: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parent_allow_messages: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Payment info shown to parents on the Fees screen — informational only
    # (bank/JazzCash/EasyPaisa account details for manual transfer). No
    # payment gateway integration; this is display text, nothing is charged
    # or processed through SchoolHub.
    payment_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Holidays
    holidays: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )