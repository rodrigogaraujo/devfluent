"""Test prompt templates render correctly."""

from backend.src.ai.prompts.levels import (
    LEVEL_PROMPTS,
    build_goals_context,
    get_level_config,
)


def test_all_levels_exist():
    assert set(LEVEL_PROMPTS.keys()) == {1, 2, 3, 4}


def test_level_config_fields():
    for level, config in LEVEL_PROMPTS.items():
        assert config.name, f"Level {level} missing name"
        assert config.cefr, f"Level {level} missing CEFR"
        assert config.instructions, f"Level {level} missing instructions"
        assert config.tts_speed > 0, f"Level {level} invalid tts_speed"
        assert config.vocab_rate > 0, f"Level {level} invalid vocab_rate"


def test_get_level_config_valid():
    config = get_level_config(1)
    assert config.name == "Foundation"
    assert config.cefr == "A2"


def test_get_level_config_fallback():
    config = get_level_config(99)
    assert config.name == "Developing"  # Fallback to level 2


def test_build_goals_context_empty():
    result = build_goals_context([], [], "")
    assert "No specific goals" in result


def test_build_goals_context_with_goals():
    result = build_goals_context(
        goals=["technical_interview", "meetings"],
        target_stack=["node", "aws"],
        target_company="startup",
    )
    assert "technical interview" in result.lower()
    assert "node" in result.lower()
    assert "startup" in result.lower()


def test_interview_prompts_render():
    from backend.src.ai.prompts.interview import MOCK_INTERVIEW_PROMPTS

    for itype, template in MOCK_INTERVIEW_PROMPTS.items():
        rendered = template.format(
            tech_role="fullstack",
            target_stack="node, aws",
            target_company="startup",
        )
        assert len(rendered) > 50, f"Interview prompt {itype} too short"
        assert "{" not in rendered, f"Interview prompt {itype} has unresolved placeholders"
