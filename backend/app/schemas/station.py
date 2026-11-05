"""Station and Line schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LineBase(BaseModel):
    """Base line schema."""
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=10, pattern="^[A-Z0-9]+$")
    color: str = Field(..., pattern="^#[0-9A-Fa-f]{6}$")
    description: Optional[str] = Field(None, max_length=500)


class LineCreate(LineBase):
    """Line creation schema."""
    pass


class LineUpdate(BaseModel):
    """Line update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class LineResponse(LineBase):
    """Line response schema."""
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StationBase(BaseModel):
    """Base station schema."""
    line_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=10, pattern="^[A-Z0-9]+$")
    order: int = Field(..., ge=0)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    capacity: int = Field(default=1000, ge=1)
    zone: Optional[str] = Field(None, max_length=50)
    is_interchange: bool = False


class StationCreate(StationBase):
    """Station creation schema."""
    pass


class StationUpdate(BaseModel):
    """Station update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    order: Optional[int] = Field(None, ge=0)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    capacity: Optional[int] = Field(None, ge=1)
    zone: Optional[str] = Field(None, max_length=50)
    is_interchange: Optional[bool] = None
    is_active: Optional[bool] = None


class StationResponse(StationBase):
    """Station response schema."""
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    line: Optional[LineResponse] = None

    class Config:
        from_attributes = True


class StationWithCongestion(StationResponse):
    """Station response with congestion data."""
    current_congestion: Optional["CongestionEventResponse"] = None
    occupancy_rate: Optional[float] = None


# Forward reference
from app.schemas.congestion import CongestionEventResponse
StationWithCongestion.model_rebuild()