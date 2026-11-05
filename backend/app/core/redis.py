"""Redis connection and caching utilities."""
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from app.core.config import settings


class RedisManager:
    """Redis connection manager."""

    client: Optional[Redis] = None


redis_manager = RedisManager()


async def connect_redis() -> None:
    """Initialize Redis connection."""
    redis_manager.client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    # Test connection
    await redis_manager.client.ping()


async def close_redis() -> None:
    """Close Redis connection."""
    if redis_manager.client:
        await redis_manager.client.close()


def get_redis() -> Redis:
    """Get Redis client instance."""
    if redis_manager.client is None:
        raise RuntimeError("Redis not initialized. Call connect_redis() first.")
    return redis_manager.client


@asynccontextmanager
async def get_redis_context() -> AsyncGenerator[Redis, None]:
    """Context manager for Redis operations."""
    client = get_redis()
    yield client


# Cache utilities
async def cache_set(key: str, value: Any, expire: int = 300) -> bool:
    """Set cache value with expiration."""
    client = get_redis()
    import json
    return await client.set(key, json.dumps(value), ex=expire)


async def cache_get(key: str) -> Optional[Any]:
    """Get cache value."""
    client = get_redis()
    import json
    value = await client.get(key)
    if value:
        return json.loads(value)
    return None


async def cache_delete(key: str) -> bool:
    """Delete cache key."""
    client = get_redis()
    return await client.delete(key) > 0


async def cache_exists(key: str) -> bool:
    """Check if cache key exists."""
    client = get_redis()
    return await client.exists(key) > 0


# Pub/Sub for real-time updates
async def publish(channel: str, message: Any) -> int:
    """Publish message to channel."""
    client = get_redis()
    import json
    return await client.publish(channel, json.dumps(message))


async def subscribe(channel: str):
    """Subscribe to channel."""
    client = get_redis()
    pubsub = client.pubsub()
    await pubsub.subscribe(channel)
    return pubsub