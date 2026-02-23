"""Create a test user for local development.

Usage:
    python -m backend.scripts.create_test_user
"""

import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.src.models.base import Base
from backend.src.models.user import User


async def main():
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://devfluent:devfluent@localhost:15432/devfluent"
    )
    admin_tid = int(os.environ.get("ADMIN_TELEGRAM_ID", "123456789"))

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        # Check if user already exists
        result = await db.execute(
            select(User).where(User.telegram_id == admin_tid)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"User with telegram_id {admin_tid} already exists (id={existing.id})")
            await engine.dispose()
            return

        user = User(
            telegram_id=admin_tid,
            name="Test Developer",
            current_level=2,
            cefr_estimate="B1",
            onboarding_done=True,
            subscription="active",
            is_active=True,
            tech_role="fullstack",
            tech_stack=["node", "react", "python"],
            goals=["technical_interview", "meetings"],
            target_stack=["node", "aws"],
            target_company="startup",
        )
        db.add(user)
        await db.commit()
        print(f"Created test user: telegram_id={admin_tid}, id={user.id}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
