import asyncio
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.auth.password import hash_password
from app.config import settings
import app.database as db_module
from app.models.institution import Institution
from app.models.user import User


async def seed_demo_institution():
    await db_module.init_db()
    email = settings.DEMO_INSTITUTION_EMAIL.strip().lower()
    password = settings.DEMO_INSTITUTION_PASSWORD
    inst_name = "Government Engineering College, Delhi (Demo)"

    async with db_module.AsyncSessionLocal() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing:
            existing.password_hash = hash_password(password)
            existing.is_active = True
            inst = await session.scalar(select(Institution).where(Institution.user_id == existing.id))
            if not inst:
                inst = Institution(
                    user_id=existing.id,
                    display_name=inst_name,
                )
                session.add(inst)
            await session.commit()
            print(f"[SEED] Demo institution account verified and updated: {email} (id: {existing.id})")
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
