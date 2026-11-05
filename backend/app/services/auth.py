"""Authentication service."""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    TokenData,
    UserRole,
)
from app.models.user import User, RefreshToken
from app.schemas.auth import UserCreate, UserUpdate, LoginRequest


class AuthService:
    """Authentication and user management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password."""
        result = await self.db.execute(
            select(User).where(User.email == email, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        user.last_login = datetime.utcnow()
        await self.db.commit()
        return user

    async def get_user(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        hashed_password = get_password_hash(user_data.password)
        user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            role=UserRole(user_data.role),
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_user(self, user_id: UUID, user_data: UserUpdate) -> Optional[User]:
        """Update user."""
        user = await self.get_user(user_id)
        if not user:
            return None

        update_data = user_data.model_dump(exclude_unset=True)
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
        if "role" in update_data:
            update_data["role"] = UserRole(update_data["role"])

        for field, value in update_data.items():
            setattr(user, field, value)

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete_user(self, user_id: UUID) -> bool:
        """Delete user."""
        user = await self.get_user(user_id)
        if not user:
            return False
        await self.db.delete(user)
        await self.db.commit()
        return True

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """List users with pagination."""
        result = await self.db.execute(
            select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
        )
        return list(result.scalars().all())

    def create_tokens(self, user: User) -> tuple[str, str]:
        """Create access and refresh tokens for user."""
        access_token = create_access_token(
            subject=str(user.id),
            roles=[user.role.value],
        )
        refresh_token = create_refresh_token(subject=str(user.id))
        return access_token, refresh_token

    async def store_refresh_token(self, user_id: UUID, token: str, expires_at: datetime) -> RefreshToken:
        """Store refresh token in database."""
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
        )
        self.db.add(refresh_token)
        await self.db.commit()
        await self.db.refresh(refresh_token)
        return refresh_token

    async def validate_refresh_token(self, token: str) -> Optional[User]:
        """Validate refresh token and return user."""
        payload = decode_token(token)
        if not payload or not verify_token_type(payload, "refresh"):
            return None

        token_data = TokenData(payload)
        if token_data.is_expired:
            return None

        # Check if token exists in database and not revoked
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token == token,
                RefreshToken.revoked == False,
                RefreshToken.expires_at > datetime.utcnow(),
            )
        )
        refresh_token = result.scalar_one_or_none()
        if not refresh_token:
            return None

        return await self.get_user(token_data.user_id)

    async def revoke_refresh_token(self, token: str) -> bool:
        """Revoke a refresh token."""
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token == token)
        )
        refresh_token = result.scalar_one_or_none()
        if not refresh_token:
            return False
        refresh_token.revoked = True
        await self.db.commit()
        return True

    async def revoke_all_user_tokens(self, user_id: UUID) -> int:
        """Revoke all refresh tokens for a user."""
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,
            )
        )
        tokens = result.scalars().all()
        for token in tokens:
            token.revoked = True
        await self.db.commit()
        return len(tokens)