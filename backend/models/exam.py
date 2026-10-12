"""
Exam + Datesheet models.
Ek Exam ke andar multiple classes ki datesheet ho sakti hai.
Har class ke liye multiple subject entries.
"""
from datetime import datetime, date
from sqlalchemy import String, Integer, ForeignKey, Date, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base   # ← apne project ka correct import path daalein


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    entries: Mapped[list["ExamEntry"]] = relationship(
        back_populates="exam",
        cascade="all, delete-orphan",
    )


class ExamEntry(Base):
    __tablename__ = "exam_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), index=True
    )
    class_name: Mapped[str] = mapped_column(String(50), index=True)
    subject: Mapped[str] = mapped_column(String(120))
    exam_date: Mapped[date] = mapped_column(Date)
    exam_time: Mapped[str | None] = mapped_column(String(60), nullable=True)  # e.g. "9:00 AM - 11:00 AM"
    day: Mapped[str | None] = mapped_column(String(20), nullable=True)         # e.g. "Monday"
    total_marks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    exam: Mapped["Exam"] = relationship(back_populates="entries")