"""Pydantic Schemas for Dashboard and Quality Endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.schemas.common import BaseModel, Field


class TopRouteItem(BaseModel):
    """High-volume route metric."""
    route_id: str
    route_short_name: str
    route_long_name: str
    total_trips: int
    trip_count: int = 0
    stop_count: int = 0
    avg_headway_min: float = 0.0
    service_span_hours: float = 0.0

    def __init__(self, **data: Any) -> None:
        if "total_trips" in data and "trip_count" not in data:
            data["trip_count"] = data["total_trips"]
        elif "trip_count" in data and "total_trips" not in data:
            data["total_trips"] = data["trip_count"]
        super().__init__(**data)


class DashboardSummaryResponse(BaseModel):
    """High-level system metrics for executive overview dashboard."""
    total_routes: int
    total_stops: int
    total_trips: int
    total_service_ids: int = 6
    avg_stops_per_route: float = 0.0
    avg_trips_per_route: float = 0.0
    high_frequency_routes_count: int = 0
    total_scheduled_vehicle_hours: float = 0.0
    total_scheduled_vehicle_km: float = 0.0
    system_avg_headway_min: float = 0.0
    system_avg_trip_duration_min: float = 0.0
    agency_name: str = "MTC"
    data_quality_score: float = 100.0
    top_frequent_routes: List[TopRouteItem] = []
    top_routes_by_trips: List[Dict[str, Any]] = []
    top_routes_by_stops: List[Dict[str, Any]] = []
    trip_distribution: List[Dict[str, Any]] = []
    multi_route_stops: List[Dict[str, Any]] = []
    service_distribution: List[Dict[str, Any]] = []
    schedule_derived_notice: str = (
        "All figures reflect published GTFS timetable capacity. No ridership or unobserved demand is fabricated."
    )


class SanitizationRecord(BaseModel):
    """Sanitization log entry."""
    table: str
    column: str
    original_value: str
    sanitized_value: str
    issue_type: str


class ValidationIssueModel(BaseModel):
    """Validation issue or warning entry."""
    table: str
    severity: str
    message: str
    affected_rows: int


class DataQualityReportResponse(BaseModel):
    """Detailed audit report on data sanitization and integrity."""
    quality_score: float
    passed_validation: bool
    agency_count: int
    route_count: int
    stop_count: int
    trip_count: int
    stop_times_count: int
    calendar_count: int
    missing_files: List[str] = []
    times_exceeding_24h_count: int = 0
    orphan_trips_count: int = 0
    invalid_coordinates_count: int = 0
    out_of_bounds_stops_count: int = 0
    sanitization_count: int = 0
    sanitization_events: List[SanitizationRecord] = []
    validation_issues: List[ValidationIssueModel] = []

    # Frontend compatibility fields
    total_records: Dict[str, int] = {}
    valid_records: Dict[str, int] = {}
    invalid_records: Dict[str, int] = {}
    duplicate_records: Dict[str, int] = {}
    missing_values: Dict[str, Dict[str, int]] = {}
    processing_status: str = "completed"
    issues: List[str] = []
    available_files: List[str] = []
