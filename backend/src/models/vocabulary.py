import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base, BaseMixin


class UserVocabulary(BaseMixin, Base):
    __tablename__ = "user_vocabulary"
    __table_args__ = (
        UniqueConstraint("user_id", "word"),
        Index("ix_user_vocabulary_review", "user_id", "next_review"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    word: Mapped[str] = mapped_column(String(255), nullable=False)
    context: Mapped[str | None] = mapped_column(Text)
    level_learned: Mapped[int | None] = mapped_column(SmallInteger)
    times_seen: Mapped[int] = mapped_column(Integer, default=1)
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    next_review: Mapped[datetime | None] = mapped_column()
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
