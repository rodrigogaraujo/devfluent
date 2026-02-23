"""Seed base vocabulary by level for reference.

Usage:
    python -m backend.scripts.seed_vocab
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.src.models.user import User
from backend.src.models.vocabulary import UserVocabulary

# Common tech vocabulary by level
VOCAB_BY_LEVEL = {
    1: [  # Foundation / A2
        ("bug", "An error or defect in a program"),
        ("fix", "To correct a problem in code"),
        ("deploy", "To release code to production"),
        ("review", "To examine code changes"),
        ("test", "To verify code works correctly"),
        ("build", "To compile or assemble a project"),
        ("push", "To send code to a remote repository"),
        ("pull", "To download code from a remote repository"),
        ("merge", "To combine code changes together"),
        ("branch", "A separate line of development"),
        ("commit", "To save changes to version control"),
        ("server", "A computer that serves requests"),
        ("database", "A system to store and manage data"),
        ("API", "Application Programming Interface"),
        ("frontend", "The user-facing part of an application"),
        ("backend", "The server-side part of an application"),
        ("feature", "A new capability added to software"),
        ("release", "A version of software made available"),
        ("ticket", "A work item or issue to resolve"),
        ("sprint", "A fixed time period for development"),
    ],
    2: [  # Developing / B1
        ("refactor", "To restructure code without changing behavior"),
        ("scalability", "Ability to handle growing workload"),
        ("tradeoff", "A compromise between competing factors"),
        ("stakeholder", "A person with interest in the project"),
        ("pipeline", "An automated sequence of processes"),
        ("middleware", "Software between the OS and application"),
        ("endpoint", "A URL that accepts API requests"),
        ("payload", "Data sent in an API request or response"),
        ("authentication", "Verifying who a user is"),
        ("authorization", "Verifying what a user can do"),
        ("latency", "The delay before data transfer begins"),
        ("throughput", "Amount of data processed per time unit"),
        ("dependency", "An external library or service required"),
        ("migration", "Moving data or schema to a new version"),
        ("rollback", "Reverting to a previous state"),
        ("monitoring", "Observing system health and performance"),
        ("incident", "An unplanned service disruption"),
        ("postmortem", "Analysis after an incident"),
        ("standup", "A brief daily team meeting"),
        ("retrospective", "A team review of recent work"),
    ],
    3: [  # Proficient / B2
        ("bottleneck", "A point of congestion limiting performance"),
        ("leverage", "To use something to maximum advantage"),
        ("streamline", "To make a process more efficient"),
        ("mitigate", "To reduce the severity of a risk"),
        ("idempotent", "Can be applied multiple times without change"),
        ("eventual consistency", "Data will be consistent over time"),
        ("sharding", "Splitting data across multiple databases"),
        ("load balancing", "Distributing work across servers"),
        ("circuit breaker", "Pattern to prevent cascading failures"),
        ("rate limiting", "Controlling the rate of requests"),
        ("containerization", "Packaging apps in isolated containers"),
        ("orchestration", "Managing multiple containers together"),
        ("observability", "Ability to understand system state"),
        ("SLA", "Service Level Agreement"),
        ("technical debt", "Cost of shortcuts in code"),
        ("code smell", "An indicator of deeper problems"),
        ("design pattern", "A reusable solution to common problems"),
        ("microservices", "Architecture of small independent services"),
        ("event-driven", "Architecture based on event processing"),
        ("domain-driven", "Design focused on the business domain"),
    ],
    4: [  # Advanced / C1
        ("spin up", "To start or create a new instance"),
        ("double down", "To increase effort on something"),
        ("circle back", "To return to a topic later"),
        ("bikeshedding", "Spending time on trivial issues"),
        ("yak shaving", "Solving problems unrelated to the goal"),
        ("rubber ducking", "Explaining a problem to find the solution"),
        ("the ask", "The request or requirement"),
        ("push back", "To disagree or challenge a decision"),
        ("align on", "To reach agreement about"),
        ("greenfield", "A new project with no constraints"),
        ("brownfield", "Modifying an existing system"),
        ("blast radius", "Scope of impact from a change"),
        ("dogfooding", "Using your own product internally"),
        ("feature flag", "Toggle to enable/disable features"),
        ("canary deploy", "Gradual rollout to a subset of users"),
        ("blue-green deploy", "Two identical production environments"),
        ("chaos engineering", "Intentionally introducing failures"),
        ("toil", "Repetitive manual operational work"),
        ("golden path", "The recommended way to do things"),
        ("war room", "Dedicated space for incident response"),
    ],
}


async def main():
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://devfluent:devfluent@localhost:15432/devfluent"
    )
    admin_tid = int(os.environ.get("ADMIN_TELEGRAM_ID", "123456789"))

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        # Find test user
        result = await db.execute(
            select(User).where(User.telegram_id == admin_tid)
        )
        user = result.scalar_one_or_none()
        if user is None:
            print(f"No user with telegram_id={admin_tid}. Run create_test_user.py first.")
            await engine.dispose()
            return

        count = 0
        for level, words in VOCAB_BY_LEVEL.items():
            for word, definition in words:
                # Check if already exists
                existing = await db.execute(
                    select(UserVocabulary).where(
                        UserVocabulary.user_id == user.id,
                        UserVocabulary.word == word,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                vocab = UserVocabulary(
                    user_id=user.id,
                    word=word,
                    context=definition,
                    level_learned=level,
                    next_review=datetime.utcnow() + timedelta(days=level),
                )
                db.add(vocab)
                count += 1

        await db.commit()
        print(f"Seeded {count} vocabulary words for user {user.name} (tid={admin_tid})")
        print(f"Total by level: {', '.join(f'L{k}={len(v)}' for k, v in VOCAB_BY_LEVEL.items())}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
