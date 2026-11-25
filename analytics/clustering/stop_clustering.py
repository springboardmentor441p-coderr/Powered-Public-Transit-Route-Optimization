"""
AI_RouteRanker - Phase 6.1 Stop Clustering Module
Implements two-tier clustering:
  Tier 1: Geographic Spatial Clustering via DBSCAN (eps=300m, min_samples=2) with chaining diagnostics.
  Tier 2: Functional Stop Typology via K-Means (k in [3, 8]) with standardized feature vectors.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.preprocessing import StandardScaler


class StopClusterer:
    """
    Two-Tier Transit Stop Clustering Engine:
      1. Spatial Physical Clustering (DBSCAN) in projected meter space.
      2. Functional Operational Typology (KMeans) in standardized multi-attribute space.
    """

    DEFAULT_DBSCAN_EPS: float = 300.0  # meters
    DEFAULT_DBSCAN_MIN_SAMPLES: int = 2
    CHAINING_DIAMETER_THRESHOLD: float = 1500.0  # meters
    CHAINING_SIZE_THRESHOLD: int = 50  # stop count

    KMEANS_CANDIDATE_K: List[int] = [3, 4, 5, 6, 7, 8]
    DEFAULT_RANDOM_STATE: int = 42

    def __init__(
        self,
        eps: float = DEFAULT_DBSCAN_EPS,
        min_samples: int = DEFAULT_DBSCAN_MIN_SAMPLES,
        chaining_diam_thresh: float = CHAINING_DIAMETER_THRESHOLD,
        chaining_size_thresh: int = CHAINING_SIZE_THRESHOLD,
        random_state: int = DEFAULT_RANDOM_STATE,
    ):
        self.eps = float(eps)
        self.min_samples = int(min_samples)
        self.chaining_diam_thresh = float(chaining_diam_thresh)
        self.chaining_size_thresh = int(chaining_size_thresh)
        self.random_state = int(random_state)

    def run_spatial_dbscan(
        self,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        eps: Optional[float] = None,
        min_samples: Optional[int] = None,
    ) -> Tuple[np.ndarray, Dict[int, Dict[str, Any]]]:
        """
        Executes DBSCAN on projected metric coordinates (x, y).
        
        Args:
          x_coords: 1D array of projected Easting in meters.
          y_coords: 1D array of projected Northing in meters.
          eps: Spatial search radius in meters (default 300.0m).
          min_samples: Minimum points to form dense cluster (default 2).
          
        Returns:
          labels: 1D array of cluster labels (noise points assigned -1).
          diagnostics: Dict mapping cluster_id -> diagnostic dictionary containing:
            - stop_count (N_c)
            - diameter_meters
            - radius_of_gyration_meters
            - bbox_dx, bbox_dy
            - is_chained (bool)
        """
        eps_val = float(eps) if eps is not None else self.eps
        min_samp = int(min_samples) if min_samples is not None else self.min_samples

        coords = np.column_stack([x_coords, y_coords])
        db = DBSCAN(eps=eps_val, min_samples=min_samp, metric="euclidean")
        labels = db.fit_predict(coords)

        # Compute chaining diagnostics for non-noise clusters
        diagnostics = {}
        unique_clusters = [c for c in np.unique(labels) if c != -1]

        for cid in unique_clusters:
            idx = np.where(labels == cid)[0]
            cluster_coords = coords[idx]
            n_c = len(idx)

            # Center and bounding box
            center = np.mean(cluster_coords, axis=0)
            min_xy = np.min(cluster_coords, axis=0)
            max_xy = np.max(cluster_coords, axis=0)
            dx = float(max_xy[0] - min_xy[0])
            dy = float(max_xy[1] - min_xy[1])

            # Diameter: max pairwise distance
            # For efficiency on moderate cluster sizes:
            if n_c > 1:
                # Pairwise distance matrix within cluster
                diff = cluster_coords[:, np.newaxis, :] - cluster_coords[np.newaxis, :, :]
                dist_matrix = np.sqrt(np.sum(diff ** 2, axis=-1))
                diameter = float(np.max(dist_matrix))
            else:
                diameter = 0.0

            # Radius of gyration
            rg = float(np.sqrt(np.mean(np.sum((cluster_coords - center) ** 2, axis=1))))

            is_chained = (diameter > self.chaining_diam_thresh) or (n_c > self.chaining_size_thresh)

            diagnostics[int(cid)] = {
                "cluster_id": int(cid),
                "stop_count": n_c,
                "center_x": float(center[0]),
                "center_y": float(center[1]),
                "bbox_dx": dx,
                "bbox_dy": dy,
                "diameter_meters": diameter,
                "radius_of_gyration_meters": rg,
                "is_chained": is_chained,
            }

        return labels, diagnostics

    def fit_functional_kmeans(
        self,
        feature_matrix: np.ndarray,
        k: int,
    ) -> Tuple[KMeans, np.ndarray, float]:
        """
        Fits a single K-Means model on standardized feature matrix.
        
        Args:
          feature_matrix: Standardized array of shape (N_eligible, D).
          k: Number of functional clusters.
          
        Returns:
          model: Fitted KMeans instance.
          labels: 1D array of assigned cluster labels in [0, k-1].
          inertia: Sum of squared distances to closest cluster center.
        """
        km = KMeans(
            n_clusters=k,
            random_state=self.random_state,
            n_init=10,
        )
        labels = km.fit_predict(feature_matrix)
        return km, labels, float(km.inertia_)

    def evaluate_kmeans_candidates(
        self,
        raw_features: np.ndarray,
        candidate_k: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates candidate KMeans models across k in [3, 8] on the invariant eligible cohort.
        
        Args:
          raw_features: 2D array of shape (N_eligible, 5) with columns:
            [ln(v_s + 1), routes_served, am_peak_headway, attributed_demand, service_span_hours]
            Must be 100% complete and finite (no NaN / Inf).
          candidate_k: List of k values to evaluate (default [3, 4, 5, 6, 7, 8]).
          
        Returns:
          Dictionary mapping k -> {
            'model': fitted KMeans,
            'labels': 1D labels array,
            'inertia': float,
            'scaler': fitted StandardScaler,
            'scaled_features': standardized feature array
          }
        """
        if np.isnan(raw_features).any() or np.isinf(raw_features).any():
            raise ValueError("Input feature matrix contains NaN or Inf! Must be filtered prior to KMeans.")

        k_list = candidate_k if candidate_k is not None else self.KMEANS_CANDIDATE_K

        # Standardize features once across the invariant eligible cohort
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(raw_features)

        results = {
            "scaler": scaler,
            "scaled_features": scaled_features,
            "candidates": {},
        }

        for k in k_list:
            km, labels, inertia = self.fit_functional_kmeans(scaled_features, k)
            results["candidates"][k] = {
                "k": k,
                "model": km,
                "labels": labels,
                "inertia": inertia,
                "cluster_sizes": np.bincount(labels).tolist(),
            }

        return results
