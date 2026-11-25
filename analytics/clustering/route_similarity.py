"""
AI_RouteRanker - Phase 6.2 Route Similarity Engine Module
Implements two independent pairwise similarity metrics:
  Method A: 100-meter Buffered Corridor Area Overlap Ratio
  Method B: Memory-Conscious Discrete Fréchet Distance (in meters)
"""

import os
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Polygon
from scipy.spatial.distance import cdist


def _frechet_worker(item: Tuple[int, int, np.ndarray, np.ndarray]) -> Tuple[int, int, float]:
    idx_i, idx_j, geom_i, geom_j = item
    df = RouteSimilarityEngine.compute_discrete_frechet(geom_i, geom_j)
    return idx_i, idx_j, df


class RouteSimilarityEngine:
    """
    Computes pairwise spatial route-direction similarities and produces independent
    distance matrices for hierarchical clustering.
    """

    BUFFER_RADIUS_METERS: float = 100.0

    @classmethod
    def compute_buffer_overlap(
        cls,
        coords_a: np.ndarray,
        coords_b: np.ndarray,
        buffer_radius: float = BUFFER_RADIUS_METERS,
    ) -> float:
        """
        Calculates the asymmetric/symmetric corridor area overlap ratio:
          Overlap(A, B) = Area(Buf(A) ∩ Buf(B)) / min(Area(Buf(A)), Area(Buf(B)))

        Args:
            coords_a: (N, 2) projected metric coordinates of Route A.
            coords_b: (M, 2) projected metric coordinates of Route B.
            buffer_radius: Buffer radius in meters (default 100.0m).

        Returns:
            Float in [0.0, 1.0].
        """
        if len(coords_a) < 2 or len(coords_b) < 2:
            return 0.0

        line_a = LineString(coords_a)
        line_b = LineString(coords_b)

        # Buffer lines
        buf_a = line_a.buffer(float(buffer_radius))
        buf_b = line_b.buffer(float(buffer_radius))

        area_a = float(buf_a.area)
        area_b = float(buf_b.area)

        if area_a <= 0.0 or area_b <= 0.0:
            return 0.0

        # Fast envelope intersection pre-filter
        if not buf_a.envelope.intersects(buf_b.envelope):
            return 0.0

        intersection_area = float(buf_a.intersection(buf_b).area)
        min_area = min(area_a, area_b)

        overlap = intersection_area / min_area
        return float(np.clip(overlap, 0.0, 1.0))

    @staticmethod
    def compute_discrete_frechet(
        coords_a: np.ndarray,
        coords_b: np.ndarray,
    ) -> float:
        """
        Calculates the exact Discrete Fréchet Distance (coupling distance) in meters
        using dynamic programming with O(N*M) time and O(M) memory.

        Args:
            coords_a: (N, 2) projected metric coordinates of Route A.
            coords_b: (M, 2) projected metric coordinates of Route B.

        Returns:
            Float distance in meters (>= 0.0).
        """
        n = len(coords_a)
        m = len(coords_b)

        if n == 0 or m == 0:
            return float("inf")

        # Ensure m <= n to minimize row length and guarantee exact symmetry
        if n < m:
            coords_a, coords_b = coords_b, coords_a
            n, m = m, n

        D = cdist(coords_a, coords_b).tolist()

        prev = [0.0] * m
        curr = [0.0] * m

        row0 = D[0]
        p_prev = row0[0]
        prev[0] = p_prev
        for j in range(1, m):
            d0j = row0[j]
            p_prev = p_prev if p_prev > d0j else d0j
            prev[j] = p_prev

        for i in range(1, n):
            row_D = D[i]
            c_j1 = prev[0] if prev[0] > row_D[0] else row_D[0]
            curr[0] = c_j1
            p_j1 = prev[0]
            for j in range(1, m):
                p_j = prev[j]
                min_prior = p_j if (p_j < p_j1 and p_j < c_j1) else (p_j1 if p_j1 < c_j1 else c_j1)
                dij = row_D[j]
                c_j1 = min_prior if min_prior > dij else dij
                curr[j] = c_j1
                p_j1 = p_j
            prev, curr = curr, prev

        return float(prev[-1])

    @classmethod
    def compute_pairwise_similarity_matrices(
        cls,
        route_geometries: Dict[str, np.ndarray],
        buffer_radius: float = BUFFER_RADIUS_METERS,
    ) -> Dict[str, Any]:
        """
        Computes pairwise similarity and distance matrices for all route-directions.

        Args:
            route_geometries: Dict mapping 'route_dir_id' -> downsampled (N, 2) coords array.
            buffer_radius: Buffer radius in meters (default 100.0m).

        Returns:
            Dictionary with:
              - 'pattern_ids': List of pattern IDs.
              - 'buffer_overlap_matrix': (P, P) float array in [0, 1].
              - 'buffer_distance_matrix': (P, P) float array where dist = 1 - overlap.
              - 'frechet_distance_matrix': (P, P) float array in meters.
        """
        pattern_ids = sorted(list(route_geometries.keys()))
        p = len(pattern_ids)

        overlap_mat = np.zeros((p, p), dtype=float)
        frechet_mat = np.zeros((p, p), dtype=float)

        # Precompute buffered corridors and envelopes once per pattern
        buffers = {}
        areas = {}
        envelopes = {}
        for p_id in pattern_ids:
            c = route_geometries[p_id]
            if len(c) >= 2:
                buf = LineString(c).buffer(float(buffer_radius))
                buffers[p_id] = buf
                areas[p_id] = float(buf.area)
                envelopes[p_id] = buf.envelope
            else:
                buffers[p_id] = None
                areas[p_id] = 0.0
                envelopes[p_id] = None

        frechet_tasks = []
        for i in range(p):
            p_i = pattern_ids[i]
            geom_i = route_geometries[p_i]
            buf_i = buffers[p_i]
            area_i = areas[p_i]
            env_i = envelopes[p_i]

            overlap_mat[i, i] = 1.0 if area_i > 0.0 else 0.0
            frechet_mat[i, i] = 0.0

            for j in range(i + 1, p):
                p_j = pattern_ids[j]
                geom_j = route_geometries[p_j]
                buf_j = buffers[p_j]
                area_j = areas[p_j]
                env_j = envelopes[p_j]

                # Compute buffer overlap using precomputed polygons
                if buf_i is not None and buf_j is not None and area_i > 0.0 and area_j > 0.0 and env_i.intersects(env_j):
                    inter_area = float(buf_i.intersection(buf_j).area)
                    min_area = min(area_i, area_j)
                    ov = float(np.clip(inter_area / min_area, 0.0, 1.0)) if min_area > 0.0 else 0.0
                else:
                    ov = 0.0

                overlap_mat[i, j] = ov
                overlap_mat[j, i] = ov

                frechet_tasks.append((i, j, geom_i, geom_j))

        # Compute Discrete Fréchet Distance matrix
        if p > 20:
            workers = min(6, max(1, (os.cpu_count() or 2) // 2))
            with ProcessPoolExecutor(max_workers=workers) as executor:
                for idx_i, idx_j, df in executor.map(_frechet_worker, frechet_tasks, chunksize=50):
                    frechet_mat[idx_i, idx_j] = df
                    frechet_mat[idx_j, idx_i] = df
        else:
            for idx_i, idx_j, geom_i, geom_j in frechet_tasks:
                df = cls.compute_discrete_frechet(geom_i, geom_j)
                frechet_mat[idx_i, idx_j] = df
                frechet_mat[idx_j, idx_i] = df

        buffer_dist_mat = 1.0 - overlap_mat
        np.fill_diagonal(buffer_dist_mat, 0.0)

        return {
            "pattern_ids": pattern_ids,
            "buffer_overlap_matrix": overlap_mat,
            "buffer_distance_matrix": buffer_dist_mat,
            "frechet_distance_matrix": frechet_mat,
        }
