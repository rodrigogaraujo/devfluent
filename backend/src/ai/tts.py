from abc import ABC, abstractmethod

import openai


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        voice: str = "nova",
    ) -> bytes: ...


class OpenAITTS(TTSProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini-tts"):
        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._model = model

    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        voice: str = "nova",
    ) -> bytes:
        response = await self._client.audio.speech.create(
            model=self._model,
            voice=voice,
            input=text,
            response_format="opus",
            speed=speed,
        )
        return response.read()
