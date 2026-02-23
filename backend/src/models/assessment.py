import uuid

from sqlalchemy import ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base, BaseMixin


class Assessment(BaseMixin, Base):
    __tablename__ = "assessments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    level_before: Mapped[int | None] = mapped_column(SmallInteger)
    level_after: Mapped[int | None] = mapped_column(SmallInteger)
    scores: Mapped[dict | None] = mapped_column(JSONB)
    feedback: Mapped[str | None] = mapped_column(Text)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id"),
    )
