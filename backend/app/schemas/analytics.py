"""Pydantic Schemas for Network Analytics Endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.schemas.common import BaseModel, Field


class FrequencyItem(BaseModel):
    """Route frequency and schedule headway metrics."""
    route_id: str
    route_short_name: str
    total_trips: int
    avg_headway_min: float
    headway_std_min: float = 0.0
    headway_cv: float = 0.0
    peak_morning_trips: int = 0
    peak_evening_trips: int = 0
    off_peak_trips: int = 0
    night_trips: int = 0
    high_frequency_flag: int = 0

    # Frontend compatibility fields
    trip_count: int = 0
    avg_headway_minutes: Optional[float] = None
    min_headway_minutes: Optional[float] = None
    max_headway_minutes: Optional[float] = None
    first_departure: Optional[str] = None
    last_departure: Optional[str] = None
    service_span_hours: Optional[float] = None
    trips_per_hour: Optional[float] = None

    def __init__(self, **data: Any) -> None:
        if "total_trips" in data and "trip_count" not in data:
            data["trip_count"] = int(data["total_trips"])
        if "avg_headway_min" in data and "avg_headway_minutes" not in data:
            data["avg_headway_minutes"] = float(data["avg_headway_min"])
        super().__init__(**data)


class HourlyTripVolume(BaseModel):
    """Network-wide trip count in each 1-hour interval."""
    hour_label: str
    hour_int: int
    total_trips: int
    is_peak: bool


class ServiceStats(BaseModel):
    """Service calendar summary."""
    service_id: str
    days: List[str] = []
    trip_count: int = 0
    route_count: int = 0
    start_date: str = "20240501"
    end_date: str = "20300501"


class ServiceSpanAnalyticsResponse(list):
    """Dual response: acts as list of ServiceStats for frontend array response, while holding network span attributes."""
    def __init__(
        self,
        system_earliest_departure: str = "04:00:00",
        system_latest_departure: str = "23:59:00",
        avg_route_span_hours: float = 0.0,
        median_route_span_hours: float = 0.0,
        span_histogram: Optional[Dict[str, int]] = None,
        network_trips_by_hour: Optional[List[HourlyTripVolume]] = None,
        service_stats: Optional[List[ServiceStats]] = None,
        items: Optional[List[ServiceStats]] = None,
        **kwargs: Any,
    ) -> None:
        stats_list = items if items is not None else (service_stats or [])
        super().__init__(stats_list)
        self.system_earliest_departure = system_earliest_departure
        self.system_latest_departure = system_latest_departure
        self.avg_route_span_hours = avg_route_span_hours
        self.median_route_span_hours = median_route_span_hours
        self.span_histogram = span_histogram or {}
        self.network_trips_by_hour = network_trips_by_hour or []
        self.service_stats = stats_list
        self.schedule_derived_notice = "Values calculated strictly from scheduled departure times across all trips."
