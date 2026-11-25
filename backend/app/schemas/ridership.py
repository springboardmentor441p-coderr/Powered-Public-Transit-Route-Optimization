"""Pydantic v2 schemas for historical CTA route ridership time series."""

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class DateRangeMeta(BaseModel):
    """Start and end date bounds."""

    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date


class RidershipObservation(BaseModel):
    """Single chronological observation (monthly aggregate or daily observation)."""

    model_config = ConfigDict(extra="forbid")

    period: str = Field(..., description="YYYY-MM for monthly or YYYY-MM-DD for daily")
    total_rides: Optional[int] = Field(None, ge=0, description="Total unlinked boardings in period")
    observation_days: Optional[int] = Field(None, ge=0, description="Number of observed days in month")
    weekday_avg_rides: Optional[float] = Field(None, ge=0.0, description="Mean weekday daily boardings")
    saturday_avg_rides: Optional[float] = Field(None, ge=0.0, description="Mean Saturday daily boardings")
    sunday_avg_rides: Optional[float] = Field(None, ge=0.0, description="Mean Sunday/Holiday daily boardings")
    daytype: Optional[str] = Field(None, description="Daytype code ('W', 'A', 'U') for daily rows")
    day_of_week: Optional[str] = Field(None, description="Day of week name for daily rows")
    is_weekend: Optional[bool] = Field(None, description="Weekend flag for daily rows")
    rides: Optional[int] = Field(None, ge=0, description="Daily unlinked boardings for daily rows")


class RidershipMethodologyMeta(BaseModel):
    """Source provenance and metric definition metadata."""

    model_config = ConfigDict(extra="forbid")

    source_table: str = "analytical.daily_ridership"
    granularity: Literal["monthly", "daily"]
    metric_definition: str = (
        "Historical daily unlinked route boardings (rides) reported by CTA; "
        "not onboard vehicle occupancy or passenger load."
    )
    missing_dates_policy: str = "Missing dates are omitted and never fabricated; zero rides are preserved as 0."


class RidershipTimeseriesResponse(BaseModel):
    """Response schema for GET /api/v1/ridership/routes/{route_id}/timeseries."""

    model_config = ConfigDict(extra="forbid")

    route_id: str
    route_short_name: str
    route_long_name: str
    route_type: int
    is_rail: bool
    ridership_available: bool
    unavailable_reason: Optional[str] = None
    requested_date_range: DateRangeMeta
    actual_date_range: Optional[DateRangeMeta] = None
    observation_count: int = Field(..., ge=0, description="Number of observations returned")
    total_observations: int = Field(..., ge=0, description="Total observations matching query")
    offset: int = Field(..., ge=0)
    limit: Optional[int] = Field(None, ge=1)
    has_more: bool
    methodology: RidershipMethodologyMeta
    data: List[RidershipObservation]
