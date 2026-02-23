import uuid
from dataclasses import dataclass
from typing import Any

import pytest
import pytest_asyncio

from backend.src.ai.llm import LLMProvider, LLMResponse
from backend.src.ai.stt import STTProvider, STTResult
from backend.src.ai.tts import TTSProvider
from backend.src.channels.base import MessageChannel


# --- Mock Providers ---


class MockLLMProvider(LLMProvider):
    """LLM mock that returns canned responses. Tracks calls for assertions."""

    def __init__(self):
        self.calls: list[dict] = []
        self.chat_response = "That's a great sentence! Keep practicing."
        self.chat_json_response: dict = {
            "corrections": [],
            "new_vocab": [],
        }

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        self.calls.append({
            "method": "chat",
            "system_prompt": system_prompt,
            "messages": messages,
        })
        return LLMResponse(
            content=self.chat_response,
            input_tokens=100,
            output_tokens=50,
            model="mock-model",
        )

    async def chat_json(
        self,
        system_prompt: str,
        messages: list[dict],
        schema: dict | None = None,
    ) -> dict:
        self.calls.append({
            "method": "chat_json",
            "system_prompt": system_prompt,
            "messages": messages,
        })
        return self.chat_json_response


class MockSTTProvider(STTProvider):
    def __init__(self):
        self.transcription = "Hello, I am practicing English."

    async def transcribe(
        self, audio_bytes: bytes, language: str = "en"
    ) -> STTResult:
        return STTResult(
            text=self.transcription,
            language=language,
            duration_seconds=3.5,
        )


class MockTTSProvider(TTSProvider):
    async def synthesize(
        self, text: str, speed: float = 1.0, voice: str = "nova"
    ) -> bytes:
        return b"fake_audio_data"


class MockMessageChannel(MessageChannel):
    """Records all sent messages for test assertions."""

    def __init__(self):
        self.sent_messages: list[dict] = []

    async def send_text(self, chat_id: str, text: str, **kwargs: Any) -> None:
        self.sent_messages.append({"type": "text", "chat_id": chat_id, "text": text})

    async def send_audio(
        self, chat_id: str, audio: bytes, caption: str = "", **kwargs: Any
    ) -> None:
        self.sent_messages.append({
            "type": "audio",
            "chat_id": chat_id,
            "caption": caption,
        })

    async def send_keyboard(
        self, chat_id: str, text: str, options: list[list[str]] | None = None, **kwargs: Any
    ) -> None:
        self.sent_messages.append({
            "type": "keyboard",
            "chat_id": chat_id,
            "text": text,
            "options": options,
        })

    async def download_audio(self, file_id: str) -> bytes:
        return b"fake_audio_data"


# --- Fixtures ---


@pytest.fixture
def mock_llm():
    return MockLLMProvider()


@pytest.fixture
def mock_stt():
    return MockSTTProvider()


@pytest.fixture
def mock_tts():
    return MockTTSProvider()


@pytest.fixture
def mock_channel():
    return MockMessageChannel()


@dataclass
class FakeUser:
    """Lightweight User stand-in for unit tests that don't need a real DB."""
    id: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
    telegram_id: int = 123456789
    name: str = "Test User"
    email: str | None = None
    current_level: int = 2
    cefr_estimate: str | None = "B1"
    onboarding_done: bool = True
    subscription: str = "active"
    weekly_goal_min: int = 60
    timezone: str = "America/Sao_Paulo"
    is_active: bool = True
    tech_role: str = "fullstack"
    tech_stack: list = None
    goals: list = None
    target_stack: list = None
    target_company: str = "startup"

    def __post_init__(self):
        if self.tech_stack is None:
            self.tech_stack = ["node", "react", "python"]
        if self.goals is None:
            self.goals = ["technical_interview", "meetings"]
        if self.target_stack is None:
            self.target_stack = ["node", "aws"]


@pytest.fixture
def test_user():
    return FakeUser()
