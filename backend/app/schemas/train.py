"""Train and Schedule schemas."""
from datetime import datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TrainBase(BaseModel):
    """Base train schema."""
    train_number: str = Field(..., min_length=1, max_length=20, pattern="^[A-Z0-9-]+$")
    line_id: UUID
    capacity: int = Field(default=500, ge=1)


class TrainCreate(TrainBase):
    """Train creation schema."""
    pass


class TrainUpdate(BaseModel):
    """Train update schema."""
    line_id: Optional[UUID] = None
    capacity: Optional[int] = Field(None, ge=1)
    status: Optional[str] = Field(None, pattern="^(active|inactive|maintenance|delayed)$")
    current_station_id: Optional[UUID] = None


class TrainResponse(TrainBase):
    """Train response schema."""
    id: UUID
    status: str
    current_station_id: Optional[UUID] = None
    current_station: Optional["StationResponse"] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScheduleBase(BaseModel):
    """Base schedule schema."""
    train_id: UUID
    station_id: UUID
    arrival_time: Optional[time] = None
    departure_time: Optional[time] = None
    day_type: str = Field(default="weekday", pattern="^(weekday|saturday|sunday|holiday)$")
    sequence: int = Field(..., ge=0)


class ScheduleCreate(ScheduleBase):
    """Schedule creation schema."""
    pass


class ScheduleUpdate(BaseModel):
    """Schedule update schema."""
    arrival_time: Optional[time] = None
    departure_time: Optional[time] = None
    day_type: Optional[str] = Field(None, pattern="^(weekday|saturday|sunday|holiday)$")
    sequence: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ScheduleResponse(ScheduleBase):
    """Schedule response schema."""
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    train: Optional[TrainResponse] = None
    station: Optional["StationResponse"] = None

    class Config:
        from_attributes = True


class ScheduleOptimizeRequest(BaseModel):
    """Schedule optimization request."""
    line_id: UUID
    day_type: str = Field(default="weekday", pattern="^(weekday|saturday|sunday|holiday)$")
    target_headway_minutes: int = Field(default=5, ge=1, le=30)
    max_trains: int = Field(default=20, ge=1, le=100)


class ScheduleOptimizeResponse(BaseModel):
    """Schedule optimization response."""
    optimized: bool
    message: str
    recommended_headway: Optional[float] = None
    recommended_train_count: Optional[int] = None
    estimated_capacity_utilization: Optional[float] = None


# Forward references
from app.schemas.station import StationResponse
TrainResponse.model_rebuild()
ScheduleResponse.model_rebuild()