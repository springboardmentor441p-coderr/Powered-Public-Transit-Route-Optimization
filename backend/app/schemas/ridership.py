"""Ridership and train occupancy schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RidershipRecordBase(BaseModel):
    """Base ridership record schema."""
    station_id: UUID
    entry_count: int = Field(default=0, ge=0)
    exit_count: int = Field(default=0, ge=0)
    timestamp: datetime
    source: str = Field(default="estimated", pattern="^(smart_card|ticketing|sensor|manual|estimated)$")


class RidershipRecordCreate(RidershipRecordBase):
    """Ridership record creation schema."""
    pass


class RidershipRecordResponse(RidershipRecordBase):
    """Ridership record response schema."""
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class TrainOccupancyBase(BaseModel):
    """Base train occupancy schema."""
    train_id: UUID
    station_id: UUID
    occupancy_count: int = Field(default=0, ge=0)
    capacity: int = Field(..., ge=1)
    timestamp: datetime


class TrainOccupancyCreate(TrainOccupancyBase):
    """Train occupancy creation schema."""
    pass


class TrainOccupancyResponse(TrainOccupancyBase):
    """Train occupancy response schema."""
    id: UUID
    created_at: datetime
    occupancy_rate: float

    class Config:
        from_attributes = True


class StationRidershipSummary(BaseModel):
    """Station ridership summary for analytics."""
    station_id: UUID
    station_name: str
    total_entries: int
    total_exits: int
    net_flow: int
    peak_hour: Optional[int] = None
    peak_entries: Optional[int] = None