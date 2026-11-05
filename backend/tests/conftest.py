"""Pytest configuration and fixtures."""
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403

# Test database URL (in-memory SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a fresh database session for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    """Create a test client with overridden database dependency."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Create authentication headers for testing."""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@metroflow.com",
        "password": "testpassword123",
        "full_name": "Test User",
        "role": "operator",
    }


@pytest.fixture
def sample_station_data():
    """Sample station data for testing."""
    return {
        "name": "Test Station",
        "code": "TST",
        "order": 1,
        "latitude": 40.7580,
        "longitude": -73.9855,
        "capacity": 1000,
        "zone": "1",
    }


@pytest.fixture
def sample_train_data():
    """Sample train data for testing."""
    return {
        "train_number": "TEST-001",
        "line_id": "00000000-0000-0000-0000-000000000000",
        "capacity": 500,
    }