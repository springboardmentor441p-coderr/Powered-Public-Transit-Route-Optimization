"""Schedule API routes."""
from typing: Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.services.train import ScheduleService
from app.models.train import DayType
from app.schemas.train import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    ScheduleOptimizeRequest,
    ScheduleOptimizeResponse,
)

router = APIRouter()


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule_data: ScheduleCreate,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new schedule."""
    service = ScheduleService(db)
    schedule = await service.create_schedule(schedule_data)
    return ScheduleResponse.model_validate(schedule)


@router.get("", response_model=List[ScheduleResponse])
async def list_schedules(
    train_id: Optional[UUID] = None,
    station_id: Optional[UUID] = None,
    day_type: Optional[str] = None,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List schedules with optional filtering."""
    service = ScheduleService(db)

    dt = None
    if day_type:
        try:
            dt = DayType(day_type)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid day type")

    schedules = await service.list_schedules(train_id, station_id, dt, active_only, skip, limit)
    return [ScheduleResponse.model_validate(s) for s in schedules]


@router.get("/train/{train_id}", response_model=List[ScheduleResponse])
async def get_train_schedule(
    train_id: UUID,
    day_type: str = "weekday",
    db: AsyncSession = Depends(get_db),
):
    """Get complete schedule for a train."""
    service = ScheduleService(db)
    try:
        dt = DayType(day_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid day type")
    schedules = await service.get_train_schedule(train_id, dt)
    return [ScheduleResponse.model_validate(s) for s in schedules]


@router.get("/station/{station_id}", response_model=List[ScheduleResponse])
async def get_station_schedule(
    station_id: UUID,
    day_type: str = "weekday",
    db: AsyncSession = Depends(get_db),
):
    """Get schedule for a station."""
    service = ScheduleService(db)
    try:
        dt = DayType(day_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid day type")
    schedules = await service.get_station_schedule(station_id, dt)
    return [ScheduleResponse.model_validate(s) for s in schedules]


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get schedule by ID."""
    service = ScheduleService(db)
    schedule = await service.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return ScheduleResponse.model_validate(schedule)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: UUID,
    schedule_data: ScheduleUpdate,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Update schedule."""
    service = ScheduleService(db)
    schedule = await service.update_schedule(schedule_id, schedule_data)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return ScheduleResponse.model_validate(schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: UUID,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Delete schedule."""
    service = ScheduleService(db)
    success = await service.delete_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found")


@router.post("/optimize", response_model=ScheduleOptimizeResponse)
async def optimize_schedule(
    request: ScheduleOptimizeRequest,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Optimize train schedule for a line."""
    service = ScheduleService(db)
    result = await service.optimize_schedule(request)
    return ScheduleOptimizeResponse(**result)