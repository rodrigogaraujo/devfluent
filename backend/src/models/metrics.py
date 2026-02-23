import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base, BaseMixin


class WeeklyMetrics(BaseMixin, Base):
    __tablename__ = "weekly_metrics"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    minutes_practiced: Mapped[int] = mapped_column(Integer, default=0)
    messages_sent: Mapped[int] = mapped_column(Integer, default=0)
    audio_messages: Mapped[int] = mapped_column(Integer, default=0)
    new_words: Mapped[int] = mapped_column(Integer, default=0)
    errors_grammar: Mapped[int] = mapped_column(Integer, default=0)
    errors_pronunciation: Mapped[int] = mapped_column(Integer, default=0)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0)
