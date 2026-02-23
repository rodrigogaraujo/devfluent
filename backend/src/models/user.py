import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Float, Index, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base, BaseMixin


class User(BaseMixin, Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    current_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    cefr_estimate: Mapped[str | None] = mapped_column(String(2))
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)
    subscription: Mapped[str] = mapped_column(String(20), default="free")
    weekly_goal_min: Mapped[int] = mapped_column(Integer, default=60)
    timezone: Mapped[str] = mapped_column(String(50), default="America/Sao_Paulo")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    # Tech profile
    tech_role: Mapped[str | None] = mapped_column(String(30))
    tech_stack: Mapped[list] = mapped_column(JSONB, default=list)
    goals: Mapped[list] = mapped_column(JSONB, default=list)
    target_stack: Mapped[list] = mapped_column(JSONB, default=list)
    target_company: Mapped[str] = mapped_column(String(30), default="startup")


class UserErrorPattern(BaseMixin, Base):
    __tablename__ = "user_error_patterns"
    __table_args__ = (
        UniqueConstraint("user_id", "error_type", "error_detail"),
        Index("ix_user_error_patterns_top", "user_id", "occurrence_count"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
    )
    error_type: Mapped[str | None] = mapped_column(String(50))
    error_detail: Mapped[str | None] = mapped_column(String(255))
    correction: Mapped[str | None] = mapped_column(Text)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    last_seen: Mapped[datetime] = mapped_column(server_default=func.now())
