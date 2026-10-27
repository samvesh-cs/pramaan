import asyncio
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.auth.password import hash_password
from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.models.user import User


async def seed_reviewer():
    await init_db()
    email = settings.REVIEWER_EMAIL.strip().lower()
    password = settings.REVIEWER_PASSWORD

    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing:
            existing.password_hash = hash_password(password)
            existing.is_active = True
            await session.commit()
            print(f"[SEED] Reviewer account verified and updated: {email} (id: {existing.id})")
            return existing

        user = User(
            email=email,
            password_hash=hash_password(password),
            role="REVIEWER",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        print(f"[SEED] Successfully created reviewer: {email} (id: {user.id})")
        return user


if __name__ == "__main__":
    asyncio.run(seed_reviewer())
