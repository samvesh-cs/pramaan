from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

# Determine connect_args based on DB dialect
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Auto-migrate SQLite schema if new columns are missing
        if settings.DATABASE_URL.startswith("sqlite"):
            def migrate_sqlite_columns(connection):
                cursor = connection.connection.cursor()
                cursor.execute("PRAGMA table_info(findings)")
                existing_cols = {row[1] for row in cursor.fetchall()}
                new_columns = [
                    ("reviewer_decision", "VARCHAR(50)"),
                    ("reviewer_notes", "TEXT"),
                    ("reviewed_by", "VARCHAR(100)"),
                    ("reviewed_at", "DATETIME"),
                ]
                for col_name, col_type in new_columns:
                    if col_name not in existing_cols:
                        cursor.execute(f"ALTER TABLE findings ADD COLUMN {col_name} {col_type}")

            await conn.run_sync(migrate_sqlite_columns)
