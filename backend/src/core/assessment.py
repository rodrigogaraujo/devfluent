import json
import uuid
from dataclasses import dataclass, field
from enum import Enum

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.ai.llm import LLMProvider
from backend.src.ai.prompts.assessment import (
    CLASSIFICATION_PROMPT,
    GOALS_PROMPT,
    ONBOARDING_COMPLETE_TEMPLATE,
    SPEAKING_ASSESSMENT_PROMPT,
    TARGET_COMPANY_PROMPT,
    TARGET_STACK_PROMPT,
    TECH_ROLE_PROMPT,
    TECH_STACK_PROMPT,
    WELCOME_MESSAGE,
    WRITTEN_ASSESSMENT_PROMPTS,
)
from backend.src.bot.keyboards import (
    build_goals_keyboard,
    build_self_declaration_keyboard,
    build_target_company_keyboard,
    build_target_stack_keyboard,
    build_tech_role_keyboard,
    build_tech_stack_keyboard,
)
from backend.src.channels.base import MessageChannel
from backend.src.models.assessment import Assessment
from backend.src.models.conversation import Conversation, Message
from backend.src.models.study_plan import StudyPlan
from backend.src.models.user import User

logger = structlog.get_logger()


class OnboardingState(str, Enum):
    WELCOME = "welcome"
    SELF_DECLARATION = "self_declaration"
    TECH_ROLE = "tech_role"
    TECH_STACK = "tech_stack"
    GOALS = "goals"
    TARGET_STACK = "target_stack"
    TARGET_COMPANY = "target_company"
    WRITTEN_1 = "written_1"
    WRITTEN_2 = "written_2"
    WRITTEN_3 = "written_3"
    SPEAKING = "speaking"
    CLASSIFYING = "classifying"
    DONE = "done"


@dataclass
class AssessmentResult:
    level: int
    cefr: str
    confidence: float
    strengths: list[str]
    weaknesses: list[str]
    feedback: str
    suggested_focus: str


@dataclass
class OnboardingData:
    state: str = OnboardingState.WELCOME.value
    conversation_id: str = ""
    self_declaration: str = ""
    tech_role: str = ""
    tech_stack: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    target_stack: list[str] = field(default_factory=list)
    target_company: str = ""
    responses: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps({
            "state": self.state,
            "conversation_id": self.conversation_id,
            "self_declaration": self.self_declaration,
            "tech_role": self.tech_role,
            "tech_stack": self.tech_stack,
            "goals": self.goals,
            "target_stack": self.target_stack,
            "target_company": self.target_company,
            "responses": self.responses,
        })

    @classmethod
    def from_json(cls, data: str) -> "OnboardingData":
        d = json.loads(data)
        return cls(**d)


REDIS_TTL = 3600  # 1 hour


