"""Ridership API routes."""
from datetime import datetime
from typing: Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.services.ridership import RidershipService, TrainOccupancyService
from app.models.ridership import DataSource
from app.schemas.ridership import (
    RidershipRecordCreate,
    RidershipRecordResponse,
    TrainOccupancyCreate,
    TrainOccupancyResponse,
)

router = APIRouter()


@router.post("", response_model=RidershipRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_ridership_record(
    record_data: RidershipRecordCreate,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Create a ridership record."""
    service = RidershipService(db)
    record = await service.create_ridership_record(record_data)
    return RidershipRecordResponse.model_validate(record)


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_create_ridership(
    records: List[RidershipRecordCreate],
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Bulk create ridership records."""
    service = RidershipService(db)
    count = await service.bulk_create_ridership(records)
    return {"created": count}


@router.get("/station/{station_id}", response_model=List[RidershipRecordResponse])
async def get_station_ridership(
    station_id: UUID,
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get ridership records for a station."""
    service = RidershipService(db)

    src = None
    if source:
        try:
            src = DataSource(source)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid source")

    records = await service.get_station_ridership(station_id, start_time, end_time, src)
    return [RidershipRecordResponse.model_validate(r) for r in records]


@router.get("/station/{station_id}/latest", response_model=Optional[RidershipRecordResponse])
async def get_latest_ridership(
    station_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get latest ridership record for a station."""
    service = RidershipService(db)
    record = await service.get_latest_ridership(station_id)
    if record:
        return RidershipRecordResponse.model_validate(record)
    return None


@router.get("/station/{station_id}/summary")
async def get_ridership_summary(
    station_id: UUID,
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get ridership summary for a station."""
    service = RidershipService(db)
    summary = await service.get_station_ridership_summary(station_id, start_time, end_time)
    return summary


# Train occupancy routes
@router.post("/occupancy", response_model=TrainOccupancyResponse, status_code=status.HTTP_201_CREATED)
async def create_occupancy_record(
    record_data: TrainOccupancyCreate,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Create a train occupancy record."""
    service = TrainOccupancyService(db)
    record = await service.create_occupancy_record(record_data)
    return TrainOccupancyResponse.model_validate(record)


@router.post("/occupancy/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_create_occupancy(
    records: List[TrainOccupancyCreate],
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Bulk create occupancy records."""
    service = TrainOccupancyService(db)
    count = await service.bulk_create_occupancy(records)
    return {"created": count}


@router.get("/occupancy/train/{train_id}", response_model=List[TrainOccupancyResponse])
async def get_train_occupancy(
    train_id: UUID,
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get occupancy records for a train."""
    service = TrainOccupancyService(db)
    records = await service.get_train_occupancy(train_id, start_time, end_time)
    return [TrainOccupancyResponse.model_validate(r) for r in records]


@router.get("/occupancy/station/{station_id}", response_model=List[TrainOccupancyResponse])
async def get_station_occupancy(
    station_id: UUID,
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get occupancy records for a station."""
    service = TrainOccupancyService(db)
    records = await service.get_station_occupancy(station_id, start_time, end_time)
    return [TrainOccupancyResponse.model_validate(r) for r in records]


@router.get("/occupancy/train/{train_id}/latest", response_model=Optional[TrainOccupancyResponse])
async def get_latest_train_occupancy(
    train_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get latest occupancy record for a train."""
    service = TrainOccupancyService(db)
    record = await service.get_latest_occupancy(train_id)
    if record:
        return TrainOccupancyResponse.model_validate(record)
    return None


@router.get("/occupancy/system/current")
async def get_system_occupancy(
    db: AsyncSession = Depends(get_db),
):
    """Get current system-wide occupancy."""
    service = TrainOccupancyService(db)
    return await service.get_current_system_occupancy()