import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.ai.context import ContextProvider
from backend.src.ai.llm import LLMProvider
from backend.src.ai.prompts.levels import get_level_config
from backend.src.config import settings
from backend.src.core.feedback import FeedbackAnalyzer
from backend.src.models.conversation import Conversation, Message
from backend.src.models.user import User

logger = structlog.get_logger()


@dataclass
class ConversationResponse:
    text: str
    audio_bytes: bytes | None = None
    corrections: list[dict] = field(default_factory=list)
    new_vocab: list[dict] = field(default_factory=list)
    tokens_used: int = 0


class ConversationEngine:
    def __init__(
        self,
        db: AsyncSession | None,
        llm: LLMProvider,
        context_provider: ContextProvider,
        feedback_analyzer: FeedbackAnalyzer,
        tts: object | None = None,
    ):
        self._db = db
        self._llm = llm
        self._context_provider = context_provider
        self._feedback = feedback_analyzer
        self._tts = tts

    async def process_message(
        self,
        user: User,
        text: str,
        is_audio: bool = False,
        audio_transcription: str | None = None,
    ) -> ConversationResponse:
        db = self._db

        # 1. Find or create conversation
        conversation = await self._get_or_create_conversation(db, user)

        # 2. Save user message
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content_text=text,
            transcription=audio_transcription,
        )
        db.add(user_message)
        await db.flush()

        # 3. Assemble context
        assembled = await self._context_provider.assemble(
            user_id=user.id,
            current_message=text,
            max_tokens=settings.MAX_CONTEXT_TOKENS,
        )

        # 4. Build system prompt
        system_prompt = assembled.to_system_prompt(
            level=user.current_level,
            goals=user.goals or [],
            target_stack=user.target_stack or [],
            target_company=user.target_company or "",
        )

        # 5. Build messages for LLM (history + current)
        messages = assembled.to_messages()
        messages.append({"role": "user", "content": text})

        # 6. Call LLM
        level_config = get_level_config(user.current_level)
        response = await self._llm.chat(
            system_prompt=system_prompt,
            messages=messages,
            temperature=0.7,
            max_tokens=800,
        )

        # 7. Extract feedback (corrections + vocab)
        feedback = await self._feedback.extract(response.content, text)

        # 8. Save assistant message
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content_text=response.content,
            corrections=feedback.corrections if feedback.corrections else None,
            tokens_used=response.input_tokens + response.output_tokens,
        )
        db.add(assistant_message)

        # 9. Update error patterns if corrections found
        if feedback.corrections:
            await FeedbackAnalyzer.update_error_patterns(
                db, user.id, feedback.corrections
            )

        # 10. Generate TTS audio if voice message and TTS available
        audio_bytes = None
        if is_audio and self._tts is not None:
            try:
                audio_bytes = await self._tts.synthesize(
                    response.content,
                    speed=level_config.tts_speed,
                )
            except Exception:
                logger.warning("tts_synthesis_failed", user_id=str(user.id))

        return ConversationResponse(
            text=response.content,
            audio_bytes=audio_bytes,
            corrections=feedback.corrections,
            new_vocab=feedback.new_vocab,
            tokens_used=response.input_tokens + response.output_tokens,
        )

    async def end_conversation(self, conversation_id: uuid.UUID) -> uuid.UUID:
        db = self._db
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation:
            conversation.ended_at = datetime.utcnow()
        return conversation_id

    async def _get_or_create_conversation(
        self, db: AsyncSession, user: User
    ) -> Conversation:
        # Find latest active conversation
        result = await db.execute(
            select(Conversation)
            .where(
                Conversation.user_id == user.id,
                Conversation.ended_at.is_(None),
                Conversation.mode != "onboarding",
            )
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        conversation = result.scalar_one_or_none()

        if conversation is not None:
            # Check timeout — if last message was > CONVERSATION_TIMEOUT_MIN ago, end it
            last_msg_result = await db.execute(
                select(Message.created_at)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            last_msg_time = last_msg_result.scalar_one_or_none()

            if last_msg_time and (
                datetime.utcnow() - last_msg_time
                > timedelta(minutes=settings.CONVERSATION_TIMEOUT_MIN)
            ):
                conversation.ended_at = datetime.utcnow()
                logger.info(
                    "conversation_auto_ended",
                    conversation_id=str(conversation.id),
                    user_id=str(user.id),
                )
                conversation = None

        if conversation is None:
            conversation = Conversation(
                user_id=user.id,
                mode="free_chat",
                level_at_time=user.current_level,
            )
            db.add(conversation)
            await db.flush()
            logger.info(
                "conversation_created",
                conversation_id=str(conversation.id),
                user_id=str(user.id),
            )

        return conversation
