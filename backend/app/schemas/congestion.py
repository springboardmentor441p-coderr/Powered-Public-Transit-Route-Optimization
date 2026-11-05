"""Congestion schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CongestionEventResponse(BaseModel):
    """Congestion event response schema."""
    id: UUID
    station_id: UUID
    station_name: Optional[str] = None
    severity: str
    predicted: bool
    passenger_count: int
    capacity: int
    occupancy_rate: float
    timestamp: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CongestionHeatmapPoint(BaseModel):
    """Congestion heatmap point for map visualization."""
    station_id: UUID
    station_name: str
    latitude: float
    longitude: float
    severity: str
    occupancy_rate: float
    passenger_count: int
    capacity: int
    timestamp: datetime
    predicted: bool


class StationCongestionStatus(BaseModel):
    """Station congestion status for real-time monitoring."""
    station_id: UUID
    station_name: str
    line_code: str
    current_occupancy: int
    capacity: int
    occupancy_rate: float
    severity: str
    trend: str  # increasing, decreasing, stable
    last_updated: datetime
    predicted_severity: Optional[str] = None