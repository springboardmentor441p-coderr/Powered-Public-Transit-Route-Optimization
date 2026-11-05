"""MongoDB connection and database access."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings


class MongoDB:
    """MongoDB connection manager."""

    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None


mongodb = MongoDB()


async def connect_mongodb() -> None:
    """Initialize MongoDB connection."""
    mongodb.client = AsyncIOMotorClient(settings.MONGODB_URI)
    mongodb.db = mongodb.client[settings.MONGODB_DB]
    # Test connection
    await mongodb.client.admin.command("ping")


async def close_mongodb() -> None:
    """Close MongoDB connection."""
    if mongodb.client:
        mongodb.client.close()


def get_mongodb() -> AsyncIOMotorDatabase:
    """Get MongoDB database instance."""
    if mongodb.db is None:
        raise RuntimeError("MongoDB not initialized. Call connect_mongodb() first.")
    return mongodb.db


@asynccontextmanager
async def get_mongodb_context() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """Context manager for MongoDB operations."""
    db = get_mongodb()
    yield db


# Collection names
class Collections:
    """MongoDB collection names."""
    RIDERSHIP_ANALYTICS = "ridership_analytics"
    CONGESTION_EVENTS = "congestion_events"
    TRAIN_OCCUPANCY_HISTORY = "train_occupancy_history"
    PREDICTION_LOGS = "prediction_logs"
    ALERT_HISTORY = "alert_history"
    STATION_PERFORMANCE = "station_performance"