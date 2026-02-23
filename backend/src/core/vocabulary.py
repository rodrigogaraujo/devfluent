import uuid
from datetime import datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.vocabulary import UserVocabulary

logger = structlog.get_logger()

# Simplified SM-2 intervals (days)
SM2_INTERVALS = [1, 3, 7, 14, 30, 60]


class VocabularyTracker:
    def __init__(self, db: AsyncSession | None):
        self._db = db

    async def track_words(self, user_id: uuid.UUID, vocab_list: list[dict]) -> None:
        db = self._db

        for item in vocab_list:
            word = item.get("word", "").strip()
            if not word:
                continue

            context = item.get("context", "")
            definition = item.get("definition", "")

            # Try to find existing
            result = await db.execute(
                select(UserVocabulary).where(
                    UserVocabulary.user_id == user_id,
                    UserVocabulary.word == word,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.times_seen += 1
                if context:
                    existing.context = context
            else:
                vocab = UserVocabulary(
                    user_id=user_id,
                    word=word,
                    context=context or definition,
                    level_learned=None,
                    next_review=datetime.utcnow() + timedelta(days=1),
                )
                db.add(vocab)

    async def update_usage(self, user_id: uuid.UUID, word: str) -> None:
        db = self._db

        result = await db.execute(
            select(UserVocabulary).where(
                UserVocabulary.user_id == user_id,
                UserVocabulary.word == word,
            )
        )
        vocab = result.scalar_one_or_none()
        if vocab is None:
            return

        vocab.times_used += 1

        # SM-2 simplified: interval = base_interval * ease_factor
        idx = min(vocab.times_used, len(SM2_INTERVALS) - 1)
        interval_days = SM2_INTERVALS[idx] * vocab.ease_factor
        vocab.next_review = datetime.utcnow() + timedelta(days=interval_days)

    async def get_due_words(
        self, user_id: uuid.UUID, limit: int = 10
    ) -> list[UserVocabulary]:
        db = self._db

        result = await db.execute(
            select(UserVocabulary)
            .where(
                UserVocabulary.user_id == user_id,
                UserVocabulary.next_review <= datetime.utcnow(),
            )
            .order_by(UserVocabulary.next_review)
            .limit(limit)
        )
        return list(result.scalars().all())
