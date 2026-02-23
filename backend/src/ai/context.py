import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.src.ai.prompts.base import SYSTEM_PROMPT_TEMPLATE
from backend.src.ai.prompts.levels import build_goals_context, get_level_config
from backend.src.models.conversation import Conversation, Message
from backend.src.models.user import User, UserErrorPattern
from backend.src.utils.tokens import count_tokens, truncate_messages

logger = structlog.get_logger()


@dataclass
class AssembledContext:
    user_profile: str
    conversation_history: list[dict] = field(default_factory=list)
    memory_summaries: list[str] = field(default_factory=list)
    total_tokens: int = 0

    def to_system_prompt(self, level: int, goals: list[str], target_stack: list[str], target_company: str) -> str:
        level_config = get_level_config(level)
        goals_context = build_goals_context(goals, target_stack, target_company)
        summaries_text = "\n".join(self.memory_summaries) if self.memory_summaries else "No previous sessions."

        return SYSTEM_PROMPT_TEMPLATE.format(
            user_profile=self.user_profile,
            level_instructions=level_config.instructions,
            goals_context=goals_context,
            memory_summaries=summaries_text,
        )

    def to_messages(self) -> list[dict]:
        return list(self.conversation_history)


class ContextProvider(ABC):
    @abstractmethod
    async def assemble(
        self,
        user_id: uuid.UUID,
        current_message: str,
        max_tokens: int = 4000,
    ) -> AssembledContext: ...


class SQLContextProvider(ContextProvider):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def assemble(
        self,
        user_id: uuid.UUID,
        current_message: str,
        max_tokens: int = 4000,
    ) -> AssembledContext:
        async with self._session_factory() as session:
            # Layer 1: User profile (~300 tokens)
            user_profile = await self._build_user_profile(session, user_id)
            profile_tokens = count_tokens(user_profile)

            # Layer 3: Memory summaries (~500-1K tokens) — fetch before Layer 2 to calculate budget
            summaries = await self._build_memory_summaries(session, user_id)
            summaries_text = "\n".join(summaries) if summaries else ""
            summaries_tokens = count_tokens(summaries_text) if summaries_text else 0

            # Layer 2: Conversation history — gets remaining budget
            history_budget = max_tokens - profile_tokens - summaries_tokens - 200  # 200 token buffer
            history_budget = max(history_budget, 500)  # minimum budget
            history = await self._build_conversation_history(session, user_id, history_budget)

            history_tokens = sum(count_tokens(m.get("content", "")) for m in history)
            total = profile_tokens + history_tokens + summaries_tokens

            return AssembledContext(
                user_profile=user_profile,
                conversation_history=history,
                memory_summaries=summaries,
                total_tokens=total,
            )

    async def _build_user_profile(self, session: AsyncSession, user_id: uuid.UUID) -> str:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return "Unknown user."

        parts = [
            f"Name: {user.name or 'Unknown'}",
            f"Level: {user.current_level}/4 ({user.cefr_estimate or 'unassessed'})",
        ]

        if user.tech_role:
            parts.append(f"Role: {user.tech_role}")
        if user.tech_stack:
            parts.append(f"Tech stack: {', '.join(user.tech_stack)}")
        if user.goals:
            parts.append(f"Goals: {', '.join(user.goals)}")
        if user.target_stack:
            parts.append(f"Target stack: {', '.join(user.target_stack)}")
        if user.target_company:
            parts.append(f"Target company: {user.target_company}")

        # Top 5 error patterns
        error_result = await session.execute(
            select(UserErrorPattern)
            .where(UserErrorPattern.user_id == user_id)
            .order_by(UserErrorPattern.occurrence_count.desc())
            .limit(5)
        )
        errors = error_result.scalars().all()
        if errors:
            error_lines = [
                f"- {e.error_type}: {e.error_detail} ({e.occurrence_count}x)"
                for e in errors
            ]
            parts.append(f"Recurring errors:\n" + "\n".join(error_lines))

        return "\n".join(parts)

    async def _build_conversation_history(
        self, session: AsyncSession, user_id: uuid.UUID, max_tokens: int
    ) -> list[dict]:
        # Find active conversation (no ended_at)
        conv_result = await session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.ended_at.is_(None))
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        conversation = conv_result.scalar_one_or_none()
        if conversation is None:
            return []

        # Get last 15 messages
        msg_result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(15)
        )
        messages = list(reversed(msg_result.scalars().all()))

        history = [
            {"role": m.role, "content": m.content_text or m.transcription or ""}
            for m in messages
            if m.content_text or m.transcription
        ]

        return truncate_messages(history, max_tokens)

    async def _build_memory_summaries(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[str]:
        result = await session.execute(
            select(Conversation.summary)
            .where(
                Conversation.user_id == user_id,
                Conversation.summary.isnot(None),
            )
            .order_by(Conversation.created_at.desc())
            .limit(5)
        )
        rows = result.scalars().all()
        return [s for s in rows if s]
