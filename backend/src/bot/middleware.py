from datetime import date

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from backend.src.config import settings
from backend.src.models.user import User

logger = structlog.get_logger()

OPEN_COMMANDS = {"/start", "/help"}


async def user_lookup(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_session: AsyncSession,
) -> User | None:
    tg_user = update.effective_user
    if not tg_user:
        return None

    result = await db_session.execute(
        select(User).where(User.telegram_id == tg_user.id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=tg_user.id,
            name=tg_user.first_name or tg_user.username or "Unknown",
            is_active=False,
        )
        db_session.add(user)
        await db_session.flush()
        logger.info("user_created", telegram_id=tg_user.id, name=user.name)

    context.user_data["user"] = user
    context.user_data["db_session"] = db_session
    return user


async def active_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user: User | None = context.user_data.get("user")
    if user is None:
        return False

    if user.is_active:
        return True

    message_text = ""
    if update.message and update.message.text:
        message_text = update.message.text.split()[0] if update.message.text else ""

    if message_text in OPEN_COMMANDS:
        return True

    if update.callback_query:
        return True

    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You're on the waitlist! We'll activate you soon. 🎯",
        )
    return False


async def rate_limit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    redis_client: object | None,
) -> bool:
    if redis_client is None:
        return True

    user: User | None = context.user_data.get("user")
    if user is None:
        return True

    try:
        key = f"msg_count:{user.id}:{date.today().isoformat()}"
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 86400)

        if count > settings.MAX_MESSAGES_PER_DAY:
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="You've been practicing a lot today! Let's continue tomorrow. 💪",
                )
            return False
    except Exception:
        logger.warning("rate_limit_redis_error", user_id=str(user.id))

    return True
