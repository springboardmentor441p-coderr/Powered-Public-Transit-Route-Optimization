"""Pydantic Schemas for Stops Endpoints."""

from __future__ import annotations

from typing import Any, List, Optional
from app.schemas.common import BaseModel, Field


class StopItem(BaseModel):
    """Transit stop summary."""
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    routes_count: int = 0
    route_count: int = 0
    trips_per_day: int = 0
    is_transfer_hub: bool = False
    routes_served: Optional[str] = ""
    route_names: List[str] = []

    def __init__(self, **data: Any) -> None:
        if "routes_count" in data and "route_count" not in data:
            data["route_count"] = data["routes_count"]
        elif "route_count" in data and "routes_count" not in data:
            data["routes_count"] = data["route_count"]

        if "routes_served" in data and "route_names" not in data:
            data["route_names"] = [s.strip() for s in str(data["routes_served"]).split(",") if s.strip()]
        super().__init__(**data)


class StopDetailResponse(BaseModel):
    """Detailed transit stop coverage information."""
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    routes_count: int
    trips_per_day: int
    is_transfer_hub: bool
    routes_served_list: List[str] = []
    schedule_derived_notice: str = "Values derived from scheduled trips stopping at this station."
