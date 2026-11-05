"""Authentication API routes."""
from datetime import timedelta
from typing: Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token_type,
    TokenData,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.services.auth import AuthService
from app.schemas.auth import (
    Token,
    LoginRequest,
    RegisterRequest,
    UserResponse,
    UserUpdate,
    RefreshTokenRequest,
)

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Get current authenticated user."""
    payload = decode_token(token)
    if not payload or not verify_token_type(payload, "access"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = TokenData(payload)
    if token_data.is_expired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = AuthService(db)
    user = await auth_service.get_user(UUID(token_data.user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserResponse.model_validate(user)


async def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_role(*roles: str):
    """Dependency to require specific roles."""
    async def role_checker(current_user: UserResponse = Depends(get_current_active_user)) -> UserResponse:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return role_checker


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """User login."""
    auth_service = AuthService(db)
    user = await auth_service.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, refresh_token = auth_service.create_tokens(user)

    # Store refresh token
    from datetime import datetime
    expires_at = datetime.utcnow() + timedelta(days=7)
    await auth_service.store_refresh_token(user.id, refresh_token, expires_at)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register new user (admin only in production)."""
    auth_service = AuthService(db)

    # Check if user exists
    existing = await auth_service.get_user_by_email(user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = await auth_service.create_user(user_data)
    return UserResponse.model_validate(user)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token."""
    auth_service = AuthService(db)
    user = await auth_service.validate_refresh_token(request.refresh_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Revoke old refresh token
    await auth_service.revoke_refresh_token(request.refresh_token)

    # Create new tokens
    access_token, refresh_token = auth_service.create_tokens(user)
    from datetime import datetime
    expires_at = datetime.utcnow() + timedelta(days=7)
    await auth_service.store_refresh_token(user.id, refresh_token, expires_at)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Logout - revoke refresh token."""
    auth_service = AuthService(db)
    await auth_service.revoke_refresh_token(request.refresh_token)
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserResponse = Depends(get_current_active_user)):
    """Get current user profile."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_me(
    user_data: UserUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile."""
    auth_service = AuthService(db)
    user = await auth_service.update_user(current_user.id, user_data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


# Admin routes
@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: UserResponse = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    auth_service = AuthService(db)
    users = await auth_service.list_users(skip, limit)
    return [UserResponse.model_validate(u) for u in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: UserResponse = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Get user by ID (admin only)."""
    auth_service = AuthService(db)
    user = await auth_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    current_user: UserResponse = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Update user (admin only)."""
    auth_service = AuthService(db)
    user = await auth_service.update_user(user_id, user_data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: UserResponse = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Delete user (admin only)."""
    auth_service = AuthService(db)
    success = await auth_service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")