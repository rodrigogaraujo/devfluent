from datetime import date, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from backend.src.config import settings
from backend.src.models.conversation import Message
from backend.src.models.user import User

logger = structlog.get_logger()


def _is_admin(update: Update) -> bool:
    tid = str(update.effective_user.id) if update.effective_user else ""
    return tid == settings.ADMIN_TELEGRAM_ID and tid != ""


async def handle_activate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update) or update.effective_chat is None:
        return

    args = context.args or []
    if not args:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Usage: /activate <telegram_id>",
        )
        return

    telegram_id = int(args[0])
    db_session: AsyncSession = context.application.bot_data["db_session"]()
    try:
        result = await db_session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"User with telegram_id {telegram_id} not found.",
            )
            return

        user.is_active = True
        user.subscription = "active"
        await db_session.commit()

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"User {user.name or telegram_id} activated.",
        )
    except Exception:
        await db_session.rollback()
        logger.exception("handle_activate_error")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error activating user.",
        )
    finally:
        await db_session.close()


async def handle_deactivate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update) or update.effective_chat is None:
        return

    args = context.args or []
    if not args:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Usage: /deactivate <telegram_id>",
        )
        return

    telegram_id = int(args[0])
    db_session: AsyncSession = context.application.bot_data["db_session"]()
    try:
        result = await db_session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"User with telegram_id {telegram_id} not found.",
            )
            return

        user.is_active = False
        user.subscription = "inactive"
        await db_session.commit()

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"User {user.name or telegram_id} deactivated.",
        )
    except Exception:
        await db_session.rollback()
        logger.exception("handle_deactivate_error")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error deactivating user.",
        )
    finally:
        await db_session.close()


async def handle_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update) or update.effective_chat is None:
        return

    db_session: AsyncSession = context.application.bot_data["db_session"]()
    try:
        result = await db_session.execute(
            select(User).order_by(User.created_at.desc()).limit(20)
        )
        users = result.scalars().all()

        if not users:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="No users found.",
            )
            return

        lines = ["<b>Users (last 20):</b>\n"]
        for u in users:
            status = "active" if u.is_active else "waitlist"
            onb = "done" if u.onboarding_done else "pending"
            lines.append(
                f"- {u.name or 'unnamed'} | L{u.current_level} | {status} | onb:{onb} | tid:{u.telegram_id}"
            )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="\n".join(lines),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("handle_users_error")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error fetching users.",
        )
    finally:
        await db_session.close()


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update) or update.effective_chat is None:
        return

    db_session: AsyncSession = context.application.bot_data["db_session"]()
    try:
        # Total users
        total_result = await db_session.execute(select(func.count(User.id)))
        total_users = total_result.scalar() or 0

        # Active users
        active_result = await db_session.execute(
            select(func.count(User.id)).where(User.is_active.is_(True))
        )
        active_users = active_result.scalar() or 0

        # Messages today
        today_start = datetime.combine(date.today(), datetime.min.time())
        msg_result = await db_session.execute(
            select(func.count(Message.id)).where(Message.created_at >= today_start)
        )
        messages_today = msg_result.scalar() or 0

        # Estimated cost (~R$0.21 per message)
        estimated_cost = messages_today * 0.21

        text = (
            "<b>Stats:</b>\n\n"
            f"Total users: {total_users}\n"
            f"Active users: {active_users}\n"
            f"Messages today: {messages_today}\n"
            f"Est. cost today: R${estimated_cost:.2f}"
        )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("handle_stats_error")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error fetching stats.",
        )
    finally:
        await db_session.close()
