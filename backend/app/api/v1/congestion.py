"""Congestion API routes."""
from datetime import datetime, timedelta
from typing: Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.services.congestion import CongestionService
from app.schemas.congestion import (
    CongestionHeatmapPoint,
    StationCongestionStatus,
)

router = APIRouter()


@router.get("/station/{station_id}", response_model=List)
async def get_station_congestion(
    station_id: UUID,
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
):
    """Get congestion events for a station."""
    service = CongestionService(db)
    events = await service.get_station_congestion(station_id, hours)
    return events


@router.get("/station/{station_id}/current")
async def get_current_congestion(
    station_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get current congestion for a station."""
    service = CongestionService(db)
    event = await service.get_current_congestion(station_id)
    if event:
        from app.schemas.congestion import CongestionEventResponse
        return CongestionEventResponse.model_validate(event)
    return None


@router.get("/current", response_model=List)
async def get_all_current_congestion(
    db: AsyncSession = Depends(get_db),
):
    """Get all current unresolved congestion events."""
    service = CongestionService(db)
    events = await service.get_all_current_congestion()
    return events


@router.get("/heatmap", response_model=List[CongestionHeatmapPoint])
async def get_congestion_heatmap(
    db: AsyncSession = Depends(get_db),
):
    """Get congestion data for heatmap visualization."""
    service = CongestionService(db)
    return await service.get_congestion_heatmap()


@router.get("/status/all", response_model=List[StationCongestionStatus])
async def get_all_station_statuses(
    db: AsyncSession = Depends(get_db),
):
    """Get congestion status for all active stations."""
    service = CongestionService(db)
    return await service.get_station_statuses()


@router.post("/event", status_code=status.HTTP_201_CREATED)
async def create_congestion_event(
    station_id: UUID,
    passenger_count: int,
    capacity: int,
    predicted: bool = False,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Create a congestion event."""
    service = CongestionService(db)
    event = await service.create_congestion_event(station_id, passenger_count, capacity, predicted)
    from app.schemas.congestion import CongestionEventResponse
    return CongestionEventResponse.model_validate(event)


@router.put("/event/{event_id}/resolve")
async def resolve_congestion(
    event_id: UUID,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a congestion event."""
    service = CongestionService(db)
    success = await service.resolve_congestion(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Event not found or already resolved")
    return {"resolved": True}