import asyncio
from collections.abc import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class FakeUser:
    def __init__(
        self,
        role: str,
        id: str = "inst-test-1",
        email: str = "institution@test-college.edu",
        is_active: bool = True,
    ):
        self.id = id
        self.role = role
        self.email = email
        self.is_active = is_active
        self.institution = None


@pytest_asyncio.fixture
async def institution_client(client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    from app.auth.dependencies import get_current_user

    user = FakeUser(
        role="INSTITUTION",
        id="inst-test-1",
        email="principal@test-college.edu",
    )
    app.dependency_overrides[get_current_user] = lambda: user
    yield client
    app.dependency_overrides.pop(get_current_user, None)



@pytest_asyncio.fixture
async def reviewer_client(client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    from app.auth.dependencies import get_current_user

    user = FakeUser(
        role="REVIEWER",
        id="rev-test-1",
        email="reviewer@aicte-india.org",
    )
    app.dependency_overrides[get_current_user] = lambda: user
    yield client
    app.dependency_overrides.pop(get_current_user, None)

