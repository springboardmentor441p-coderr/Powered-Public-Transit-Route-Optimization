"""Pydantic v2 schemas for canonical CTA route directory and feature profiles."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta


class RouteSummaryItem(BaseModel):
    """Summary representation of a canonical CTA transit route."""

    model_config = ConfigDict(extra="forbid")

    route_id: str = Field(..., description="Canonical route identifier")
    route_short_name: str = Field(..., description="Short route label")
    route_long_name: str = Field(..., description="Descriptive route name")
    route_type: int = Field(..., description="GTFS route_type (3=Bus, 1=Rail)")
    is_rail: bool = Field(..., description="Whether the route is a heavy rail line")
    operational_cluster: Optional[str] = Field(None, description="Operational typology label")
    regional_partition: Optional[str] = Field(None, description="Geographic partition")
    scheduled_trips: int = Field(..., ge=0, description="Daily scheduled trips")
    service_span_hours: float = Field(..., ge=0.0, description="Daily operating span in hours")
    am_headway_min: Optional[float] = Field(None, description="AM peak headway in minutes (null if unavailable)")
    forecasted_daily_demand: Optional[float] = Field(
        None, description="Forecasted daily demand (null for rail lines)"
    )


class RouteListResponse(BaseModel):
    """Paginated response for GET /api/v1/routes."""

    model_config = ConfigDict(extra="forbid")

    data: List[RouteSummaryItem]
    pagination: PaginationMeta
    filters: Dict[str, Any] = Field(default_factory=dict)


class RouteOperationalMetrics(BaseModel):
    """Operational supply metrics for a route."""

    model_config = ConfigDict(extra="forbid")

    scheduled_trips: int
    service_span_hours: float
    am_headway_min: Optional[float] = None
    route_length_km: float
    unique_stops_count: int
    operational_cluster_k3: Optional[int] = None
    operational_cluster_label: Optional[str] = None


class RouteDemandMetrics(BaseModel):
    """Demand and ridership metrics (unavailable/null for rail lines by design)."""

    model_config = ConfigDict(extra="forbid")

    demand_metrics_available: bool
    historical_mean_daily_rides: Optional[float] = None
    forecasted_daily_demand: Optional[float] = None
    rides_per_trip: Optional[float] = None
    load_intensity_factor: Optional[float] = None


class RouteHubMetrics(BaseModel):
    """Transit hub connectivity metrics."""

    model_config = ConfigDict(extra="forbid")

    hub_stop_count: int
    hub_stop_ratio: float
    hub_weighted_importance: float
    hub_connectivity_index: float


class RouteCorridorMetrics(BaseModel):
    """Corridor similarity and co-routing metrics."""

    model_config = ConfigDict(extra="forbid")

    max_corridor_overlap: float
    mean_corridor_overlap: float
    shared_consecutive_stop_count: int
    corridor_duplication_ratio: float
    corridor_duplication_index: float


class RouteDetailResponse(BaseModel):
    """Detailed feature profile for GET /api/v1/routes/{route_id}."""

    model_config = ConfigDict(extra="forbid")

    route_id: str
    route_short_name: str
    route_long_name: str
    route_type: int
    is_rail: bool
    regional_partition: Optional[str] = None
    operational: RouteOperationalMetrics
    demand: RouteDemandMetrics
    hubs: RouteHubMetrics
    corridor: RouteCorridorMetrics
