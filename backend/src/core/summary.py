import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.ai.llm import LLMProvider
from backend.src.core.feedback import FeedbackAnalyzer
from backend.src.models.conversation import Conversation, Message

logger = structlog.get_logger()

SUMMARY_PROMPT = """Analyze this English tutoring conversation between a developer and their AI tutor.
Generate a structured summary.

Conversation messages:
{messages}

Respond in JSON:
{{
    "summary": "<3-4 sentence summary of what was discussed and practiced>",
    "errors": [
        {{
            "type": "<grammar|vocabulary|preposition|tense|article|word_choice|spelling>",
            "detail": "<what the student said wrong>",
            "user_said": "<original text>",
            "correction": "<correct version>",
            "severity": "<minor|moderate|major>"
        }}
    ],
    "new_vocab": [
        {{
            "word": "<word or phrase>",
            "context": "<how it was used>",
            "definition": "<brief definition>"
        }}
    ]
}}

Rules:
- Summary should mention key topics and any progress indicators
- Only include real errors the student made, not stylistic choices
- Max 5 errors, max 5 vocab items
- If no errors found, return empty array
- If no new vocab, return empty array"""


class SummaryGenerator:
    def __init__(self, db: AsyncSession | None, llm: LLMProvider):
        self._db = db
        self._llm = llm

    async def generate(self, conversation_id: uuid.UUID) -> str | None:
        db = self._db

        # Load conversation
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()
        if conversation is None:
            return None

        # Load messages
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        messages = msg_result.scalars().all()

        if not messages:
            logger.info("summary_skip_no_messages", conversation_id=str(conversation_id))
            return None

        # Format messages for LLM
        formatted = []
        for m in messages:
            content = m.content_text or m.transcription or "(no content)"
            formatted.append(f"{m.role}: {content}")
        messages_text = "\n".join(formatted)

        try:
            prompt = SUMMARY_PROMPT.format(messages=messages_text)
            result = await self._llm.chat_json(
                system_prompt=prompt,
                messages=[{"role": "user", "content": "Generate the conversation summary."}],
            )

            summary = result.get("summary", "")
            errors = result.get("errors", [])
            new_vocab = result.get("new_vocab", [])

            # Update conversation record
            conversation.summary = summary
            conversation.errors_found = errors if errors else None
            conversation.new_vocab = new_vocab if new_vocab else None

            # Update error patterns
            if errors:
                corrections = [
                    {
                        "error_type": e.get("type", "grammar"),
                        "original": e.get("detail", ""),
                        "corrected": e.get("correction", ""),
                    }
                    for e in errors
                ]
                await FeedbackAnalyzer.update_error_patterns(
                    db, conversation.user_id, corrections
                )

            logger.info(
                "summary_generated",
                conversation_id=str(conversation_id),
                errors_count=len(errors),
                vocab_count=len(new_vocab),
            )

            return summary

        except Exception:
            logger.exception("summary_generation_failed", conversation_id=str(conversation_id))
            return None
