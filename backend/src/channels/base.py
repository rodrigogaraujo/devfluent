from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class IncomingMessage:
    chat_id: str
    user_id: str
    user_name: str
    text: str | None
    audio_file_id: str | None
    is_audio: bool
    raw: Any


class MessageChannel(ABC):
    @abstractmethod
    async def send_text(self, chat_id: str, text: str, **kwargs: Any) -> None: ...

    @abstractmethod
    async def send_audio(
        self, chat_id: str, audio: bytes, caption: str = "", **kwargs: Any
    ) -> None: ...

    @abstractmethod
    async def send_keyboard(
        self, chat_id: str, text: str, options: list[list[str]], **kwargs: Any
    ) -> None: ...

    @abstractmethod
    async def edit_keyboard(
        self, chat_id: str, message_id: int, keyboard: Any, **kwargs: Any
    ) -> None: ...

    @abstractmethod
    async def download_audio(self, file_id: str) -> bytes: ...
