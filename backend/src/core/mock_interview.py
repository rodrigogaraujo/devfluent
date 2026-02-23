import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.ai.llm import LLMProvider
from backend.src.ai.prompts.interview import GOAL_TO_INTERVIEW, MOCK_INTERVIEW_PROMPTS
from backend.src.channels.base import MessageChannel
from backend.src.models.conversation import Conversation, Message
from backend.src.models.user import User

logger = structlog.get_logger()


class MockInterviewEngine:
    def __init__(self, db: AsyncSession | None, llm: LLMProvider, channel: MessageChannel):
        self._db = db
        self._llm = llm
        self._channel = channel

    def suggest_interview_type(self, user: User) -> str:
        """Auto-suggest interview type based on user goals."""
        for goal in (user.goals or []):
            interview_type = GOAL_TO_INTERVIEW.get(goal)
            if interview_type:
                return interview_type
        return "hr_behavioral"

    async def start_interview(
        self, user: User, chat_id: str, interview_type: str | None = None
    ) -> Conversation:
        db = self._db
        if interview_type is None:
            interview_type = self.suggest_interview_type(user)

        prompt_template = MOCK_INTERVIEW_PROMPTS.get(interview_type, MOCK_INTERVIEW_PROMPTS["hr_behavioral"])
        system_prompt = prompt_template.format(
            tech_role=user.tech_role or "developer",
            target_stack=", ".join(user.target_stack or []) or "general",
            target_company=user.target_company or "startup",
        )

        # Create interview conversation
        conversation = Conversation(
            user_id=user.id,
            mode="mock_interview",
            topic=f"Mock Interview: {interview_type}",
            level_at_time=user.current_level,
        )
        db.add(conversation)
        await db.flush()

        # Generate opening message
        response = await self._llm.chat(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": "Please start the interview. Introduce yourself and ask the first question."}],
        )

        # Save assistant message
        msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content_text=response.content,
            tokens_used=response.output_tokens,
        )
        db.add(msg)

        await self._channel.send_text(chat_id, response.content)

        logger.info(
            "mock_interview_started",
            user_id=str(user.id),
            interview_type=interview_type,
            conversation_id=str(conversation.id),
        )

        return conversation

    async def process_response(self, user: User, text: str) -> str:
        """Process a response during a mock interview."""
        db = self._db

        # Find active mock interview conversation
        result = await db.execute(
            select(Conversation)
            .where(
                Conversation.user_id == user.id,
                Conversation.mode == "mock_interview",
                Conversation.ended_at.is_(None),
            )
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            return "No active interview session. Start one with /interview."

        # Save user message
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content_text=text,
        )
        db.add(user_msg)

        # Load conversation history
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        )
        messages = msg_result.scalars().all()

        # Build messages for LLM
        interview_type = (conversation.topic or "").replace("Mock Interview: ", "")
        prompt_template = MOCK_INTERVIEW_PROMPTS.get(interview_type, MOCK_INTERVIEW_PROMPTS["hr_behavioral"])
        system_prompt = prompt_template.format(
            tech_role=user.tech_role or "developer",
            target_stack=", ".join(user.target_stack or []) or "general",
            target_company=user.target_company or "startup",
        )

        chat_messages = []
        for m in messages:
            content = m.content_text or m.transcription or ""
            chat_messages.append({"role": m.role, "content": content})

        response = await self._llm.chat(
            system_prompt=system_prompt,
            messages=chat_messages,
        )

        # Save assistant message
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content_text=response.content,
            tokens_used=response.output_tokens,
        )
        db.add(assistant_msg)

        return response.content