class AssessmentEngine:
    def __init__(
        self,
        db: AsyncSession,
        llm: LLMProvider,
        channel: MessageChannel,
        redis_client: object | None = None,
        tts: object | None = None,
    ):
        self._db = db
        self._llm = llm
        self._channel = channel
        self._redis = redis_client
        self._tts = tts

    async def _send_voice_prompt(self, chat_id: str, text: str) -> None:
        """Send a prompt as voice audio + text fallback."""
        if self._tts is not None:
            try:
                audio = await self._tts.synthesize(text, speed=0.9)
                await self._channel.send_audio(chat_id, audio, caption=text)
                return
            except Exception:
                logger.warning("assessment_tts_failed")
        await self._channel.send_text(chat_id, text)

    def _redis_key(self, user_id: uuid.UUID) -> str:
        return f"assessment:{user_id}"

    async def _get_state(self, user_id: uuid.UUID) -> OnboardingData | None:
        if self._redis is None:
            return None
        try:
            data = await self._redis.get(self._redis_key(user_id))
            if data:
                return OnboardingData.from_json(data)
        except Exception:
            logger.warning("assessment_redis_get_error", user_id=str(user_id))
        return None

    async def _save_state(self, user_id: uuid.UUID, data: OnboardingData) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(
                self._redis_key(user_id), data.to_json(), ex=REDIS_TTL
            )
        except Exception:
            logger.warning("assessment_redis_set_error", user_id=str(user_id))

    async def _clear_state(self, user_id: uuid.UUID) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.delete(self._redis_key(user_id))
        except Exception:
            pass

    async def start_onboarding(self, user: User, chat_id: str) -> None:
        conversation = Conversation(
            user_id=user.id,
            mode="onboarding",
            level_at_time=user.current_level,
        )
        self._db.add(conversation)
        await self._db.flush()

        data = OnboardingData(
            state=OnboardingState.SELF_DECLARATION.value,
            conversation_id=str(conversation.id),
        )
        await self._save_state(user.id, data)

        await self._channel.send_text(chat_id, WELCOME_MESSAGE)
        from backend.src.ai.prompts.assessment import SELF_DECLARATION_PROMPT

        keyboard = build_self_declaration_keyboard()
        await self._channel.send_keyboard(
            chat_id, SELF_DECLARATION_PROMPT, keyboard=keyboard
        )

    async def process_callback(
        self, user: User, chat_id: str, callback_data: str, message_id: int | None = None
    ) -> None:
        data = await self._get_state(user.id)
        if data is None:
            await self._channel.send_text(
                chat_id,
                "Your onboarding session expired. Please send /start to begin again.",
            )
            return

        state = data.state

        if callback_data.startswith("self_declaration:"):
            if state != OnboardingState.SELF_DECLARATION.value:
                return
            value = callback_data.split(":", 1)[1]
            data.self_declaration = value
            data.state = OnboardingState.TECH_ROLE.value
            await self._save_state(user.id, data)
            keyboard = build_tech_role_keyboard()
            await self._channel.send_keyboard(chat_id, TECH_ROLE_PROMPT, keyboard=keyboard)

        elif callback_data.startswith("tech_role:"):
            if state != OnboardingState.TECH_ROLE.value:
                return
            value = callback_data.split(":", 1)[1]
            data.tech_role = value
            data.state = OnboardingState.TECH_STACK.value
            await self._save_state(user.id, data)
            keyboard = build_tech_stack_keyboard(set())
            await self._channel.send_keyboard(chat_id, TECH_STACK_PROMPT, keyboard=keyboard)

        elif callback_data.startswith("toggle:"):
            parts = callback_data.split(":", 2)
            if len(parts) < 3:
                return
            category = parts[1]
            value = parts[2]
            await self._handle_toggle(user, chat_id, data, category, value, message_id)

        elif callback_data.startswith("confirm:"):
            category = callback_data.split(":", 1)[1]
            await self._handle_confirm(user, chat_id, data, category)

        elif callback_data.startswith("target_company:"):
            if state != OnboardingState.TARGET_COMPANY.value:
                return
            value = callback_data.split(":", 1)[1]
            data.target_company = value
            await self._advance_to_written(user, chat_id, data)

    async def _handle_toggle(
        self,
        user: User,
        chat_id: str,
        data: OnboardingData,
        category: str,
        value: str,
        message_id: int | None = None,
    ) -> None:
        if category == "tech_stack":
            if value in data.tech_stack:
                data.tech_stack.remove(value)
            else:
                data.tech_stack.append(value)
            await self._save_state(user.id, data)
            keyboard = build_tech_stack_keyboard(set(data.tech_stack))

        elif category == "goals":
            if value in data.goals:
                data.goals.remove(value)
            else:
                data.goals.append(value)
            await self._save_state(user.id, data)
            keyboard = build_goals_keyboard(set(data.goals))

        elif category == "target_stack":
            if value in data.target_stack:
                data.target_stack.remove(value)
            else:
                data.target_stack.append(value)
            await self._save_state(user.id, data)
            keyboard = build_target_stack_keyboard(set(data.target_stack))

        else:
            return

        # Edit existing message keyboard instead of sending new one
        if message_id:
            try:
                await self._channel.edit_keyboard(chat_id, message_id, keyboard)
            except Exception:
                await self._channel.send_keyboard(chat_id, f"Select and tap Confirm:", keyboard=keyboard)
        else:
            await self._channel.send_keyboard(chat_id, f"Select and tap Confirm:", keyboard=keyboard)

    async def _handle_confirm(
        self,
        user: User,
        chat_id: str,
        data: OnboardingData,
        category: str,
    ) -> None:
        if category == "tech_stack" and data.state == OnboardingState.TECH_STACK.value:
            if not data.tech_stack:
                await self._channel.send_text(
                    chat_id, "Please select at least one technology before confirming."
                )
                return
            data.state = OnboardingState.GOALS.value
            await self._save_state(user.id, data)
            keyboard = build_goals_keyboard(set())
            await self._channel.send_keyboard(chat_id, GOALS_PROMPT, keyboard=keyboard)

        elif category == "goals" and data.state == OnboardingState.GOALS.value:
            if not data.goals:
                await self._channel.send_text(
                    chat_id, "Please select at least one goal before confirming."
                )
                return

            if "technical_interview" in data.goals:
                data.state = OnboardingState.TARGET_STACK.value
                await self._save_state(user.id, data)
                keyboard = build_target_stack_keyboard(set())
                await self._channel.send_keyboard(
                    chat_id, TARGET_STACK_PROMPT, keyboard=keyboard
                )
            else:
                data.state = OnboardingState.TARGET_COMPANY.value
                await self._save_state(user.id, data)
                keyboard = build_target_company_keyboard()
                await self._channel.send_keyboard(
                    chat_id, TARGET_COMPANY_PROMPT, keyboard=keyboard
                )

        elif category == "target_stack" and data.state == OnboardingState.TARGET_STACK.value:
            if not data.target_stack:
                await self._channel.send_text(
                    chat_id, "Please select at least one target technology."
                )
                return
            data.state = OnboardingState.TARGET_COMPANY.value
            await self._save_state(user.id, data)
            keyboard = build_target_company_keyboard()
            await self._channel.send_keyboard(
                chat_id, TARGET_COMPANY_PROMPT, keyboard=keyboard
            )

    async def _advance_to_written(
        self, user: User, chat_id: str, data: OnboardingData
    ) -> None:
        # Save tech profile and goals to user record
        await self._save_tech_profile(user, data.tech_role, data.tech_stack)
        await self._save_goals(user, data.goals, data.target_stack, data.target_company)

        data.state = OnboardingState.WRITTEN_1.value
        await self._save_state(user.id, data)

        prompt = WRITTEN_ASSESSMENT_PROMPTS[1]
        await self._send_voice_prompt(chat_id, prompt)

    async def process_text_response(
        self, user: User, chat_id: str, text: str
    ) -> None:
        data = await self._get_state(user.id)
        if data is None:
            return

        state = data.state

        if state == OnboardingState.WRITTEN_1.value:
            data.responses.append(text)
            self._db.add(Message(
                conversation_id=uuid.UUID(data.conversation_id),
                role="user",
                content_text=text,
            ))
            data.state = OnboardingState.WRITTEN_2.value
            await self._save_state(user.id, data)
            prompt = WRITTEN_ASSESSMENT_PROMPTS[2]
            await self._send_voice_prompt(chat_id, prompt)

        elif state == OnboardingState.WRITTEN_2.value:
            data.responses.append(text)
            self._db.add(Message(
                conversation_id=uuid.UUID(data.conversation_id),
                role="user",
                content_text=text,
            ))
            # Build tech-context for question 3
            tech_context = data.tech_role or "your preferred technology"
            if data.tech_stack:
                tech_context = " and ".join(data.tech_stack[:2])

            data.state = OnboardingState.WRITTEN_3.value
            await self._save_state(user.id, data)
            prompt = WRITTEN_ASSESSMENT_PROMPTS[3].format(tech_context=tech_context)
            await self._send_voice_prompt(chat_id, prompt)

        elif state == OnboardingState.WRITTEN_3.value:
            data.responses.append(text)
            self._db.add(Message(
                conversation_id=uuid.UUID(data.conversation_id),
                role="user",
                content_text=text,
            ))
            data.state = OnboardingState.SPEAKING.value
            await self._save_state(user.id, data)
            await self._send_voice_prompt(chat_id, SPEAKING_ASSESSMENT_PROMPT)

    async def process_voice_response(
        self, user: User, chat_id: str, transcription: str
    ) -> None:
        data = await self._get_state(user.id)
        if data is None:
            return

        if data.state != OnboardingState.SPEAKING.value:
            return

        data.responses.append(f"[voice] {transcription}")
        self._db.add(Message(
            conversation_id=uuid.UUID(data.conversation_id),
            role="user",
            content_text=transcription,
            transcription=transcription,
        ))

        data.state = OnboardingState.CLASSIFYING.value
        await self._save_state(user.id, data)

        await self._channel.send_text(
            chat_id, "Analyzing your responses... This will take a moment."
        )

        result = await self._classify_level(user, data)

        data.state = OnboardingState.DONE.value
        await self._save_state(user.id, data)

        # Update user record
        user.current_level = result.level
        user.cefr_estimate = result.cefr
        user.onboarding_done = True

        # Create assessment record
        assessment = Assessment(
            user_id=user.id,
            type="onboarding",
            level_before=1,
            level_after=result.level,
            scores={
                "confidence": result.confidence,
                "strengths": result.strengths,
                "weaknesses": result.weaknesses,
            },
            feedback=result.feedback,
            conversation_id=uuid.UUID(data.conversation_id),
        )
        self._db.add(assessment)

        # Send results
        message = ONBOARDING_COMPLETE_TEMPLATE.format(
            level=result.level,
            cefr=result.cefr,
            confidence=int(result.confidence * 100),
            strengths=", ".join(result.strengths),
            weaknesses=", ".join(result.weaknesses),
            feedback_pt=result.feedback,
            suggested_focus=result.suggested_focus,
        )
        await self._channel.send_text(chat_id, message)
        await self._clear_state(user.id)

        logger.info(
            "onboarding_complete",
            user_id=str(user.id),
            level=result.level,
            cefr=result.cefr,
        )

    async def _classify_level(
        self, user: User, data: OnboardingData
    ) -> AssessmentResult:
        responses_text = "\n\n".join(
            f"Response {i + 1}: {r}" for i, r in enumerate(data.responses)
        )
        goals_text = ", ".join(data.goals) if data.goals else "general practice"

        prompt = CLASSIFICATION_PROMPT.format(
            tech_role=data.tech_role or "not specified",
            goals=goals_text,
            responses=responses_text,
        )

        result = await self._llm.chat_json(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "Please classify this developer's English level."}],
        )

        return AssessmentResult(
            level=result.get("level", 1),
            cefr=result.get("cefr", "A2"),
            confidence=result.get("confidence", 0.5),
            strengths=result.get("strengths", []),
            weaknesses=result.get("weaknesses", []),
            feedback=result.get("feedback_pt", ""),
            suggested_focus=result.get("suggested_focus", ""),
        )

    async def _save_tech_profile(
        self, user: User, tech_role: str, tech_stack: list[str]
    ) -> None:
        user.tech_role = tech_role
        user.tech_stack = tech_stack

    async def _save_goals(
        self,
        user: User,
        goals: list[str],
        target_stack: list[str],
        target_company: str,
    ) -> None:
        user.goals = goals
        user.target_stack = target_stack
        if target_company:
            user.target_company = target_company

    async def add_custom_option(
        self, user: User, chat_id: str, category: str, value: str
    ) -> None:
        """Add a custom typed option to a multi-select phase."""
        data = await self._get_state(user.id)
        if data is None:
            return

        value = value.strip()
        if not value:
            return

        if category == "tech_stack" and data.state == OnboardingState.TECH_STACK.value:
            if value not in data.tech_stack:
                data.tech_stack.append(value)
            await self._save_state(user.id, data)
            keyboard = build_tech_stack_keyboard(set(data.tech_stack))
            await self._channel.send_keyboard(
                chat_id,
                f'Added "{value}"! Select more or tap Confirm.',
                keyboard=keyboard,
            )
        elif category == "target_stack" and data.state == OnboardingState.TARGET_STACK.value:
            if value not in data.target_stack:
                data.target_stack.append(value)
            await self._save_state(user.id, data)
            keyboard = build_target_stack_keyboard(set(data.target_stack))
            await self._channel.send_keyboard(
                chat_id,
                f'Added "{value}"! Select more or tap Confirm.',
                keyboard=keyboard,
            )

    def is_onboarding_active(self, state: OnboardingData | None) -> bool:
        if state is None:
            return False
        return state.state != OnboardingState.DONE.value

    async def get_onboarding_state(self, user_id: uuid.UUID) -> OnboardingData | None:
        return await self._get_state(user_id)
