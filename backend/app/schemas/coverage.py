"""Pydantic Schemas for Network Coverage Endpoints."""

from __future__ import annotations

from typing import Any, Dict, List
from app.schemas.common import BaseModel, Field
from app.schemas.stops import StopItem


class TransferHubItem(BaseModel):
    """Major transfer hub with high route connectivity."""
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    routes_count: int
    trips_per_day: int
    sample_routes: List[str] = []


class ServiceDensityDistribution(BaseModel):
    """Distribution of stops by number of serving routes."""
    single_route: int = 0
    two_to_four_routes: int = 0
    five_to_nine_routes: int = 0
    ten_plus_routes: int = 0


class CoverageSummaryResponse(BaseModel):
    """Network-wide geographic and stop service coverage summary."""
    total_stops: int
    total_transfer_hubs: int
    avg_routes_per_stop: float
    max_routes_at_single_stop: int
    density_distribution: ServiceDensityDistribution
    top_transfer_hubs: List[TransferHubItem] = []
    geographic_bounds: Dict[str, float] = {}

    # Frontend compatibility fields
    stops_single_route: int = 0
    stops_multi_route: int = 0
    max_routes_per_stop: int = 0
    top_shared_stops: List[Dict[str, Any]] = []

    schedule_derived_notice: str = "Coverage metrics calculated from timetable stop associations."
