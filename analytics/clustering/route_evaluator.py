"""
AI_RouteRanker - Phase 6.2 Route Evaluator Module
Implements:
  1. Route-Level Operational KMeans Clustering across K in [3, 7]
  2. Hierarchical Agglomerative Clustering on Precomputed Route Distance Matrices (K in [2, 12])
  3. Precomputed Silhouette Scoring and Degeneracy Handling
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score


class RouteEvaluator:
    """
    Evaluates route-level operational typology and route-direction spatial corridor clustering.
    """

    OPERATIONAL_K_RANGE: List[int] = [3, 4, 5, 6, 7]
    CORRIDOR_K_RANGE: List[int] = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

    @classmethod
    def evaluate_operational_kmeans(
        cls,
        feature_df: pd.DataFrame,
        feature_cols: List[str],
        k_values: Optional[List[int]] = None,
        random_state: int = 42,
        n_init: int = 10,
    ) -> Dict[str, Any]:
        """
        Executes and evaluates operational KMeans across K in [3, 7].

        Args:
            feature_df: DataFrame of route operational features.
            feature_cols: List of 5 operational feature column names.
            k_values: List of candidate K values (default [3, 4, 5, 6, 7]).
            random_state: Fixed random seed (default 42).
            n_init: Number of initializations (default 10).

        Returns:
            Dictionary with candidate models, assignments, inertias, and silhouette scores.
        """
        k_list = k_values if k_values is not None else cls.OPERATIONAL_K_RANGE

        # Drop any row with NaNs in feature_cols
        valid_df = feature_df.dropna(subset=feature_cols).copy().reset_index(drop=True)
        n_routes = len(valid_df)

        if n_routes < max(k_list):
            raise ValueError(f"Insufficient routes ({n_routes}) to evaluate max K={max(k_list)}!")

        raw_X = valid_df[feature_cols].values
        scaler = StandardScaler()
        scaled_X = scaler.fit_transform(raw_X)

        candidate_results = {}
        evaluation_rows = []

        for k in k_list:
            km = KMeans(n_clusters=k, random_state=random_state, n_init=n_init)
            labels = km.fit_predict(scaled_X)
            inertia = float(km.inertia_)

            # Compute silhouette
            n_labels = len(np.unique(labels))
            if 2 <= n_labels <= n_routes - 1:
                sil = float(silhouette_score(scaled_X, labels))
                status = "VALID"
            else:
                sil = np.nan
                status = "NOT_COMPUTABLE"

            # Route type composition per cluster
            cluster_summaries = []
            for c in range(k):
                c_mask = (labels == c)
                c_df = valid_df[c_mask]
                n_c = len(c_df)
                bus_count = int((c_df["route_type"] == 3).sum()) if "route_type" in c_df.columns else 0
                rail_count = int((c_df["route_type"] == 1).sum()) if "route_type" in c_df.columns else 0
                
                feat_means = {col: float(c_df[col].mean()) for col in feature_cols}
                feat_medians = {col: float(c_df[col].median()) for col in feature_cols}

                cluster_summaries.append({
                    "cluster_id": c,
                    "stop_count": n_c,
                    "bus_count": bus_count,
                    "rail_count": rail_count,
                    "means": feat_means,
                    "medians": feat_medians,
                })

            candidate_results[k] = {
                "k": k,
                "model": km,
                "labels": labels,
                "inertia": inertia,
                "silhouette": sil,
                "status": status,
                "cluster_summaries": cluster_summaries,
            }

            evaluation_rows.append({
                "k": k,
                "inertia": inertia,
                "silhouette": sil,
                "status": status,
            })

        return {
            "scaler": scaler,
            "scaled_features": scaled_X,
            "valid_routes_df": valid_df,
            "candidate_results": candidate_results,
            "evaluation_summary": pd.DataFrame(evaluation_rows),
        }

    @classmethod
    def evaluate_hierarchical_corridors(
        cls,
        distance_matrix: np.ndarray,
        pattern_ids: List[str],
        k_values: Optional[List[int]] = None,
        linkage: str = "average",
    ) -> Dict[str, Any]:
        """
        Executes and evaluates Agglomerative Hierarchical Clustering on precomputed distance matrix.

        Args:
            distance_matrix: (P, P) symmetric distance matrix with zeros on diagonal.
            pattern_ids: List of pattern IDs corresponding to matrix rows/columns.
            k_values: Candidate cluster counts (default [2, ..., 12]).
            linkage: Linkage criterion (default 'average').

        Returns:
            Dictionary with candidate cluster assignments and precomputed silhouette scores.
        """
        p = len(pattern_ids)
        max_k_possible = min(12, p - 1) if p > 2 else 2
        k_list = [k for k in (k_values if k_values is not None else cls.CORRIDOR_K_RANGE) if 2 <= k <= max_k_possible]

        candidate_results = {}
        evaluation_rows = []

        for k in k_list:
            agg = AgglomerativeClustering(
                n_clusters=k,
                metric="precomputed",
                linkage=linkage
            )
            labels = agg.fit_predict(distance_matrix)

            n_labels = len(np.unique(labels))
            if 2 <= n_labels <= p - 1:
                sil = float(silhouette_score(distance_matrix, labels, metric="precomputed"))
                status = "VALID"
            else:
                sil = np.nan
                status = "NOT_COMPUTABLE"

            cluster_sizes = np.bincount(labels).tolist()

            candidate_results[k] = {
                "k": k,
                "labels": labels,
                "silhouette": sil,
                "status": status,
                "cluster_sizes": cluster_sizes,
            }

            evaluation_rows.append({
                "k": k,
                "silhouette": sil,
                "status": status,
                "max_cluster_size": max(cluster_sizes) if cluster_sizes else 0,
                "min_cluster_size": min(cluster_sizes) if cluster_sizes else 0,
            })

        return {
            "pattern_ids": pattern_ids,
            "candidate_results": candidate_results,
            "evaluation_summary": pd.DataFrame(evaluation_rows),
        }
