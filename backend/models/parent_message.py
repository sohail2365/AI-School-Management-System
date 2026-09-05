from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class ParentMessage(Base):
    """
    A single message in a parent<->teacher/admin thread about one student.
    Deliberately simple — one flat table per student's conversation, no
    read-receipts or attachments. Polled on page load, not real-time
    (no websocket infra needed for a school-scale message volume).
    """

    __tablename__ = "parent_messages"

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

    sender_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # "parent" or "staff" (admin/teacher) — lets the UI align bubbles
    # left/right without an extra join back to Users on every render.
    sender_role: Mapped[str] = mapped_column(Text, nullable=False)

    message: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
