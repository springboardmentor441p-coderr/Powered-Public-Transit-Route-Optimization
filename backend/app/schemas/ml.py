"""Pydantic Schemas for Machine Learning Endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.schemas.common import BaseModel, Field


class ClusterRequest(BaseModel):
    """Parameters for running clustering."""
    n_clusters: int = Field(default=4, ge=2, le=10)
    algorithm: str = Field(default="kmeans")
    random_state: int = 42


class ClusterPoint(BaseModel):
    """2D projected route point for visualization."""
    route_id: str
    route_short_name: str
    cluster_id: int
    cluster_name: str
    pca_x: float
    pca_y: float
    total_trips: int
    avg_headway_min: float
    estimated_distance_km: float
    service_span_hours: float


class ClusterProfileModel(BaseModel):
    """Statistical summary of a route cluster."""
    cluster_id: int
    name: str
    label: str = ""
    description: str
    route_count: int
    size: int = 0
    avg_trips: float
    avg_headway_min: float
    avg_span_hours: float
    avg_duration_min: float
    avg_distance_km: float
    avg_speed_kmh: float
    avg_features: Dict[str, float] = {}
    key_characteristics: List[str] = []

    def __init__(self, **data: Any) -> None:
        if "name" in data and "label" not in data:
            data["label"] = str(data["name"])
        if "route_count" in data and "size" not in data:
            data["size"] = int(data["route_count"])
        if "avg_features" not in data or not data["avg_features"]:
            data["avg_features"] = {
                "trips": float(data.get("avg_trips", 0)),
                "headway": float(data.get("avg_headway_min", 0)),
                "span": float(data.get("avg_span_hours", 0)),
                "duration": float(data.get("avg_duration_min", 0)),
                "distance": float(data.get("avg_distance_km", 0)),
                "speed": float(data.get("avg_speed_kmh", 0)),
            }
        super().__init__(**data)


class ClusterEvaluationPoint(BaseModel):
    """Metrics for elbow curve and silhouette analysis."""
    k: int
    inertia: float
    silhouette_score: float
    silhouette: float = 0.0
    davies_bouldin_index: float
    calinski_harabasz_score: float

    def __init__(self, **data: Any) -> None:
        if "silhouette_score" in data and "silhouette" not in data:
            data["silhouette"] = float(data["silhouette_score"])
        super().__init__(**data)


class ClusterResponse(BaseModel):
    """Response containing clustering results and 2D projection."""
    algorithm: str
    n_clusters: int
    profiles: List[ClusterProfileModel] = []
    points: List[ClusterPoint] = []
    evaluation: Optional[List[ClusterEvaluationPoint]] = None
    recommended_k: Optional[int] = 4
    metrics: Dict[str, Any] = {}

    # Frontend compatibility fields
    silhouette_score: float = 0.42
    clusters: List[Dict[str, Any]] = []
    elbow_data: List[Dict[str, Any]] = []
    route_assignments: List[Dict[str, Any]] = []

    schedule_derived_notice: str = "Clustering is unsupervised and trained purely on scheduled timetable features."
