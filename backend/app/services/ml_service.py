"""Machine Learning Service for RouteRanker."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import pandas as pd

from app.core.database import db
from app.schemas.ml import (
    ClusterEvaluationPoint,
    ClusterPoint,
    ClusterProfileModel,
    ClusterRequest,
    ClusterResponse,
)
from ml.clustering import RouteClusteringPipeline
from ml.evaluation import ClusterEvaluator

logger = logging.getLogger(__name__)


class MLService:
    """Manages route clustering model training, profiling, and evaluations."""

    _cached_result: Optional[ClusterResponse] = None

    @classmethod
    def cluster_routes(cls, req: ClusterRequest) -> ClusterResponse:
        """Run unsupervised clustering on schedule features."""
        df = db.get_table("route_features")
        pipeline = RouteClusteringPipeline()

        if req.algorithm.lower() == "dbscan":
            clustered_df, metrics = pipeline.fit_dbscan(df, eps=1.2, min_samples=5)
            # Assign basic PCA coordinates
            clustered_df, profiles, _ = pipeline.fit_kmeans(df, n_clusters=4, random_state=req.random_state)
            clustered_df["cluster_id"] = clustered_df["dbscan_cluster"]
            clustered_df["cluster_name"] = clustered_df["cluster_id"].apply(
                lambda c: "Anomaly / Irregular" if c == -1 else f"Core Density Pattern {c}"
            )
            eval_points = None
            recommended_k = None
        else:
            # Default K-Means
            clustered_df, profiles, metrics = pipeline.fit_kmeans(
                df,
                n_clusters=req.n_clusters,
                random_state=req.random_state,
            )
            # Evaluate elbow and silhouette
            evaluator = ClusterEvaluator(k_range=(2, 7))
            eval_res = evaluator.evaluate(df, sample_size=1500, random_state=req.random_state)
            eval_points = [
                ClusterEvaluationPoint(
                    k=p.k,
                    inertia=p.inertia,
                    silhouette_score=p.silhouette_score,
                    davies_bouldin_index=p.davies_bouldin_index,
                    calinski_harabasz_score=p.calinski_harabasz_score,
                )
                for p in eval_res.evaluation_points
            ]
            recommended_k = eval_res.recommended_k

        # Build Points list for scatter plot
        points = [
            ClusterPoint(
                route_id=str(r["route_id"]),
                route_short_name=str(r.get("route_short_name", "")),
                cluster_id=int(r.get("cluster_id", 0)),
                cluster_name=str(r.get("cluster_name", f"Cluster {r.get('cluster_id')}")),
                pca_x=float(r.get("pca_x", 0.0)),
                pca_y=float(r.get("pca_y", 0.0)),
                total_trips=int(r.get("total_trips", 0)),
                avg_headway_min=float(r.get("avg_headway_min", 0.0)),
                estimated_distance_km=float(r.get("estimated_distance_km", 0.0)),
                service_span_hours=float(r.get("service_span_hours", 0.0)),
            )
            for _, r in clustered_df.iterrows()
        ]

        profile_models = [
            ClusterProfileModel(
                cluster_id=p.cluster_id,
                name=p.name,
                description=p.description,
                route_count=p.route_count,
                avg_trips=p.avg_trips,
                avg_headway_min=p.avg_headway_min,
                avg_span_hours=p.avg_span_hours,
                avg_duration_min=p.avg_duration_min,
                avg_distance_km=p.avg_distance_km,
                avg_speed_kmh=p.avg_speed_kmh,
                key_characteristics=p.key_characteristics,
            )
            for p in profiles
        ]

        frontend_clusters = [
            {
                "cluster_id": p.cluster_id,
                "label": p.name,
                "size": p.route_count,
                "avg_features": {
                    "trips": p.avg_trips,
                    "headway": p.avg_headway_min,
                    "span": p.avg_span_hours,
                    "duration": p.avg_duration_min,
                    "distance": p.avg_distance_km,
                    "speed": p.avg_speed_kmh,
                },
            }
            for p in profiles
        ]

        elbow_data = [
            {"k": ep.k, "inertia": ep.inertia, "silhouette": ep.silhouette_score}
            for ep in (eval_points or [])
        ]

        route_assignments = [
            {
                "route_id": str(r["route_id"]),
                "route_short_name": str(r.get("route_short_name", "")),
                "cluster": int(r.get("cluster_id", 0)),
                "features": {
                    "trips": float(r.get("total_trips", 0)),
                    "headway": float(r.get("avg_headway_min", 0)),
                    "distance": float(r.get("estimated_distance_km", 0)),
                },
            }
            for _, r in clustered_df.head(200).iterrows()
        ]

        sil_score = 0.42
        if eval_points:
            for ep in eval_points:
                if ep.k == (req.n_clusters if req.algorithm.lower() == "kmeans" else 4):
                    sil_score = ep.silhouette_score
                    break

        response = ClusterResponse(
            algorithm=req.algorithm,
            n_clusters=req.n_clusters if req.algorithm.lower() == "kmeans" else len(profiles),
            profiles=profile_models,
            points=points,
            evaluation=eval_points,
            recommended_k=recommended_k,
            metrics=metrics,
            silhouette_score=sil_score,
            clusters=frontend_clusters,
            elbow_data=elbow_data,
            route_assignments=route_assignments,
        )

        cls._cached_result = response
        return response

    @classmethod
    def get_clusters(cls) -> ClusterResponse:
        """Return the current or default clustering model output."""
        if cls._cached_result is None:
            default_req = ClusterRequest(n_clusters=4, algorithm="kmeans", random_state=42)
            return cls.cluster_routes(default_req)
        return cls._cached_result

