WELCOME_MESSAGE = (
    "Hey there! Welcome to DevFluent — your AI English tutor built for developers like you.\n\n"
    "I'll help you practice English for real work situations: meetings, code reviews, "
    "interviews, and everyday dev communication.\n\n"
    "Let's start by getting to know you a bit. First, I need to understand your current "
    "English level, your tech background, and what you want to practice.\n\n"
    "Ready? Let's go!"
)

SELF_DECLARATION_PROMPT = (
    "How would you rate your current English level?\n\n"
    "This is just a starting point — I'll assess you properly in a moment."
)

SELF_DECLARATION_OPTIONS = ["Beginner", "Intermediate", "Advanced"]

TECH_ROLE_PROMPT = (
    "What's your main tech role?\n\n"
    "This helps me tailor conversations to your daily work context."
)

TECH_ROLE_OPTIONS = ["Backend", "Frontend", "Fullstack", "Mobile", "Data/ML", "DevOps/Infra"]

TECH_STACK_PROMPT = (
    "What technologies do you work with?\n\n"
    "Select all that apply, then tap Confirm."
)

TECH_STACK_OPTIONS = [
    "Python", "JavaScript/TS", "Java", "Go", "React", "Node.js",
    "AWS", "Kubernetes", "SQL", "Docker", "C#/.NET", "Ruby",
]

GOALS_PROMPT = (
    "What do you want to practice with DevFluent?\n\n"
    "Select all that apply, then tap Confirm."
)

GOALS_OPTIONS = [
    ("hr_interview", "HR/Behavioral interview"),
    ("technical_interview", "Technical interview"),
    ("meetings", "Daily meetings & standups"),
    ("presentations", "Leading meetings & presentations"),
]

TARGET_STACK_PROMPT = (
    "You're preparing for technical interviews — great!\n\n"
    "What stack is the job you're targeting?\n"
    "Select all that apply, then tap Confirm."
)

TARGET_STACK_OPTIONS = [
    "Node.js", "Python", "React", "Java", "Go", "AWS", "System Design",
    "Kubernetes", "SQL", "Docker", "C#/.NET", "Ruby",
]

TARGET_COMPANY_PROMPT = (
    "What type of company are you targeting?\n\n"
    "This helps me adjust the interview style and vocabulary."
)

TARGET_COMPANY_OPTIONS = ["Big Tech", "Startup", "Enterprise", "Not sure"]

WRITTEN_ASSESSMENT_PROMPTS = {
    1: (
        "Let's check your English! Tell me a bit about yourself — "
        "what do you do and what project are you working on right now?\n\n"
        "(Write in English, don't worry about mistakes!)"
    ),
    2: (
        "Nice! Now imagine you're in a standup meeting. "
        "Describe what you did yesterday and what you plan to do today.\n\n"
        "(Try to use complete sentences.)"
    ),
    3: (
        "Last one! Imagine you're explaining a technical decision to a teammate. "
        "Why would you choose {tech_context} for a new project? "
        "What are the trade-offs?\n\n"
        "(Take your time, be as detailed as you'd like.)"
    ),
}

SPEAKING_ASSESSMENT_PROMPT = (
    "Almost done! Now I'd like to hear your voice.\n\n"
    "Send me a voice message explaining: What's the most interesting technical "
    "challenge you've faced recently? How did you solve it?\n\n"
    "(Speak in English for about 30-60 seconds. Don't worry about being perfect!)"
)

CLASSIFICATION_PROMPT = """You are an English language assessor for Brazilian software developers.

Analyze the following responses from a developer's English assessment. Consider:
- Grammar accuracy and complexity
- Vocabulary range (general + technical)
- Sentence structure and coherence
- Communication effectiveness
- The user's tech role: {tech_role}
- The user's learning goals: {goals}

Classify into exactly one level:
- Level 1 (Foundation/A2): Basic phrases, frequent errors, limited vocabulary
- Level 2 (Developing/B1): Simple sentences work, some complex structures, moderate errors
- Level 3 (Proficient/B2): Good fluency, occasional errors, can discuss technical topics
- Level 4 (Advanced/C1): Near-native fluency, rare errors, nuanced expression

Respond in JSON with this exact structure:
{{
    "level": <1-4>,
    "cefr": "<A2|B1|B2|C1>",
    "confidence": <0.0-1.0>,
    "strengths": ["<strength1>", "<strength2>"],
    "weaknesses": ["<weakness1>", "<weakness2>"],
    "feedback_pt": "<feedback paragraph in Brazilian Portuguese>",
    "suggested_focus": "<personalized suggestion based on their goals, in English>"
}}

Assessment responses:
{responses}"""

ONBOARDING_COMPLETE_TEMPLATE = (
    "Assessment complete! Here are your results:\n\n"
    "Level: {level}/4 ({cefr})\n"
    "Confidence: {confidence}%\n\n"
    "Strengths: {strengths}\n"
    "Areas to improve: {weaknesses}\n\n"
    "{feedback_pt}\n\n"
    "Focus: {suggested_focus}\n\n"
    "Your personalized study plan is ready! Use /plan to see it."
)
