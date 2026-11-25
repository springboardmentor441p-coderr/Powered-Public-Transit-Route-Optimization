"""Pydantic v2 schemas for multi-criteria rankings, explanations, and sensitivity."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta


class RankingPillars(BaseModel):
    """Hierarchical pillar score breakdown."""

    model_config = ConfigDict(extra="forbid")

    demand_pressure: float = Field(..., ge=0.0, le=1.0)
    service_provision: float = Field(..., ge=0.0, le=1.0)
    network_hubs: float = Field(..., ge=0.0, le=1.0)
    corridor_structure: float = Field(..., ge=0.0, le=1.0)


class RankingItem(BaseModel):
    """Single route evaluation within an isolated ranking track."""

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(..., ge=1)
    route_id: str
    route_short_name: str
    route_long_name: str
    is_rail: bool
    track: str
    profile: str
    overall_score: float = Field(..., ge=0.0, le=1.0)
    percentile_rank: float = Field(..., ge=0.0, le=100.0)
    topsis_score: float = Field(..., ge=0.0, le=1.0)
    topsis_rank: int = Field(..., ge=1)
    scheduled_trips: int = Field(..., ge=0)
    service_span_hours: float = Field(..., ge=0.0)
    am_headway_min: Optional[float] = None
    corridor_duplication_index: float
    operational_cluster: Optional[str] = None
    regional_partition: Optional[str] = None
    pillars: RankingPillars
    contributions: Dict[str, Optional[float]]
    original_weights: Dict[str, float]
    effective_weights: Dict[str, float]
    valid_weight_coverage: float = Field(..., ge=0.0, le=1.0)
    is_headway_missing: bool
    missing_criteria: List[str] = Field(default_factory=list)


class RankingListResponse(BaseModel):
    """Paginated ranking list for an isolated track."""

    model_config = ConfigDict(extra="forbid")

    track: str
    profile: str
    total_routes: int
    data: List[RankingItem]
    pagination: PaginationMeta
    filters: Dict[str, Any] = Field(default_factory=dict)


class FeatureDriver(BaseModel):
    """Single positive or negative criterion driver in a route explanation."""

    model_config = ConfigDict(extra="forbid")

    criterion: str
    feature_key: str
    contribution: float
    score: float


class RouteExplanationResponse(BaseModel):
    """Detailed natural-language explanation for a route's ranking."""

    model_config = ConfigDict(extra="forbid")

    route_id: str
    route_short_name: str
    route_long_name: str
    is_rail: bool
    operational_cluster_label: Optional[str] = None
    regional_partition: Optional[str] = None
    track: str
    profile: str
    overall_score: float = Field(..., ge=0.0, le=1.0)
    rank: int = Field(..., ge=1)
    total_routes: int = Field(..., ge=1)
    percentile_rank: float = Field(..., ge=0.0, le=100.0)
    topsis_score: float = Field(..., ge=0.0, le=1.0)
    topsis_rank: int = Field(..., ge=1)
    pillars: RankingPillars
    criterion_scores: Dict[str, Optional[float]]
    original_weights: Dict[str, float]
    effective_weights: Dict[str, float]
    contributions: Dict[str, Optional[float]]
    missing_criteria: List[str]
    is_headway_missing: bool
    valid_weight_coverage: float = Field(..., ge=0.0, le=1.0)
    top_positive_drivers: List[FeatureDriver]
    top_negative_drivers: List[FeatureDriver]
    narrative: str


class SensitivityScenarioItem(BaseModel):
    """Single OAT weight perturbation sensitivity scenario."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    track: str
    target_criterion: str
    delta: float
    spearman_rho: float
    mean_absolute_rank_shift: float
    max_rank_shift: int
    top_10_overlap: float
    top_20_overlap: float


class SensitivityListResponse(BaseModel):
    """Response for GET /api/v1/rankings/sensitivity."""

    model_config = ConfigDict(extra="forbid")

    total_scenarios: int
    data: List[SensitivityScenarioItem]
    filters: Dict[str, Any] = Field(default_factory=dict)
