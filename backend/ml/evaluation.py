"""Clustering Evaluation Module for RouteRanker.

Evaluates K-Means clustering quality across candidate values of k:
- Elbow Method (Inertia)
- Silhouette Score
- Davies-Bouldin Index
- Calinski-Harabasz Index
Recommends optimal number of clusters based on schedule feature separation.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from ml.clustering import CLUSTER_FEATURES

logger = logging.getLogger(__name__)


@dataclass
class KEvaluationPoint:
    """Metrics for a single candidate k."""
    k: int
    inertia: float
    silhouette_score: float
    davies_bouldin_index: float
    calinski_harabasz_score: float


@dataclass
class ClusterEvaluationResult:
    """Complete evaluation report across tested cluster numbers."""
    evaluation_points: List[KEvaluationPoint]
    recommended_k: int
    recommendation_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluation_points": [asdict(p) for p in self.evaluation_points],
            "recommended_k": self.recommended_k,
            "recommendation_reason": self.recommendation_reason,
        }


class ClusterEvaluator:
    """Evaluates clustering quality across different values of k."""

    def __init__(self, k_range: Tuple[int, int] = (2, 8)) -> None:
        self.k_min = k_range[0]
        self.k_max = k_range[1]

    def evaluate(
        self,
        features_df: pd.DataFrame,
        sample_size: int = 2000,
        random_state: int = 42,
    ) -> ClusterEvaluationResult:
        """Calculate inertia and separation metrics for k in [k_min, k_max]."""
        # Prepare and scale feature matrix
        x_raw = features_df[CLUSTER_FEATURES].fillna(0.0).values
        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(x_raw)

        # For silhouette calculation on large datasets, subsample deterministically
        n_samples = len(x_scaled)
        if n_samples > sample_size:
            np.random.seed(random_state)
            idx = np.random.choice(n_samples, sample_size, replace=False)
            x_eval = x_scaled[idx]
        else:
            x_eval = x_scaled

        points: List[KEvaluationPoint] = []
        best_silhouette = -1.0
        recommended_k = 4

        for k in range(self.k_min, self.k_max + 1):
            km = KMeans(n_clusters=k, init="k-means++", n_init=5, random_state=random_state)
            labels = km.fit_predict(x_scaled)
            inertia = round(float(km.inertia_), 2)

            # Metrics
            if len(x_eval) < len(x_scaled):
                labels_eval = km.predict(x_eval)
            else:
                labels_eval = labels

            sil = round(float(silhouette_score(x_eval, labels_eval)), 4)
            db = round(float(davies_bouldin_score(x_scaled, labels)), 4)
            ch = round(float(calinski_harabasz_score(x_scaled, labels)), 2)

            points.append(
                KEvaluationPoint(
                    k=k,
                    inertia=inertia,
                    silhouette_score=sil,
                    davies_bouldin_index=db,
                    calinski_harabasz_score=ch,
                )
            )

            if sil > best_silhouette:
                best_silhouette = sil
                recommended_k = k

        reason = (
            f"k={recommended_k} achieves the highest silhouette score ({best_silhouette}) "
            "and favorable cluster separation across schedule span, trip volume, and headway."
        )

        return ClusterEvaluationResult(
            evaluation_points=points,
            recommended_k=recommended_k,
            recommendation_reason=reason,
        )

