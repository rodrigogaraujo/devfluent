"""Test context assembly logic."""

import pytest

from backend.src.utils.tokens import count_tokens, truncate_messages


def test_count_tokens_basic():
    tokens = count_tokens("Hello, world!")
    assert tokens > 0
    assert tokens < 10


def test_count_tokens_empty():
    assert count_tokens("") == 0


def test_truncate_messages_within_budget():
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    result = truncate_messages(messages, max_tokens=1000)
    assert len(result) == 2


def test_truncate_messages_over_budget():
    messages = [
        {"role": "user", "content": "A" * 500},
        {"role": "assistant", "content": "B" * 500},
        {"role": "user", "content": "C" * 500},
        {"role": "assistant", "content": "D" * 500},
        {"role": "user", "content": "E" * 500},
        {"role": "assistant", "content": "F" * 500},
    ]
    result = truncate_messages(messages, max_tokens=100, keep_minimum=2)
    assert len(result) >= 2
    assert len(result) < len(messages)


def test_truncate_messages_keeps_minimum():
    messages = [
        {"role": "user", "content": "X" * 1000},
        {"role": "assistant", "content": "Y" * 1000},
        {"role": "user", "content": "Z" * 1000},
    ]
    result = truncate_messages(messages, max_tokens=10, keep_minimum=2)
    assert len(result) >= 2
