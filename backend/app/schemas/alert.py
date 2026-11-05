"""Alert schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AlertBase(BaseModel):
    """Base alert schema."""
    type: str = Field(..., pattern="^(overcrowding|delay|emergency|maintenance|schedule_change|system)$")
    severity: str = Field(..., pattern="^(info|warning|critical)$")
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    station_id: Optional[UUID] = None
    train_id: Optional[UUID] = None
    expires_at: Optional[datetime] = None


class AlertCreate(AlertBase):
    """Alert creation schema."""
    pass


class AlertUpdate(BaseModel):
    """Alert update schema."""
    is_read: Optional[bool] = None
    is_dismissed: Optional[bool] = None
    dismissed_by: Optional[UUID] = None


class AlertResponse(AlertBase):
    """Alert response schema."""
    id: UUID
    is_read: bool
    is_dismissed: bool
    dismissed_by: Optional[UUID] = None
    dismissed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    station: Optional["StationResponse"] = None
    train: Optional["TrainResponse"] = None

    class Config:
        from_attributes = True


class AlertSummary(BaseModel):
    """Alert summary for dashboard."""
    total: int
    unread: int
    critical: int
    warning: int
    info: int
    by_type: dict[str, int]


# Forward references
from app.schemas.station import StationResponse
from app.schemas.train import TrainResponse
AlertResponse.model_rebuild()