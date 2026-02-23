from typing import Any

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from backend.src.channels.base import MessageChannel


class TelegramChannel(MessageChannel):
    def __init__(self, bot: Bot):
        self._bot = bot

    async def send_text(self, chat_id: str, text: str, **kwargs: Any) -> None:
        await self._bot.send_message(
            chat_id=int(chat_id),
            text=text,
            parse_mode="HTML",
            **kwargs,
        )

    async def send_audio(
        self, chat_id: str, audio: bytes, caption: str = "", **kwargs: Any
    ) -> None:
        await self._bot.send_voice(
            chat_id=int(chat_id),
            voice=audio,
            caption=caption or None,
            **kwargs,
        )

    async def send_keyboard(
        self, chat_id: str, text: str, options: list[list[str]] | None = None, **kwargs: Any
    ) -> None:
        reply_markup = kwargs.pop("keyboard", None)
        if reply_markup is None and options is not None:
            keyboard = [
                [InlineKeyboardButton(text=opt, callback_data=opt) for opt in row]
                for row in options
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        await self._bot.send_message(
            chat_id=int(chat_id),
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            **kwargs,
        )

    async def edit_keyboard(
        self, chat_id: str, message_id: int, keyboard: Any, **kwargs: Any
    ) -> None:
        await self._bot.edit_message_reply_markup(
            chat_id=int(chat_id),
            message_id=message_id,
            reply_markup=keyboard,
            **kwargs,
        )

    async def download_audio(self, file_id: str) -> bytes:
        file = await self._bot.get_file(file_id)
        data = await file.download_as_bytearray()
        return bytes(data)
