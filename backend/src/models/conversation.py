import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base, BaseMixin


class Conversation(BaseMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_recent", "user_id", "created_at"),
        Index(
            "ix_conversations_user_summaries",
            "user_id",
            postgresql_where="summary IS NOT NULL",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(String(30), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(255))
    level_at_time: Mapped[int | None] = mapped_column(SmallInteger)
    started_at: Mapped[datetime] = mapped_column(
        server_default="now()",
    )
    ended_at: Mapped[datetime | None] = mapped_column()
    summary: Mapped[str | None] = mapped_column(Text)
    errors_found: Mapped[dict | None] = mapped_column(JSONB)
    new_vocab: Mapped[dict | None] = mapped_column(JSONB)


class Message(BaseMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_asc", "conversation_id", "created_at"),
        Index("ix_messages_conversation_desc", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text)
    content_audio: Mapped[str | None] = mapped_column(String(500))
    transcription: Mapped[str | None] = mapped_column(Text)
    corrections: Mapped[dict | None] = mapped_column(JSONB)
    pronunciation: Mapped[dict | None] = mapped_column(JSONB)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
