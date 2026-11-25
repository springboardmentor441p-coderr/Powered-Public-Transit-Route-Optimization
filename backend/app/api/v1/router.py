"""Aggregated API v1 router."""

from fastapi import APIRouter

from app.api.v1.corridors import router as corridors_router
from app.api.v1.forecasting import router as forecasting_router
from app.api.v1.rankings import router as rankings_router
from app.api.v1.ridership import router as ridership_router
from app.api.v1.routes import router as routes_router
from app.api.v1.spatial import router as spatial_router

api_v1_router = APIRouter()
api_v1_router.include_router(routes_router)
api_v1_router.include_router(rankings_router)
api_v1_router.include_router(ridership_router)
api_v1_router.include_router(spatial_router)
api_v1_router.include_router(corridors_router)
api_v1_router.include_router(forecasting_router)
