from pydantic import BaseModel, Field
from typing import Optional

class LoginRequest(BaseModel):
    username: str
    password: str

class AlertConfigRequest(BaseModel):
    route: str
    metric: str = Field(default="rides_per_scheduled_hour", pattern="^(rides_per_scheduled_hour|rides_per_scheduled_trip|mean_daily_rides)$")
    threshold: float = Field(..., gt=0)
    condition: str = Field(default="above", pattern="^(above|below)$")
    severity: str = Field(default="warning", pattern="^(info|warning|critical|emergency)$")
    message: Optional[str] = None

class EmergencyBroadcastRequest(BaseModel):
    title: str
    message: str
    severity: str = Field(default="emergency", pattern="^(info|warning|critical|emergency)$")
    affected_routes: list[str] = []
    active: bool = True

class ScheduleUpdateRequest(BaseModel):
    route: str
    service_date: str
    new_scheduled_trips: int = Field(..., ge=0)
    reason: str = "Manual schedule update"

class ForecastRequest(BaseModel):
    route: str
    target_date: str
    virtual_date: Optional[str] = None
    reporting_delay_days: int = 1

class ReplayCreateRequest(BaseModel):
    start_date: str = "2026-06-01"
    end_date: str = "2026-07-31"
    reporting_delay_days: int = 1
    speed_seconds: int = 5

class ReplayControlRequest(BaseModel):
    action: str = Field(..., pattern="^(start|pause|advance|reset)$")

class ScenarioRequest(BaseModel):
    route: str
    service_date: str
    proposed_trips: int = Field(..., ge=0)
    demand_multiplier: float = Field(default=1.0, gt=0)
    assumed_trip_duration_minutes: Optional[float] = Field(default=None, gt=0)

class OptimizationRequest(BaseModel):
    objective: str = Field(default="maximize_ridership", pattern="^(maximize_ridership|minimize_overcrowding|cost_reduction|balanced_headways)$")
    target_date: str = "2026-06-03"
    fleet_budget_shift_pct: float = Field(default=15.0, ge=0.0, le=50.0)
    overcrowding_threshold: float = Field(default=280.0, ge=150.0, le=450.0)

class ReclusterRequest(BaseModel):
    n_clusters: int = Field(default=3, ge=2, le=5)

class ActualRidershipFeedbackRequest(BaseModel):
    route: str
    service_date: str
    actual_rides: float = Field(..., ge=0)
    predicted_rides: float = Field(..., ge=0)

class SelfTrainTriggerRequest(BaseModel):
    force_retrain: bool = False

class DelayReportRequest(BaseModel):
    route: str
    delay_minutes: int = Field(..., ge=1)
    cause: str = Field(default="Signal Issue", pattern="^(Signal Issue|Track Maintenance|Medical Emergency|Weather|Rolling Stock Failure)$")
    station_or_segment: Optional[str] = "Downtown Core Corridor"
    estimated_impact_multiplier: float = Field(default=1.25, ge=1.0, le=3.0)

