"""API v1 routes."""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.stations import router as stations_router
from app.api.v1.trains import router as trains_router
from app.api.v1.schedules import router as schedules_router
from app.api.v1.ridership import router as ridership_router
from app.api.v1.congestion import router as congestion_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.predictions import router as predictions_router
from app.api.v1.analytics import router as analytics_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(stations_router, prefix="/stations", tags=["Stations"])
api_router.include_router(trains_router, prefix="/trains", tags=["Trains"])
api_router.include_router(schedules_router, prefix="/schedules", tags=["Schedules"])
api_router.include_router(ridership_router, prefix="/ridership", tags=["Ridership"])
api_router.include_router(congestion_router, prefix="/congestion", tags=["Congestion"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["Alerts"])
api_router.include_router(predictions_router, prefix="/predictions", tags=["Predictions"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])