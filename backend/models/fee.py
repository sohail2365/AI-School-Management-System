from datetime import date, datetime
import enum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy import Date as SqlDate
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class FeeStatus(str, enum.Enum):
    pending = "pending"
    partial = "partial"
    paid = "paid"


class Fee(Base):
    __tablename__ = "fees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    fee_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    due_date: Mapped[date | None] = mapped_column(SqlDate, nullable=True)
    month: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ✅ NEW: "monthly" | "admission" | "additional" | "other"
    fee_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="monthly",
        server_default="monthly",
    )

    paid_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    due_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    status: Mapped[FeeStatus] = mapped_column(
        Enum(FeeStatus, validate_strings=True),
        nullable=False,
        default=FeeStatus.pending,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )