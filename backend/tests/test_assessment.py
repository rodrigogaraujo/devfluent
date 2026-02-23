"""Test assessment and onboarding logic."""

import pytest

from backend.src.ai.prompts.interview import GOAL_TO_INTERVIEW, MOCK_INTERVIEW_PROMPTS


def test_goal_to_interview_mapping():
    assert GOAL_TO_INTERVIEW["hr_interview"] == "hr_behavioral"
    assert GOAL_TO_INTERVIEW["technical_interview"] == "technical_screening"


def test_all_interview_types_have_prompts():
    for interview_type in GOAL_TO_INTERVIEW.values():
        assert interview_type in MOCK_INTERVIEW_PROMPTS


def test_test_user_defaults(test_user):
    assert test_user.onboarding_done is True
    assert test_user.is_active is True
    assert test_user.current_level == 2
    assert test_user.tech_role == "fullstack"
    assert "node" in test_user.tech_stack
    assert "technical_interview" in test_user.goals
    assert "aws" in test_user.target_stack


@pytest.mark.asyncio
async def test_mock_interview_suggest_type(mock_llm, mock_channel, test_user):
    from backend.src.core.mock_interview import MockInterviewEngine

    engine = MockInterviewEngine(db=None, llm=mock_llm, channel=mock_channel)
    suggested = engine.suggest_interview_type(test_user)
    # test_user has "technical_interview" in goals
    assert suggested == "technical_screening"


@pytest.mark.asyncio
async def test_mock_interview_suggest_hr(mock_llm, mock_channel, test_user):
    from backend.src.core.mock_interview import MockInterviewEngine

    test_user.goals = ["hr_interview"]
    engine = MockInterviewEngine(db=None, llm=mock_llm, channel=mock_channel)
    suggested = engine.suggest_interview_type(test_user)
    assert suggested == "hr_behavioral"


@pytest.mark.asyncio
async def test_mock_interview_suggest_default(mock_llm, mock_channel, test_user):
    from backend.src.core.mock_interview import MockInterviewEngine

    test_user.goals = ["meetings"]  # No direct interview mapping
    engine = MockInterviewEngine(db=None, llm=mock_llm, channel=mock_channel)
    suggested = engine.suggest_interview_type(test_user)
    assert suggested == "hr_behavioral"  # Default fallback
