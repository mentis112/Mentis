import asyncio
import os

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.instructor import Instructor
from app.repositories.preference_repository import PreferenceRepository


async def seed_demo_user() -> None:
    email = os.getenv("DEMO_USER_EMAIL", "demo@mentis.dev").strip().lower()
    username = os.getenv("DEMO_USER_USERNAME", "Demo Instructor").strip()
    password = os.getenv("DEMO_USER_PASSWORD", "DemoPass123!").strip()

    if not email or not username or len(password) < 8:
        raise RuntimeError("Invalid demo user environment values")

    async with SessionLocal() as session:
        existing = (
            await session.execute(select(Instructor).where(Instructor.email == email))
        ).scalar_one_or_none()
        if existing:
            print(f"Demo user already exists: {email}")
            return

        instructor = Instructor(
            username=username,
            email=email,
            password_hash=hash_password(password),
        )
        session.add(instructor)
        await session.flush()
        await PreferenceRepository(session).create_default(instructor.id)
        await session.commit()
        print(f"Created demo user: {email}")


if __name__ == "__main__":
    asyncio.run(seed_demo_user())
