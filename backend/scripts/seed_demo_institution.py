import asyncio
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.auth.password import hash_password
from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.models.institution import Institution
from app.models.user import User


async def seed_demo_institution():
    await init_db()
    email = settings.DEMO_INSTITUTION_EMAIL.strip().lower()
    password = settings.DEMO_INSTITUTION_PASSWORD
    inst_name = "Government Engineering College, Delhi (Demo)"

    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing:
            print(f"[SEED] Demo institution account already exists: {email} (id: {existing.id})")
            return existing

        user = User(
            email=email,
            password_hash=hash_password(password),
            role="INSTITUTION",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        inst = Institution(
            user_id=user.id,
            display_name=inst_name,
        )
        session.add(inst)
        await session.commit()
        await session.refresh(user)
        print(f"[SEED] Successfully created demo institution: {email} (id: {user.id})")
        return user


if __name__ == "__main__":
    asyncio.run(seed_demo_institution())
