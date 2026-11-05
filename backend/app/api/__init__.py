"""API package."""
from app.api.v1 import api_router  # noqa: F401

__all__ = ["api_router"]