"""Station and Line API routes."""
from typing: Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.services.station import StationService
from app.schemas.station import (
    StationCreate,
    StationUpdate,
    StationResponse,
    LineCreate,
    LineUpdate,
    LineResponse,
)

router = APIRouter()


# Line routes
@router.post("/lines", response_model=LineResponse, status_code=status.HTTP_201_CREATED)
async def create_line(
    line_data: LineCreate,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new line."""
    service = StationService(db)

    # Check if code exists
    existing = await service.get_line_by_code(line_data.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Line code already exists",
        )

    line = await service.create_line(line_data)
    return LineResponse.model_validate(line)


@router.get("/lines", response_model=List[LineResponse])
async def list_lines(
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List all lines."""
    service = StationService(db)
    lines = await service.list_lines(active_only, skip, limit)
    return [LineResponse.model_validate(l) for l in lines]


@router.get("/lines/{line_id}", response_model=LineResponse)
async def get_line(
    line_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get line by ID."""
    service = StationService(db)
    line = await service.get_line(line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    return LineResponse.model_validate(line)


@router.put("/lines/{line_id}", response_model=LineResponse)
async def update_line(
    line_id: UUID,
    line_data: LineUpdate,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Update line."""
    service = StationService(db)
    line = await service.update_line(line_id, line_data)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    return LineResponse.model_validate(line)


@router.delete("/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_line(
    line_id: UUID,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Delete line."""
    service = StationService(db)
    success = await service.delete_line(line_id)
    if not success:
        raise HTTPException(status_code=404, detail="Line not found")


# Station routes
@router.post("", response_model=StationResponse, status_code=status.HTTP_201_CREATED)
async def create_station(
    station_data: StationCreate,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new station."""
    service = StationService(db)

    # Check if code exists
    existing = await service.get_station_by_code(station_data.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Station code already exists",
        )

    station = await service.create_station(station_data)
    return StationResponse.model_validate(station)


@router.get("", response_model=List[StationResponse])
async def list_stations(
    line_id: Optional[UUID] = None,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List stations with optional filtering."""
    service = StationService(db)
    stations = await service.list_stations(line_id, active_only, skip, limit)
    return [StationResponse.model_validate(s) for s in stations]


@router.get("/{station_id}", response_model=StationResponse)
async def get_station(
    station_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get station by ID."""
    service = StationService(db)
    station = await service.get_station(station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return StationResponse.model_validate(station)


@router.get("/code/{code}", response_model=StationResponse)
async def get_station_by_code(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """Get station by code."""
    service = StationService(db)
    station = await service.get_station_by_code(code)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return StationResponse.model_validate(station)


@router.get("/line/{line_id}", response_model=List[StationResponse])
async def get_stations_by_line(
    line_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all stations for a line in order."""
    service = StationService(db)
    stations = await service.get_stations_by_line(line_id)
    return [StationResponse.model_validate(s) for s in stations]


@router.put("/{station_id}", response_model=StationResponse)
async def update_station(
    station_id: UUID,
    station_data: StationUpdate,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Update station."""
    service = StationService(db)
    station = await service.update_station(station_id, station_data)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return StationResponse.model_validate(station)


@router.delete("/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_station(
    station_id: UUID,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Delete station."""
    service = StationService(db)
    success = await service.delete_station(station_id)
    if not success:
        raise HTTPException(status_code=404, detail="Station not found")