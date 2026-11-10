"""Pydantic Schemas for Route Overlap Endpoints."""

from __future__ import annotations

from typing import Any, List, Optional
from app.schemas.common import BaseModel, Field


class OverlapPairItem(BaseModel):
    """Pair of routes sharing stop infrastructure."""
    route_id_a: str
    route_id_b: str
    route_short_name_a: str
    route_short_name_b: str
    shared_stops: int
    stops_count_a: int
    stops_count_b: int
    overlap_ratio_a: float
    overlap_ratio_b: float
    jaccard_overlap_pct: float

    # Frontend compatibility fields
    route_a_id: str = ""
    route_a_name: str = ""
    route_b_id: str = ""
    route_b_name: str = ""
    total_stops: int = 0
    jaccard_similarity: float = 0.0

    def __init__(self, **data: Any) -> None:
        if "route_id_a" in data and "route_a_id" not in data:
            data["route_a_id"] = str(data["route_id_a"])
        if "route_id_b" in data and "route_b_id" not in data:
            data["route_b_id"] = str(data["route_id_b"])
        if "route_short_name_a" in data and "route_a_name" not in data:
            data["route_a_name"] = str(data["route_short_name_a"])
        if "route_short_name_b" in data and "route_b_name" not in data:
            data["route_b_name"] = str(data["route_short_name_b"])
        if "jaccard_overlap_pct" in data and "jaccard_similarity" not in data:
            data["jaccard_similarity"] = round(float(data["jaccard_overlap_pct"]) / 100.0, 3)
        if "stops_count_a" in data and "stops_count_b" in data and "total_stops" not in data:
            data["total_stops"] = int(data["stops_count_a"]) + int(data["stops_count_b"]) - int(data.get("shared_stops", 0))
        super().__init__(**data)


class RouteOverlapDetailResponse(BaseModel):
    """Detailed overlap analysis for a single route with all intersecting routes."""
    route_id: str
    route_short_name: str
    route_name: str = ""
    total_stops: int
    overlapping_routes_count: int
    highest_jaccard_overlap_pct: float
    overlapping_routes: List[OverlapPairItem] = []
    schedule_derived_notice: str = (
        "Overlap calculated as Jaccard stop similarity = shared_stops / (stops_a + stops_b - shared_stops)."
    )

    def __init__(self, **data: Any) -> None:
        if "route_short_name" in data and "route_name" not in data:
            data["route_name"] = str(data["route_short_name"])
        super().__init__(**data)
