"""Explicit response models for the versioned RouteRanker API."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class RouteItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    route_id: str
    route_short_name: str | None = None
    route_long_name: str | None = None
    route_type: str | None = None
    trip_count: int | None = None
    stop_count: int | None = None
    template_week_trip_count: int | None = None
    average_first_stop_headway_seconds: float | None = None
    first_service_time: str | None = None
    last_service_time: str | None = None
    kmeans_cluster_id: int | None = None
    dbscan_cluster_id: int | None = None
    fit_status: str | None = None


class StopItem(BaseModel):
    stop_id: str
    stop_name: str | None = None
    stop_lat_value: float | None = None
    stop_lon_value: float | None = None
    trip_count: int | None = None
    route_count: int | None = None


class RouteFeature(BaseModel):
    model_config = ConfigDict(extra="allow")
    route_id: str
    total_scheduled_trip_records: int | None = None
    unique_stop_count: int | None = None
    average_first_stop_headway_seconds: float | None = None
    scheduled_service_span_seconds: float | None = None
    shared_stop_ratio: float | None = None


class RouteCluster(BaseModel):
    route_id: str
    kmeans_cluster_id: int | None = None
    dbscan_cluster_id: int | None = None
    fit_status: str


class StopRoute(BaseModel):
    route_id: str
    route_short_name: str | None = None
    route_long_name: str | None = None


class StopRouteCount(BaseModel):
    stop_id: str
    stop_name: str | None = None
    route_count: int = Field(ge=0)


class ScheduledHour(BaseModel):
    service_hour: int
    scheduled_trip_records: int


class SimilarityItem(BaseModel):
    route_id_a: str
    route_id_b: str
    shared_stop_count: int
    route_a_stop_count: int
    route_b_stop_count: int
    jaccard_similarity: float


class ErrorResponse(BaseModel):
    detail: str
    code: str


class CompareResponse(BaseModel):
    routes: list[RouteItem]
    compared_route_ids: list[str]
    note: str = "Comparisons describe supplied GTFS schedules and stop-network features."


class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    data: dict[str, Any]


class ClusterSummary(BaseModel):
    algorithm: str
    cluster_id: int
    route_count: int
    is_noise: bool = False
    profile: dict[str, Any] | None = None


class ModelMetric(BaseModel):
    algorithm: str
    n_clusters: int
    silhouette_score: float | None = None
    silhouette_sample_size: int | None = None
    davies_bouldin_index: float | None = None
    noise_count: int = 0
    inlier_count: int
    k: int | None = None
    eps: float | None = None
    min_samples: int | None = None


class ModelMetadata(BaseModel):
    model: str
    feature_columns: list[str]
    training_route_count: int | None = None
    selected_k: int | None = None
    eps: float | None = None
    min_samples: int | None = None
    new_route_behavior: str


class DatasetStatistics(BaseModel):
    gtfs_quality_status: str | None = None
    dataset_totals: dict[str, Any]
    scheduled_service_level: dict[str, Any]
    headway_diagnostics: dict[str, Any]
    time_of_day: dict[str, Any]
    data_quality: dict[str, Any]
    limitations: dict[str, Any]
    interpretation: str


class RouteStatistics(BaseModel):
    route_count: int
    routes_with_trips: int
    scheduled_trip_records: int
    median_stops_per_route: float | None


class StopStatistics(BaseModel):
    stop_count: int
    stops_with_scheduled_trips: int
    stops_served_by_routes: int
    median_routes_per_stop: float | None


class HeadwaySummary(BaseModel):
    route_id: str | None = None
    groups_with_estimates: int
    groups_without_estimates: int
    median_of_group_medians_seconds: float | None
    mean_of_group_means_seconds: float | None
    note: str
