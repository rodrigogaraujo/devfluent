"""Test mock interview engine."""

import pytest

from backend.src.ai.prompts.interview import MOCK_INTERVIEW_PROMPTS


def test_hr_behavioral_prompt_has_star_method():
    prompt = MOCK_INTERVIEW_PROMPTS["hr_behavioral"]
    assert "STAR" in prompt


def test_technical_screening_prompt_has_target_stack():
    prompt = MOCK_INTERVIEW_PROMPTS["technical_screening"]
    assert "{target_stack}" in prompt


def test_system_design_prompt_has_design_elements():
    prompt = MOCK_INTERVIEW_PROMPTS["system_design"]
    assert "system design" in prompt.lower()
    assert "scalable" in prompt.lower()


def test_all_prompts_have_required_placeholders():
    for itype, prompt in MOCK_INTERVIEW_PROMPTS.items():
        assert "{tech_role}" in prompt, f"{itype} missing tech_role placeholder"
        assert "{target_stack}" in prompt, f"{itype} missing target_stack placeholder"


def test_all_prompts_request_feedback():
    for itype, prompt in MOCK_INTERVIEW_PROMPTS.items():
        assert "feedback" in prompt.lower(), f"{itype} should request feedback"
        assert "score" in prompt.lower(), f"{itype} should include scoring"
