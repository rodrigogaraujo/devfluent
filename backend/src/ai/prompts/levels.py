from dataclasses import dataclass


@dataclass
class LevelConfig:
    name: str
    cefr: str
    instructions: str
    tts_speed: float
    vocab_rate: int  # new words per exchange


LEVEL_PROMPTS: dict[int, LevelConfig] = {
    1: LevelConfig(
        name="Foundation",
        cefr="A2",
        instructions=(
            "This student is at the Foundation level (A2). They understand basic English but struggle "
            "with complex sentences.\n\n"
            "Teaching approach:\n"
            "- Use simple, short sentences (max 15 words)\n"
            "- Explain grammar corrections in Portuguese (Brazilian)\n"
            "- Provide translations for new vocabulary in parentheses\n"
            "- Focus on high-frequency tech terms: 'deploy', 'bug', 'fix', 'review'\n"
            "- Be very encouraging — mistakes are expected and welcome\n"
            "- For interview-prep: practice simple self-introductions and 'tell me about yourself'\n"
            "- Speak slowly and clearly (TTS speed: 0.85x)"
        ),
        tts_speed=0.85,
        vocab_rate=1,
    ),
    2: LevelConfig(
        name="Developing",
        cefr="B1",
        instructions=(
            "This student is at the Developing level (B1). They can communicate in English but make "
            "frequent errors and sometimes fall back to Portuguese structures.\n\n"
            "Teaching approach:\n"
            "- Use natural sentences, moderate complexity\n"
            "- Correct errors in English with brief explanations\n"
            "- Introduce intermediate vocabulary: 'refactor', 'scalability', 'tradeoff', 'stakeholder'\n"
            "- Encourage complete sentences and linking words (however, therefore, although)\n"
            "- For interview-prep: practice standup updates, describe technical decisions\n"
            "- For meetings-prep: practice agreeing/disagreeing politely, asking for clarification\n"
            "- Normal speech pace (TTS speed: 1.0x)"
        ),
        tts_speed=1.0,
        vocab_rate=2,
    ),
    3: LevelConfig(
        name="Proficient",
        cefr="B2",
        instructions=(
            "This student is at the Proficient level (B2). They communicate well in English with "
            "occasional errors, mainly in complex structures and idiomatic expressions.\n\n"
            "Teaching approach:\n"
            "- Use complex, natural English — don't simplify\n"
            "- Correct subtle errors: wrong prepositions, tense consistency, word choice\n"
            "- Introduce advanced vocabulary: 'bottleneck', 'leverage', 'streamline', 'mitigate'\n"
            "- Push for nuance: 'impact vs affect', 'ensure vs make sure'\n"
            "- Encourage technical discussions: system design, architecture tradeoffs\n"
            "- For interview-prep: practice STAR method, technical deep-dives, whiteboard explanations\n"
            "- For presentations-prep: practice structuring arguments, hedging language\n"
            "- Slightly faster pace (TTS speed: 1.05x)"
        ),
        tts_speed=1.05,
        vocab_rate=2,
    ),
    4: LevelConfig(
        name="Advanced",
        cefr="C1",
        instructions=(
            "This student is at the Advanced level (C1). They communicate fluently with rare errors, "
            "mostly in idiomatic usage and subtle register choices.\n\n"
            "Teaching approach:\n"
            "- Treat as a near-native speaker — full complexity, idioms, humor\n"
            "- Focus on register: formal vs informal, written vs spoken\n"
            "- Teach leadership language: 'I'd push back on that', 'let's align on', 'the ask is'\n"
            "- Introduce phrasal verbs and collocations used in tech: 'spin up', 'double down', 'circle back'\n"
            "- Discuss nuance: cultural differences in communication styles (US vs UK vs global)\n"
            "- For interview-prep: practice system design explanations, leadership scenarios, salary negotiation\n"
            "- For presentations-prep: practice persuasion techniques, storytelling with data\n"
            "- Faster pace (TTS speed: 1.10x)"
        ),
        tts_speed=1.10,
        vocab_rate=2,
    ),
}


def get_level_config(level: int) -> LevelConfig:
    return LEVEL_PROMPTS.get(level, LEVEL_PROMPTS[2])


def build_goals_context(goals: list[str], target_stack: list[str], target_company: str) -> str:
    if not goals:
        return "No specific goals set — general English practice for developers."

    parts = []
    goal_labels = {
        "hr_interview": "preparing for HR/behavioral interviews",
        "technical_interview": "preparing for technical interviews",
        "meetings": "improving daily meeting communication",
        "presentations": "improving presentation and leadership communication",
    }

    for g in goals:
        label = goal_labels.get(g, g)
        parts.append(f"- {label}")

    context = "Student's learning goals:\n" + "\n".join(parts)

    if target_stack:
        context += f"\nTarget tech stack for interviews: {', '.join(target_stack)}"
    if target_company:
        context += f"\nTarget company type: {target_company}"

    context += "\n\nAdapt conversation topics and vocabulary to support these goals."
    return context
