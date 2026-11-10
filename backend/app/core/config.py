"""Configuration settings for RouteRanker Backend."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List


class Settings:
    """Application configuration and file system paths."""

    # Project paths
    BACKEND_DIR: Path = Path(__file__).resolve().parent.parent.parent
    PROJECT_ROOT: Path = BACKEND_DIR.parent
    DATA_RAW_DIR: Path = PROJECT_ROOT / "data" / "raw"
    DATA_PROCESSED_DIR: Path = PROJECT_ROOT / "data" / "processed"
    DATA_MODELS_DIR: Path = PROJECT_ROOT / "data" / "models"

    GTFS_ZIP_PATH: Path = DATA_RAW_DIR / "mtc-gtfs.zip"
    DUCKDB_PATH: Path = DATA_PROCESSED_DIR / "routeranker.duckdb"
    SQLITE_PATH: Path = DATA_PROCESSED_DIR / "routeranker.db"

    # API Settings
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "RouteRanker GTFS Analytics API"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "*",
    ]

    # Pagination
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 500

    def ensure_directories(self) -> None:
        """Ensure all storage directories exist."""
        self.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
        self.DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        self.DATA_MODELS_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()

