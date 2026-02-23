import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

import openai


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse: ...

    @abstractmethod
    async def chat_json(
        self,
        system_prompt: str,
        messages: list[dict],
        schema: dict | None = None,
    ) -> dict: ...


class OpenAILLM(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._model = model

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        all_messages = [{"role": "system", "content": system_prompt}, *messages]
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=all_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        usage = response.usage
        return LLMResponse(
            content=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=response.model,
        )

    async def chat_json(
        self,
        system_prompt: str,
        messages: list[dict],
        schema: dict | None = None,
    ) -> dict:
        all_messages = [{"role": "system", "content": system_prompt}, *messages]
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=all_messages,
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
