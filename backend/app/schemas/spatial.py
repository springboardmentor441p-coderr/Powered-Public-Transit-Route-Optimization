"""Pydantic v2 schemas for Phase 6.1 spatial hub rankings and DBSCAN clusters."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta


class CoordinatePair(BaseModel):
    """Leaflet-compatible WGS84 coordinate pair."""

    model_config = ConfigDict(extra="forbid")

    lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="WGS84 latitude")
    lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description="WGS84 longitude")
    coordinates_available: bool = Field(..., description="Whether valid coordinates exist")


class BoundingBoxMeta(BaseModel):
    """Geographic bounding box filter metadata."""

    model_config = ConfigDict(extra="forbid")

    min_lat: float = Field(..., ge=-90.0, le=90.0)
    min_lon: float = Field(..., ge=-180.0, le=180.0)
    max_lat: float = Field(..., ge=-90.0, le=90.0)
    max_lon: float = Field(..., ge=-180.0, le=180.0)


class HubRankingItem(BaseModel):
    """Ranked transit hub item for GET /api/v1/spatial/hubs/top."""

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(..., ge=1)
    stop_id: str
    stop_name: str
    coordinates: CoordinatePair
    config: str
    hub_score: float
    total_visits: int = Field(..., ge=0)
    routes_served: int = Field(..., ge=0)
    attributed_demand_proxy: float = Field(
        ...,
        ge=0.0,
        description="Route-level demand proxy attributed to stop; not actual stop-level boardings",
    )
    demand_intensity: float = Field(..., ge=0.0)


class SpatialMethodologyMeta(BaseModel):
    """Source and methodology provenance for spatial responses."""

    model_config = ConfigDict(extra="forbid")

    source_artifact: str
    demand_proxy_note: str = (
        "attributed_demand reflects route-level ridership attributed to stops by visit share, "
        "not actual stop-level APC/turnstile boarding counts."
    )


class TopHubsResponse(BaseModel):
    """Response schema for GET /api/v1/spatial/hubs/top."""

    model_config = ConfigDict(extra="forbid")

    config: str
    total_top_hubs: int
    data: List[HubRankingItem]
    pagination: PaginationMeta
    methodology: SpatialMethodologyMeta


class SpatialStopHubItem(BaseModel):
    """Unified spatial stop/hub item with DBSCAN cluster and hub eligibility status."""

    model_config = ConfigDict(extra="forbid")

    stop_id: str
    stop_name: str
    coordinates: CoordinatePair
    dbscan_cluster: int
    is_noise_point: bool
    hub_ranking_eligible: bool
    rank: Optional[int] = Field(None, ge=1)
    hub_score: Optional[float] = None
    total_visits: Optional[int] = Field(None, ge=0)
    routes_served: Optional[int] = Field(None, ge=0)
    attributed_demand_proxy: Optional[float] = Field(None, ge=0.0)
    demand_intensity: Optional[float] = Field(None, ge=0.0)


class SpatialHubsListResponse(BaseModel):
    """Response schema for GET /api/v1/spatial/hubs."""

    model_config = ConfigDict(extra="forbid")

    config: str
    data: List[SpatialStopHubItem]
    pagination: PaginationMeta
    bounding_box: Optional[BoundingBoxMeta] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    methodology: SpatialMethodologyMeta


class ClusterSummaryResponse(BaseModel):
    """Response schema for GET /api/v1/spatial/clusters/summary."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    representative_service_date: str
    demand_attribution_period: str
    boarding_stops_input_count: int
    active_stop_visits_count: int
    dbscan_parameters: Dict[str, Any]
    dbscan_cluster_count: int
    dbscan_noise_stop_count: int
    dbscan_chained_cluster_count: int
    kmeans_parameters: Dict[str, Any]
    kmeans_eligible_stops_count: int
    hub_ranking_sensitivity: Dict[str, Any]
    coverage_metrics: Dict[str, Any]
    methodology: SpatialMethodologyMeta
