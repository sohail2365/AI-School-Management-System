from datetime import date, datetime
import enum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Column, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base

class Gender(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("school_id", "class_name", "roll_number", name="uq_students_school_class_roll"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    roll_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    class_name: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(
        Enum(Gender, validate_strings=True),
        nullable=True
    )

    father_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    mother_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # Parent Portal linkage. Adding a parent_email here (via student create/
    # update) auto-provisions a portal login for that parent — see
    # backend/routes/students.py's _auto_create_parent_login helper.
    parent_email: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    parent_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Profile/ID-card photo shown on the printable student card. This is
    # separate from StudentDocument (which holds the full B-form/ID-card/test
    # paper archive) because the card print view needs one canonical photo
    # without querying the documents table every time.
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
