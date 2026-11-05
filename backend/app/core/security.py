"""Security utilities for authentication and authorization."""
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from jose import jwt
from passlib.context import CryptContext
from pydantic import SecretStr

from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(
    subject: str,
    roles: list[str],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": subject,
        "roles": roles,
        "exp": expire,
        "type": "access",
        "jti": str(uuid4()),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Create JWT refresh token."""
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid4()),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.JWTError:
        return {}


def verify_token_type(payload: dict, token_type: str) -> bool:
    """Verify token type matches expected type."""
    return payload.get("type") == token_type


class TokenData:
    """Token data extracted from JWT."""

    def __init__(self, payload: dict):
        self.user_id: str = payload.get("sub", "")
        self.roles: list[str] = payload.get("roles", [])
        self.exp: int = payload.get("exp", 0)
        self.token_type: str = payload.get("type", "")
        self.jti: str = payload.get("jti", "")

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.utcnow().timestamp() > self.exp

    def has_role(self, role: str) -> bool:
        """Check if user has specific role."""
        return role in self.roles

    def has_any_role(self, roles: list[str]) -> bool:
        """Check if user has any of the specified roles."""
        return any(role in self.roles for role in roles)


# Role definitions
class UserRole:
    """User role constants."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

    @classmethod
    def all(cls) -> list[str]:
        return [cls.ADMIN, cls.OPERATOR, cls.VIEWER]

    @classmethod
    def management_roles(cls) -> list[str]:
        """Roles that can manage resources."""
        return [cls.ADMIN, cls.OPERATOR]


# Permission definitions
class Permission:
    """Permission constants."""
    # Station permissions
    STATION_READ = "station:read"
    STATION_WRITE = "station:write"
    STATION_DELETE = "station:delete"

    # Train permissions
    TRAIN_READ = "train:read"
    TRAIN_WRITE = "train:write"
    TRAIN_DELETE = "train:delete"

    # Schedule permissions
    SCHEDULE_READ = "schedule:read"
    SCHEDULE_WRITE = "schedule:write"
    SCHEDULE_DELETE = "schedule:delete"
    SCHEDULE_OPTIMIZE = "schedule:optimize"

    # Prediction permissions
    PREDICTION_READ = "prediction:read"
    PREDICTION_WRITE = "prediction:write"
    PREDICTION_RETRAIN = "prediction:retrain"

    # Alert permissions
    ALERT_READ = "alert:read"
    ALERT_WRITE = "alert:write"
    ALERT_DISMISS = "alert:dismiss"

    # Analytics permissions
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"

    # User management
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"


# Role-Permission mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        Permission.STATION_READ, Permission.STATION_WRITE, Permission.STATION_DELETE,
        Permission.TRAIN_READ, Permission.TRAIN_WRITE, Permission.TRAIN_DELETE,
        Permission.SCHEDULE_READ, Permission.SCHEDULE_WRITE, Permission.SCHEDULE_DELETE, Permission.SCHEDULE_OPTIMIZE,
        Permission.PREDICTION_READ, Permission.PREDICTION_WRITE, Permission.PREDICTION_RETRAIN,
        Permission.ALERT_READ, Permission.ALERT_WRITE, Permission.ALERT_DISMISS,
        Permission.ANALYTICS_READ, Permission.ANALYTICS_EXPORT,
        Permission.USER_READ, Permission.USER_WRITE, Permission.USER_DELETE,
    ],
    UserRole.OPERATOR: [
        Permission.STATION_READ, Permission.STATION_WRITE,
        Permission.TRAIN_READ, Permission.TRAIN_WRITE,
        Permission.SCHEDULE_READ, Permission.SCHEDULE_WRITE, Permission.SCHEDULE_OPTIMIZE,
        Permission.PREDICTION_READ,
        Permission.ALERT_READ, Permission.ALERT_WRITE, Permission.ALERT_DISMISS,
        Permission.ANALYTICS_READ,
        Permission.USER_READ,
    ],
    UserRole.VIEWER: [
        Permission.STATION_READ,
        Permission.TRAIN_READ,
        Permission.SCHEDULE_READ,
        Permission.PREDICTION_READ,
        Permission.ALERT_READ,
        Permission.ANALYTICS_READ,
        Permission.USER_READ,
    ],
}


def get_permissions_for_role(role: str) -> list[str]:
    """Get permissions for a role."""
    return ROLE_PERMISSIONS.get(role, [])


def get_permissions_for_roles(roles: list[str]) -> list[str]:
    """Get combined permissions for multiple roles."""
    permissions = set()
    for role in roles:
        permissions.update(ROLE_PERMISSIONS.get(role, []))
    return list(permissions)


def check_permission(user_roles: list[str], required_permission: str) -> bool:
    """Check if user roles have required permission."""
    user_permissions = get_permissions_for_roles(user_roles)
    return required_permission in user_permissions