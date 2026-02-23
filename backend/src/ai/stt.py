from abc import ABC, abstractmethod
from dataclasses import dataclass

import groq


@dataclass
class STTResult:
    text: str
    language: str
    duration_seconds: float


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
    ) -> STTResult: ...


class GroqSTT(STTProvider):
    def __init__(self, api_key: str, model: str = "whisper-large-v3"):
        self._client = groq.AsyncGroq(api_key=api_key)
        self._model = model

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
    ) -> STTResult:
        response = await self._client.audio.transcriptions.create(
            file=("audio.ogg", audio_bytes),
            model=self._model,
            language=language,
        )

        text = response.text.strip()
        if not text:
            raise ValueError("Empty transcription returned from STT")

        duration = getattr(response, "duration", 0.0) or 0.0

        return STTResult(
            text=text,
            language=language,
            duration_seconds=float(duration),
        )
