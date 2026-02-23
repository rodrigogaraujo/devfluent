"""Test conversation engine logic."""

import pytest

from backend.src.ai.prompts.levels import get_level_config


def test_level_tts_speeds():
    """Verify TTS speeds are progressive across levels."""
    speeds = [get_level_config(level).tts_speed for level in range(1, 5)]
    assert speeds == sorted(speeds), "TTS speeds should increase with level"


def test_level_names():
    configs = {level: get_level_config(level) for level in range(1, 5)}
    assert configs[1].name == "Foundation"
    assert configs[2].name == "Developing"
    assert configs[3].name == "Proficient"
    assert configs[4].name == "Advanced"


@pytest.mark.asyncio
async def test_mock_llm_chat(mock_llm):
    response = await mock_llm.chat(
        system_prompt="You are a tutor.",
        messages=[{"role": "user", "content": "Hello"}],
    )
    assert response.content == "That's a great sentence! Keep practicing."
    assert response.input_tokens > 0
    assert len(mock_llm.calls) == 1


@pytest.mark.asyncio
async def test_mock_llm_chat_json(mock_llm):
    result = await mock_llm.chat_json(
        system_prompt="Extract corrections.",
        messages=[{"role": "user", "content": "Analyze this."}],
    )
    assert "corrections" in result
    assert "new_vocab" in result


@pytest.mark.asyncio
async def test_mock_channel_records_messages(mock_channel):
    await mock_channel.send_text("123", "Hello!")
    await mock_channel.send_audio("123", b"audio")
    assert len(mock_channel.sent_messages) == 2
    assert mock_channel.sent_messages[0]["type"] == "text"
    assert mock_channel.sent_messages[1]["type"] == "audio"


@pytest.mark.asyncio
async def test_mock_stt(mock_stt):
    result = await mock_stt.transcribe(b"audio_data")
    assert result.text == "Hello, I am practicing English."
    assert result.duration_seconds > 0


@pytest.mark.asyncio
async def test_mock_tts(mock_tts):
    audio = await mock_tts.synthesize("Hello world", speed=1.0)
    assert audio == b"fake_audio_data"
