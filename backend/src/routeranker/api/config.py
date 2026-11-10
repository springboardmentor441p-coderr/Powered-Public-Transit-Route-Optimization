"""Environment-backed API configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime paths and explicit browser origins."""

    processed_dir: Path
    cors_origins: tuple[str, ...]
    api_prefix: str = "/api/v1"

    @classmethod
    def from_environment(cls) -> "Settings":
        root = Path(os.getenv("ROUTERANKER_PROCESSED_DIR", "data/processed")).expanduser().resolve()
        origins = tuple(
            origin.strip().rstrip("/")
            for origin in os.getenv(
                "ROUTERANKER_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if origin.strip()
        )
        return cls(processed_dir=root, cors_origins=origins)
