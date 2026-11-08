from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    # Use ConfigDict to load .env automatically
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database configuration – values are read from environment variables of the same name
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str

    # JWT configuration
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    # Token expiration settings (minutes)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Admin configuration (can be overridden via .env)
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "admin123"

settings = Settings()