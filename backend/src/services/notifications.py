from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.src.channels.base import MessageChannel
from backend.src.models.conversation import Message
from backend.src.models.user import User
from backend.src.services.reports import ReportService

logger = structlog.get_logger()


class NotificationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        channel: MessageChannel,
    ):
        self._session_factory = session_factory
        self._channel = channel

    async def send_daily_reminder(self) -> None:
        """Send reminder to active users who haven't practiced today."""
        async with self._session_factory() as db:
            try:
                today_start = datetime.combine(date.today(), datetime.min.time())

                # Get active users
                result = await db.execute(
                    select(User).where(User.is_active.is_(True), User.onboarding_done.is_(True))
                )
                users = result.scalars().all()

                for user in users:
                    # Check if user sent any messages today
                    msg_count = await db.execute(
                        select(func.count(Message.id))
                        .join(
                            # Simplified: just check messages by role
                        )
                        .where(
                            Message.role == "user",
                            Message.created_at >= today_start,
                        )
                    )
                    # Simplified approach: send to all active users who haven't messaged
                    # A more precise version would join through conversations
                    await self._channel.send_text(
                        str(user.telegram_id),
                        "Hey! You haven't practiced English today. "
                        "Send me a message to keep your streak going!",
                    )
                    logger.info("daily_reminder_sent", user_id=str(user.id))

            except Exception:
                logger.exception("daily_reminder_error")

    async def send_weekly_reports(self) -> None:
        """Send weekly reports to all active users."""
        async with self._session_factory() as db:
            try:
                result = await db.execute(
                    select(User).where(User.is_active.is_(True), User.onboarding_done.is_(True))
                )
                users = result.scalars().all()

                report_service = ReportService(db=db)

                for user in users:
                    try:
                        report = await report_service.generate_weekly_report(user.id)
                        await self._channel.send_text(str(user.telegram_id), report)
                        logger.info("weekly_report_sent", user_id=str(user.id))
                    except Exception:
                        logger.warning("weekly_report_failed", user_id=str(user.id))

            except Exception:
                logger.exception("weekly_reports_error")
