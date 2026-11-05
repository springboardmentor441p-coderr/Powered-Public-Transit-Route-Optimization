"""Prediction schemas."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class CrowdPredictionRequest(BaseModel):
    """Crowd prediction request."""
    station_id: UUID
    hours_ahead: int = Field(default=24, ge=1, le=168)
    interval_minutes: int = Field(default=15, ge=5, le=60)


class CrowdPredictionPoint(BaseModel):
    """Single crowd prediction point."""
    timestamp: datetime
    predicted_entries: int
    predicted_exits: int
    predicted_occupancy: int
    confidence_lower: int
    confidence_upper: int


class CrowdPredictionResponse(BaseModel):
    """Crowd prediction response."""
    station_id: UUID
    station_name: str
    predictions: List[CrowdPredictionPoint]
    model_version: str
    generated_at: datetime


class DemandForecastPoint(BaseModel):
    """Demand forecast point."""
    date: datetime
    predicted_demand: int
    confidence_lower: int
    confidence_upper: int
    factors: dict[str, float]


class DemandForecastResponse(BaseModel):
    """Demand forecast response."""
    line_id: Optional[UUID] = None
    station_id: Optional[UUID] = None
    forecasts: List[DemandForecastPoint]
    model_version: str
    generated_at: datetime


class TrafficPatternPoint(BaseModel):
    """Traffic pattern point."""
    hour: int
    day_of_week: int
    avg_entries: float
    avg_exits: float
    peak_factor: float


class TrafficPatternResponse(BaseModel):
    """Traffic pattern analysis response."""
    station_id: UUID
    station_name: str
    patterns: List[TrafficPatternPoint]
    peak_hours: List[int]
    off_peak_hours: List[int]
    weekly_pattern: dict[str, float]


class ModelRetrainRequest(BaseModel):
    """Model retrain request."""
    model_type: str = Field(..., pattern="^(crowd|demand|congestion|all)$")
    force: bool = False


class ModelRetrainResponse(BaseModel):
    """Model retrain response."""
    success: bool
    message: str
    model_type: str
    training_time_seconds: Optional[float] = None
    metrics: Optional[dict] = None