import uuid

from sqlalchemy import Boolean, ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base, BaseMixin


class StudyPlan(BaseMixin, Base):
    __tablename__ = "study_plans"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    week_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    theme: Mapped[str | None] = mapped_column(String(255))
    focus_skills: Mapped[dict | None] = mapped_column(JSONB)
    target_vocab: Mapped[dict | None] = mapped_column(JSONB)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
