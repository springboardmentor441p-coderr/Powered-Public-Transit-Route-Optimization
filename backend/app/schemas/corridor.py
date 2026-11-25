"""Pydantic v2 schemas for Phase 6.2 & 6.3 corridor topology and co-routing APIs."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta


class CorridorMethodologyMeta(BaseModel):
    """Provenance and metric-distinction metadata for corridor topology."""

    model_config = ConfigDict(extra="forbid")

    source_artifacts: List[str]
    metric_distinctions: str = (
        "Geographic buffer overlap (250m spatial corridor), discrete Frechet shape clustering, "
        "stop-set Jaccard similarity, shared consecutive stop sequences, and route-direction hub "
        "connectivity are reported separately and never merged into a single score."
    )


class CorridorClusterItem(BaseModel):
    """Single directional pattern within a corridor cluster."""

    model_config = ConfigDict(extra="forbid")

    pattern_id: str
    route_id: str
    direction_id: int
    route_short_name: Optional[str] = None
    route_long_name: Optional[str] = None
    is_rail: Optional[bool] = None
    operational_cluster_label: Optional[str] = None
    k: int = Field(..., ge=2, le=12)
    cluster_type: Literal["geographic_buffer_overlap", "geometric_frechet_shape"]
    cluster_id: int
    buffer_cluster_id: int
    frechet_cluster_id: int
    length_km: Optional[float] = Field(None, ge=0.0)
    scheduled_trip_count: Optional[int] = Field(None, ge=0)
    hub_stop_count: Optional[int] = Field(None, ge=0)
    hub_stop_ratio: Optional[float] = Field(None, ge=0.0, le=1.0)


class CorridorClusterListResponse(BaseModel):
    """Response schema for GET /api/v1/corridors/clusters."""

    model_config = ConfigDict(extra="forbid")

    k: int
    cluster_type: Literal["geographic_buffer_overlap", "geometric_frechet_shape"]
    data: List[CorridorClusterItem]
    pagination: PaginationMeta
    filters: Dict[str, Any] = Field(default_factory=dict)
    methodology: CorridorMethodologyMeta


class CoRoutingPeerItem(BaseModel):
    """Co-routing relationship between a pattern and a peer pattern under a specific metric."""

    model_config = ConfigDict(extra="forbid")

    peer_pattern_id: str
    peer_route_id: str
    peer_direction_id: Optional[int] = None
    similarity_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    metric_type: Literal["geographic_buffer_overlap", "stop_set_jaccard_similarity"]


class SharedStopSequenceItem(BaseModel):
    """Shared consecutive stop sequence between two route-direction patterns."""

    model_config = ConfigDict(extra="forbid")

    pattern_a: str
    pattern_b: str
    peer_pattern_id: str
    peer_route_id: str
    sequence_length: int = Field(..., ge=1)
    start_stop_id: str
    end_stop_id: str
    shared_stops: List[str]


class PatternCoRoutingProfile(BaseModel):
    """Directional co-routing profile preserving distinct spatial and stop metrics."""

    model_config = ConfigDict(extra="forbid")

    pattern_id: str
    route_id: str
    direction_id: int
    length_km: Optional[float] = Field(None, ge=0.0)
    scheduled_trip_count: Optional[int] = Field(None, ge=0)
    hub_stop_count: Optional[int] = Field(None, ge=0)
    hub_stop_ratio: Optional[float] = Field(None, ge=0.0, le=1.0)
    buffer_cluster_k3: Optional[int] = None
    frechet_cluster_k3: Optional[int] = None
    missing_buffer_entries_count: int = Field(0, ge=0)
    missing_jaccard_entries_count: int = Field(0, ge=0)
    geographic_overlap_peers: List[CoRoutingPeerItem]
    stop_jaccard_peers: List[CoRoutingPeerItem]
    shared_consecutive_sequences: List[SharedStopSequenceItem]


class RouteCoRoutingResponse(BaseModel):
    """Response schema for GET /api/v1/corridors/routes/{route_id}/co-routing."""

    model_config = ConfigDict(extra="forbid")

    route_id: str
    route_short_name: str
    route_long_name: str
    is_rail: bool
    operational_cluster_label: Optional[str] = None
    corridor_duplication_index: Optional[float] = None
    patterns: List[PatternCoRoutingProfile]
    methodology: CorridorMethodologyMeta
