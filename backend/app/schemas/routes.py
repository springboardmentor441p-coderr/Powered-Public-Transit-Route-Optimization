"""Pydantic Schemas for Routes Endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.schemas.common import BaseModel, Field


class RouteItem(BaseModel):
    """Summary of a route for listing."""
    route_id: str
    agency_id: Optional[str] = "69"
    route_short_name: str
    route_long_name: str
    route_type: int = 3
    total_trips: int = 0
    trip_count: int = 0
    service_span_hours: float = 0.0
    avg_trip_duration_min: float = 0.0
    stop_count: int = 0
    estimated_distance_km: float = 0.0
    high_frequency_flag: int = 0

    def __init__(self, **data: Any) -> None:
        if "total_trips" in data and "trip_count" not in data:
            data["trip_count"] = int(data["total_trips"])
        super().__init__(**data)


class RouteDetailResponse(BaseModel):
    """Detailed operational metrics for a specific route."""
    route_id: str
    agency_id: Optional[str] = "69"
    agency_name: Optional[str] = "MTC"
    route_short_name: str
    route_long_name: str
    route_type: int = 3
    total_trips: int = 0
    trip_count: int = 0
    direction_0_trips: int = 0
    direction_1_trips: int = 0
    directions: List[int] = [0, 1]
    service_ids: List[str] = ["Regular"]
    first_departure_time: str = "N/A"
    last_departure_time: str = "N/A"
    service_span_hours: float = 0.0
    avg_trip_duration_min: float = 0.0
    min_trip_duration_min: float = 0.0
    max_trip_duration_min: float = 0.0
    avg_stops_per_trip: float = 0.0
    stop_count: int = 0
    estimated_distance_km: float = 0.0
    avg_speed_kmh: float = 0.0
    avg_headway_min: float = 0.0
    headway_std_min: float = 0.0
    headway_cv: float = 0.0
    peak_morning_trips: int = 0
    peak_evening_trips: int = 0
    off_peak_trips: int = 0
    night_trips: int = 0
    peak_ratio: float = 0.0
    direction_balance_ratio: float = 0.0
    hub_stops_count: int = 0
    high_frequency_flag: int = 0
    schedule_derived_notice: str = "Metrics computed deterministically from published GTFS timetables."

    def __init__(self, **data: Any) -> None:
        if "total_trips" in data and "trip_count" not in data:
            data["trip_count"] = int(data["total_trips"])
        super().__init__(**data)


class RouteStopItem(BaseModel):
    """A scheduled stop along a route."""
    stop_id: str
    stop_sequence: int
    direction_id: int = 0
    stop_name: str
    stop_lat: float
    stop_lon: float


class RouteStopsResponse(list):
    """Dual response: acts as list of RouteStopItem for frontend array parsing, while exposing route attributes."""
    def __init__(
        self,
        route_id: str = "",
        route_short_name: str = "",
        direction_0_stops: Optional[List[RouteStopItem]] = None,
        direction_1_stops: Optional[List[RouteStopItem]] = None,
        total_stops_served: int = 0,
        items: Optional[List[RouteStopItem]] = None,
        **kwargs: Any,
    ) -> None:
        dir0 = direction_0_stops or []
        dir1 = direction_1_stops or []
        # Frontend expects all stops ordered by sequence
        stops_list = items if items is not None else (dir0 if dir0 else dir1)
        super().__init__(stops_list)
        self.route_id = route_id
        self.route_short_name = route_short_name
        self.direction_0_stops = dir0
        self.direction_1_stops = dir1
        self.total_stops_served = total_stops_served or len(self)


class RouteTripItem(BaseModel):
    """A scheduled trip for a route."""
    trip_id: str
    route_id: str = ""
    service_id: str = "Regular"
    direction_id: int = 0
    first_departure_time: str = "N/A"
    last_arrival_time: str = "N/A"
    duration_min: float = 0.0
    stops_count: int = 0


class RouteTripsResponse(list):
    """Dual response: list of RouteTripItem for frontend, with metadata attributes."""
    def __init__(
        self,
        route_id: str = "",
        route_short_name: str = "",
        total_trips: int = 0,
        trips: Optional[List[RouteTripItem]] = None,
        **kwargs: Any,
    ) -> None:
        trip_list = trips or []
        super().__init__(trip_list)
        self.route_id = route_id
        self.route_short_name = route_short_name
        self.total_trips = total_trips or len(self)
        self.trips = trip_list


class HourlyDepartureDistribution(BaseModel):
    """Departures scheduled within a specific 1-hour time window."""
    hour_label: str
    hour_int: int
    scheduled_departures: int
    direction_0_count: int
    direction_1_count: int


class ScheduleEntry(BaseModel):
    """Individual schedule entry for timetable views."""
    trip_id: str
    direction_id: int = 0
    service_id: str = "Regular"
    departure_time: str
    stop_id: str = ""
    stop_name: str = ""


class RouteScheduleResponse(list):
    """Dual response: acts as list of ScheduleEntry for frontend, while exposing timetable attributes."""
    def __init__(
        self,
        route_id: str = "",
        route_short_name: str = "",
        service_span_hours: float = 0.0,
        first_departure_time: str = "N/A",
        last_departure_time: str = "N/A",
        active_service_ids: Optional[List[str]] = None,
        hourly_distribution: Optional[List[HourlyDepartureDistribution]] = None,
        earliest_trips: Optional[List[RouteTripItem]] = None,
        latest_trips: Optional[List[RouteTripItem]] = None,
        entries: Optional[List[ScheduleEntry]] = None,
        **kwargs: Any,
    ) -> None:
        sched_entries = entries or []
        super().__init__(sched_entries)
        self.route_id = route_id
        self.route_short_name = route_short_name
        self.service_span_hours = service_span_hours
        self.first_departure_time = first_departure_time
        self.last_departure_time = last_departure_time
        self.active_service_ids = active_service_ids or []
        self.hourly_distribution = hourly_distribution or []
        self.earliest_trips = earliest_trips or []
        self.latest_trips = latest_trips or []
