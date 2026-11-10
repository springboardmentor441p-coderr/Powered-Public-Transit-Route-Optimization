"""Route Clustering Module for RouteRanker.

Applies K-Means and DBSCAN unsupervised learning algorithms to group routes
based strictly on operational and schedule characteristics.
Generates cluster profiles and 2D PCA projections for dashboard visualization.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

CLUSTER_FEATURES: List[str] = [
    "total_trips",
    "service_span_hours",
    "avg_trip_duration_min",
    "stop_count",
    "estimated_distance_km",
    "avg_headway_min",
    "peak_ratio",
    "avg_speed_kmh",
]


@dataclass
class ClusterProfile:
    """Statistical summary of a single route cluster."""
    cluster_id: int
    name: str
    description: str
    route_count: int
    avg_trips: float
    avg_headway_min: float
    avg_span_hours: float
    avg_duration_min: float
    avg_distance_km: float
    avg_speed_kmh: float
    key_characteristics: List[str] = field(default_factory=list)


class RouteClusteringPipeline:
    """Manages scaling, model training, and cluster profiling for transit routes."""

    def __init__(self, models_dir: Optional[Path] = None) -> None:
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.models_dir = models_dir or (self.project_root / "data" / "models")
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.scaler: Optional[StandardScaler] = None
        self.kmeans_model: Optional[KMeans] = None
        self.dbscan_model: Optional[DBSCAN] = None
        self.pca_model: Optional[PCA] = None

    def prepare_data(self, features_df: pd.DataFrame) -> Tuple[np.ndarray, pd.DataFrame]:
        """Validate, impute, and extract feature matrix."""
        df = features_df.copy()
        for col in CLUSTER_FEATURES:
            if col not in df.columns:
                df[col] = 0.0
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        # Drop invalid rows if any
        x_raw = df[CLUSTER_FEATURES].values
        return x_raw, df

    def fit_kmeans(
        self,
        features_df: pd.DataFrame,
        n_clusters: int = 4,
        random_state: int = 42,
    ) -> Tuple[pd.DataFrame, List[ClusterProfile], Dict[str, Any]]:
        """Fit K-Means clustering, assign semantic names, and calculate PCA projection."""
        x_raw, df = self.prepare_data(features_df)

        self.scaler = StandardScaler()
        x_scaled = self.scaler.fit_transform(x_raw)

        self.kmeans_model = KMeans(
            n_clusters=n_clusters,
            init="k-means++",
            n_init=10,
            max_iter=300,
            random_state=random_state,
        )
        labels = self.kmeans_model.fit_predict(x_scaled)
        df["cluster_id"] = labels

        # PCA 2D projection for dashboard scatter plots
        self.pca_model = PCA(n_components=2, random_state=random_state)
        pca_coords = self.pca_model.fit_transform(x_scaled)
        df["pca_x"] = np.round(pca_coords[:, 0], 3)
        df["pca_y"] = np.round(pca_coords[:, 1], 3)

        # Generate cluster profiles and assign semantic names based on centroids
        profiles, cluster_name_map = self._profile_clusters(df, n_clusters)
        df["cluster_name"] = df["cluster_id"].map(cluster_name_map)

        # Save artifacts
        joblib.dump(self.scaler, self.models_dir / "scaler.joblib")
        joblib.dump(self.kmeans_model, self.models_dir / "kmeans_model.joblib")
        joblib.dump(self.pca_model, self.models_dir / "pca_model.joblib")

        metrics = {
            "inertia": round(float(self.kmeans_model.inertia_), 2),
            "n_clusters": n_clusters,
            "pca_explained_variance_ratio": [round(float(v), 4) for v in self.pca_model.explained_variance_ratio_],
        }

        logger.info(f"K-Means fitted successfully with k={n_clusters}, inertia={metrics['inertia']}")
        return df, profiles, metrics

    def fit_dbscan(
        self,
        features_df: pd.DataFrame,
        eps: float = 1.2,
        min_samples: int = 5,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Fit DBSCAN clustering to identify density clusters and operational outliers."""
        x_raw, df = self.prepare_data(features_df)

        if self.scaler is None:
            self.scaler = StandardScaler()
            x_scaled = self.scaler.fit_transform(x_raw)
        else:
            x_scaled = self.scaler.transform(x_raw)

        self.dbscan_model = DBSCAN(eps=eps, min_samples=min_samples)
        labels = self.dbscan_model.fit_predict(x_scaled)
        df["dbscan_cluster"] = labels

        joblib.dump(self.dbscan_model, self.models_dir / "dbscan_model.joblib")

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = int(np.sum(labels == -1))

        metrics = {
            "n_clusters": n_clusters,
            "noise_routes_count": n_noise,
            "eps": eps,
            "min_samples": min_samples,
        }
        logger.info(f"DBSCAN fitted: {n_clusters} clusters, {n_noise} anomaly routes.")
        return df, metrics

    def _profile_clusters(
        self,
        df: pd.DataFrame,
        n_clusters: int,
    ) -> Tuple[List[ClusterProfile], Dict[int, str]]:
        """Generate human-readable profiles and assign semantic names to clusters."""
        profiles: List[ClusterProfile] = []
        name_map: Dict[int, str] = {}

        cluster_stats = []
        for c_id in range(n_clusters):
            c_df = df[df["cluster_id"] == c_id]
            stats = {
                "cluster_id": c_id,
                "count": len(c_df),
                "avg_trips": float(c_df["total_trips"].mean()) if len(c_df) else 0.0,
                "avg_headway": float(c_df["avg_headway_min"].mean()) if len(c_df) else 0.0,
                "avg_span": float(c_df["service_span_hours"].mean()) if len(c_df) else 0.0,
                "avg_duration": float(c_df["avg_trip_duration_min"].mean()) if len(c_df) else 0.0,
                "avg_dist": float(c_df["estimated_distance_km"].mean()) if len(c_df) else 0.0,
                "avg_speed": float(c_df["avg_speed_kmh"].mean()) if len(c_df) else 0.0,
            }
            cluster_stats.append(stats)

        # Sort clusters by trip volume to assign meaningful labels
        sorted_by_trips = sorted(cluster_stats, key=lambda x: x["avg_trips"], reverse=True)

        assigned_labels = {}
        for rank, s in enumerate(sorted_by_trips):
            c_id = s["cluster_id"]
            if rank == 0 and s["avg_trips"] > 25:
                name = "High-Frequency Trunk"
                desc = "Major transit corridors operating high daily trip volumes with short headways."
                chars = ["High trip volume", "Frequent departures", "Extended span"]
            elif s["avg_dist"] > 25.0:
                name = "Long-Distance Regional"
                desc = "Routes covering longer regional distances connecting outer suburbs to core."
                chars = ["High distance", "Long trip duration", "Suburban connectivity"]
            elif s["avg_trips"] >= 10:
                name = "Standard Local Feeder"
                desc = "Regular urban collector routes providing steady intermediate connectivity."
                chars = ["Moderate frequency", "Standard route length", "Balanced daily span"]
            else:
                name = "Low-Frequency / Targeted"
                desc = "Specialized or peak-targeted services operating limited scheduled runs."
                chars = ["Low scheduled trips", "Wider headways", "Niche coverage"]

            # Ensure unique names
            final_name = name
            suffix = 2
            while final_name in assigned_labels.values():
                final_name = f"{name} {suffix}"
                suffix += 1

            assigned_labels[c_id] = final_name
            name_map[c_id] = final_name

            profile = ClusterProfile(
                cluster_id=c_id,
                name=final_name,
                description=desc,
                route_count=s["count"],
                avg_trips=round(s["avg_trips"], 1),
                avg_headway_min=round(s["avg_headway"], 1),
                avg_span_hours=round(s["avg_span"], 1),
                avg_duration_min=round(s["avg_duration"], 1),
                avg_distance_km=round(s["avg_dist"], 1),
                avg_speed_kmh=round(s["avg_speed"], 1),
                key_characteristics=chars,
            )
            profiles.append(profile)

        # Sort profiles by cluster_id
        profiles.sort(key=lambda p: p.cluster_id)
        return profiles, name_map

