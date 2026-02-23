import uuid
from dataclasses import dataclass, field
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.ai.llm import LLMProvider
from backend.src.models.user import UserErrorPattern

logger = structlog.get_logger()

FEEDBACK_EXTRACTION_PROMPT = """Analyze the tutor's response to the student's message. Extract:

1. **Corrections**: Any grammar, vocabulary, or phrasing errors the student made that the tutor corrected (explicitly or implicitly).
2. **New vocabulary**: Any new words or phrases the tutor introduced that the student likely doesn't know.

Student said: "{user_message}"
Tutor responded: "{ai_response}"

Respond in JSON:
{{
    "corrections": [
        {{
            "original": "<what the student said>",
            "corrected": "<correct version>",
            "explanation": "<brief explanation>",
            "error_type": "<grammar|vocabulary|preposition|tense|article|word_choice|spelling>"
        }}
    ],
    "new_vocab": [
        {{
            "word": "<word or phrase>",
            "context": "<how it was used in the response>",
            "definition": "<brief definition>"
        }}
    ]
}}

Rules:
- Only include ACTUAL corrections, not stylistic preferences
- error_type must be one of: grammar, vocabulary, preposition, tense, article, word_choice, spelling
- If no corrections, return empty array
- If no new vocab, return empty array
- Max 3 corrections, max 2 new vocab per exchange"""


@dataclass
class FeedbackResult:
    corrections: list[dict] = field(default_factory=list)
    new_vocab: list[dict] = field(default_factory=list)


class FeedbackAnalyzer:
    def __init__(self, llm: LLMProvider):
        self._llm = llm

    async def extract(self, ai_response: str, user_message: str) -> FeedbackResult:
        try:
            prompt = FEEDBACK_EXTRACTION_PROMPT.format(
                user_message=user_message,
                ai_response=ai_response,
            )
            result = await self._llm.chat_json(
                system_prompt=prompt,
                messages=[{"role": "user", "content": "Extract corrections and vocabulary."}],
            )
            return FeedbackResult(
                corrections=result.get("corrections", []),
                new_vocab=result.get("new_vocab", []),
            )
        except Exception:
            logger.warning("feedback_extraction_failed")
            return FeedbackResult()

    @staticmethod
    async def update_error_patterns(
        db: AsyncSession, user_id: uuid.UUID, corrections: list[dict]
    ) -> None:
        for correction in corrections:
            error_type = correction.get("error_type", "grammar")
            error_detail = correction.get("original", "")[:255]
            corrected = correction.get("corrected", "")

            if not error_detail:
                continue

            # Try to find existing pattern
            result = await db.execute(
                select(UserErrorPattern).where(
                    UserErrorPattern.user_id == user_id,
                    UserErrorPattern.error_type == error_type,
                    UserErrorPattern.error_detail == error_detail,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.occurrence_count += 1
                existing.last_seen = datetime.utcnow()
                existing.correction = corrected
            else:
                pattern = UserErrorPattern(
                    user_id=user_id,
                    error_type=error_type,
                    error_detail=error_detail,
                    correction=corrected,
                )
                db.add(pattern)
