from pydantic import BaseModel, Field
from typing import Optional

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
