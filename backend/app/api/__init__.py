"""API router package."""
from fastapi import APIRouter
from app.api.endpoints import router as api_router

__all__ = ["api_router"]
