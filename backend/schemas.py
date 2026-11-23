from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ReplayCreateRequest(BaseModel):
    start_date: str = Field(default="2026-06-01", description="Virtual replay start date (2026-06-01 to 2026-07-31)")
    reporting_delay_days: int = Field(default=1, ge=1, description="Assumed reporting delay in days")
    speed_seconds: int = Field(default=5, ge=1, description="Wall-clock seconds per virtual day")

class ReplayControlRequest(BaseModel):
    action: str = Field(..., description="start | pause | advance | reset")
    target_date: Optional[str] = Field(default=None, description="Optional jump date when resetting")

class ScenarioRequest(BaseModel):
    route: str
    service_date: str
    daytype: str = "W"
    baseline_rides: float
    baseline_trips: int
    baseline_hours: Optional[float] = None
    proposed_trips: int = Field(..., ge=0)
    demand_stress_pct: float = Field(default=0.0, description="Hypothetical demand change percentage, e.g., 20.0 for +20%")
    assumed_trip_duration_mins: Optional[float] = Field(default=None, description="Override duration in minutes if hours unavailable")