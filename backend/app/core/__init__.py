"""Core module exports."""
from app.core.config import settings, get_settings
from app.core.database import Base, engine, AsyncSessionLocal, get_db, init_db, close_db
from app.core.mongodb import mongodb, connect_mongodb, close_mongodb, get_mongodb, Collections
from app.core.redis import redis_manager, connect_redis, close_redis, get_redis, cache_set, cache_get, cache_delete, publish, subscribe
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token_type,
    TokenData,
    UserRole,
    Permission,
    ROLE_PERMISSIONS,
    get_permissions_for_role,
    get_permissions_for_roles,
    check_permission,
)

__all__ = [
    # Config
    "settings",
    "get_settings",
    # Database
    "Base",
    "engine",
    "AsyncSessionLocal",
    "get_db",
    "init_db",
    "close_db",
    # MongoDB
    "mongodb",
    "connect_mongodb",
    "close_mongodb",
    "get_mongodb",
    "Collections",
    # Redis
    "redis_manager",
    "connect_redis",
    "close_redis",
    "get_redis",
    "cache_set",
    "cache_get",
    "cache_delete",
    "publish",
    "subscribe",
    # Security
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "verify_token_type",
    "TokenData",
    "UserRole",
    "Permission",
    "ROLE_PERMISSIONS",
    "get_permissions_for_role",
    "get_permissions_for_roles",
    "check_permission",
]