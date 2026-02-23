import uuid
from datetime import date, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.metrics import WeeklyMetrics
from backend.src.models.user import User

logger = structlog.get_logger()


class ReportService:
    def __init__(self, db: AsyncSession | None):
        self._db = db

    async def generate_weekly_report(self, user_id: uuid.UUID) -> str:
        db = self._db

        # Get user
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if user is None:
            return "User not found."

        # Get current week metrics
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        result = await db.execute(
            select(WeeklyMetrics).where(
                WeeklyMetrics.user_id == user_id,
                WeeklyMetrics.week_start == week_start,
            )
        )
        metrics = result.scalar_one_or_none()

        if metrics is None:
            return (
                f"Hi {user.name or 'there'}! No activity recorded this week yet.\n\n"
                "Start a conversation to begin tracking your progress!"
            )

        # Calculate goal progress
        goal_pct = min(100, int((metrics.minutes_practiced / max(user.weekly_goal_min, 1)) * 100))

        lines = [
            f"Weekly Report for {user.name or 'Developer'}",
            f"Week of {week_start.strftime('%b %d, %Y')}",
            "",
            f"Practice time: {metrics.minutes_practiced} min / {user.weekly_goal_min} min goal ({goal_pct}%)",
            f"Messages sent: {metrics.messages_sent}",
            f"Voice messages: {metrics.audio_messages}",
            f"New words learned: {metrics.new_words}",
            f"Grammar corrections: {metrics.errors_grammar}",
            f"Streak: {metrics.streak_days} days",
            f"XP earned: {metrics.xp_earned}",
        ]

        if goal_pct >= 100:
            lines.append("\nYou hit your weekly goal! Great work!")
        elif goal_pct >= 50:
            remaining = user.weekly_goal_min - metrics.minutes_practiced
            lines.append(f"\n{remaining} more minutes to reach your goal. Keep going!")
        else:
            lines.append("\nTry to practice a little each day — consistency is key!")

        return "\n".join(lines)
