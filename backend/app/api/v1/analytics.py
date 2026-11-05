"""Analytics API routes."""
from datetime import datetime, timedelta
from typing: Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.services.analytics import AnalyticsService
from app.schemas.analytics import (
    TrafficAnalyticsResponse,
    StationPerformanceResponse,
    OperationalMonitoringResponse,
)

router = APIRouter()


@router.get("/traffic", response_model=TrafficAnalyticsResponse)
async def get_traffic_analytics(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    line_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get traffic analytics for a period."""
    service = AnalyticsService(db)
    return await service.get_traffic_analytics(start_time, end_time, line_id)


@router.get("/traffic/last-7-days", response_model=TrafficAnalyticsResponse)
async def get_traffic_last_7_days(
    line_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get traffic analytics for last 7 days."""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=7)
    service = AnalyticsService(db)
    return await service.get_traffic_analytics(start_time, end_time, line_id)


@router.get("/traffic/last-30-days", response_model=TrafficAnalyticsResponse)
async def get_traffic_last_30_days(
    line_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get traffic analytics for last 30 days."""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)
    service = AnalyticsService(db)
    return await service.get_traffic_analytics(start_time, end_time, line_id)


@router.get("/station-performance", response_model=StationPerformanceResponse)
async def get_station_performance(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    line_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get station performance metrics."""
    service = AnalyticsService(db)
    return await service.get_station_performance(start_time, end_time, line_id)


@router.get("/station-performance/last-7-days", response_model=StationPerformanceResponse)
async def get_station_performance_last_7_days(
    line_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get station performance for last 7 days."""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=7)
    service = AnalyticsService(db)
    return await service.get_station_performance(start_time, end_time, line_id)


@router.get("/operational", response_model=OperationalMonitoringResponse)
async def get_operational_monitoring(
    db: AsyncSession = Depends(get_db),
):
    """Get real-time operational monitoring data."""
    service = AnalyticsService(db)
    return await service.get_operational_monitoring()