import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.ai.llm import LLMProvider
from backend.src.models.study_plan import StudyPlan
from backend.src.models.user import User

logger = structlog.get_logger()

STUDY_PLAN_PROMPT = """You are a curriculum designer for an English tutoring platform for software developers.

Create a personalized week 1 study plan for this developer:

- Name: {name}
- English level: {level}/4 ({cefr})
- Tech role: {tech_role}
- Tech stack: {tech_stack}
- Learning goals: {goals}
- Target stack (for interviews): {target_stack}
- Target company type: {target_company}

Design a study plan that:
1. Focuses on their stated goals (e.g., if "hr_interview" → behavioral question practice, if "technical_interview" → technical vocabulary for their target stack)
2. Matches their English level (simpler exercises for L1-L2, more complex for L3-L4)
3. Incorporates their tech background naturally

Respond in JSON:
{{
    "theme": "<short theme for this week, e.g., 'Self-introduction & project description'>",
    "focus_skills": ["<skill1>", "<skill2>", "<skill3>"],
    "target_vocab": ["<word1>", "<word2>", "<word3>", "<word4>", "<word5>"]
}}

Rules:
- theme: max 60 chars, practical and specific to their goals
- focus_skills: exactly 3 skills, oriented to their goals
- target_vocab: 5 words/phrases relevant to their level + goals + tech stack"""


class StudyPlanGenerator:
    def __init__(self, db: AsyncSession, llm: LLMProvider):
        self._db = db
        self._llm = llm

    async def generate(self, user: User) -> StudyPlan:
        goals_text = ", ".join(user.goals) if user.goals else "general English practice"
        target_stack_text = ", ".join(user.target_stack) if user.target_stack else "not specified"
        tech_stack_text = ", ".join(user.tech_stack) if user.tech_stack else "not specified"

        cefr_map = {1: "A2", 2: "B1", 3: "B2", 4: "C1"}
        cefr = cefr_map.get(user.current_level, "B1")

        prompt = STUDY_PLAN_PROMPT.format(
            name=user.name or "Developer",
            level=user.current_level,
            cefr=cefr,
            tech_role=user.tech_role or "not specified",
            tech_stack=tech_stack_text,
            goals=goals_text,
            target_stack=target_stack_text,
            target_company=user.target_company or "not specified",
        )

        result = await self._llm.chat_json(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "Generate my personalized study plan."}],
        )

        plan = StudyPlan(
            user_id=user.id,
            level=user.current_level,
            week_number=1,
            theme=result.get("theme", "Getting Started"),
            focus_skills=result.get("focus_skills", []),
            target_vocab=result.get("target_vocab", []),
        )
        self._db.add(plan)
        await self._db.flush()

        logger.info(
            "study_plan_generated",
            user_id=str(user.id),
            theme=plan.theme,
            level=plan.level,
        )

        return plan
