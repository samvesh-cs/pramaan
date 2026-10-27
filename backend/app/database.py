import logging
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

logger = logging.getLogger(__name__)


def _resolve_db_url(url: str) -> str:
    # If unconfigured placeholder or missing, fallback to SQLite
    if not url or "<username>" in url or "<password>" in url or "<dbname>" in url:
        return "sqlite+aiosqlite:///./sih_prototype.db"
    return url


effective_db_url = _resolve_db_url(settings.DATABASE_URL)

connect_args = {}
if effective_db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    effective_db_url,
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


def _migrate_sqlite_columns(connection):
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

    cursor.execute("PRAGMA table_info(applications)")
    app_cols = {row[1] for row in cursor.fetchall()}
    if "owner_id" not in app_cols:
        cursor.execute("ALTER TABLE applications ADD COLUMN owner_id VARCHAR(36)")
    if "status" not in app_cols:
        cursor.execute("ALTER TABLE applications ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'draft'")

    cursor.execute("PRAGMA table_info(documents)")
    doc_cols = {row[1] for row in cursor.fetchall()}
    if "file_hash" not in doc_cols:
        cursor.execute("ALTER TABLE documents ADD COLUMN file_hash VARCHAR(64)")

    cursor.execute("PRAGMA table_info(users)")
    user_cols = {row[1] for row in cursor.fetchall()}
    if user_cols and "last_login_at" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN last_login_at DATETIME")


async def init_db() -> None:
    global engine, AsyncSessionLocal, effective_db_url

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if effective_db_url.startswith("sqlite"):
                await conn.run_sync(_migrate_sqlite_columns)
    except Exception as e:
        # If connecting to PostgreSQL failed, fallback to local SQLite so development and demo never break
        if not effective_db_url.startswith("sqlite"):
            logger.warning(
                "Primary database (%s) connection failed: %s. Falling back to local SQLite database (./sih_prototype.db).",
                effective_db_url,
                e,
            )
            print(f"[WARN] Database connection failed ({e}). Falling back to local SQLite database (./sih_prototype.db).")
            effective_db_url = "sqlite+aiosqlite:///./sih_prototype.db"
            engine = create_async_engine(
                effective_db_url,
                echo=settings.DEBUG,
                future=True,
                connect_args={"check_same_thread": False},
            )
            AsyncSessionLocal = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await conn.run_sync(_migrate_sqlite_columns)
        else:
            raise e

