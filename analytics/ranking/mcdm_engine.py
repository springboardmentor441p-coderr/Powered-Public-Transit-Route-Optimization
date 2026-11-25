"""
AI_RouteRanker - Phase 7 MCDM Scoring Engine
Implements Hierarchical Weighted Sum Model (WSM / SAW) with dynamic criterion weight masking,
secondary TOPSIS benchmark scoring, and deterministic competitive tie-breaking.
"""

from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd


class MCDMEngine:
    """
    Core mathematical ranking engine implementing WSM and TOPSIS multi-criteria algorithms.
    """

    @staticmethod
    def compute_wsm(
        matrix: np.ndarray,
        base_weights: np.ndarray,
        valid_mask: np.ndarray,
        coverage_mask: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Computes Weighted Sum Model (WSM) scores with dynamic criterion weight masking.

        Parameters
        ----------
        matrix : np.ndarray
            Shape [N, M] transformed criteria matrix in [0, 1] (NaN for missing values).
        base_weights : np.ndarray
            Shape [M] base weights vector summing to 1.0.
        valid_mask : np.ndarray
            Shape [N, M] boolean mask where True indicates valid (non-NaN) criterion.
        coverage_mask : np.ndarray
            Shape [N] boolean mask where True indicates route meets min valid weight threshold.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray, np.ndarray]
            - scores: np.ndarray of shape [N] with overall WSM scores in [0, 1] (NaN for uncovered).
            - effective_weights: np.ndarray of shape [N, M] with dynamically re-scaled weights.
            - contributions: np.ndarray of shape [N, M] with exact additive contributions.
        """
        n_rows, n_cols = matrix.shape
        scores = np.full(n_rows, np.nan, dtype=np.float64)
        effective_weights = np.zeros((n_rows, n_cols), dtype=np.float64)
        contributions = np.zeros((n_rows, n_cols), dtype=np.float64)

        for i in range(n_rows):
            if not coverage_mask[i]:
                continue

            valid_cols = valid_mask[i]
            if not np.any(valid_cols):
                continue

            valid_w = base_weights[valid_cols]
            sum_valid_w = np.sum(valid_w)

            if sum_valid_w <= 0:
                continue

            # Dynamic weight renormalization: w_j' = w_j / sum(valid_w)
            norm_w = valid_w / sum_valid_w
            effective_weights[i, valid_cols] = norm_w

            # Exact additive criterion contributions
            vals = matrix[i, valid_cols]
            contribs = norm_w * vals
            contributions[i, valid_cols] = contribs

            # Composite overall score
            route_score = float(np.sum(contribs))
            scores[i] = np.clip(route_score, 0.0, 1.0)

        return scores, effective_weights, contributions

    @staticmethod
    def compute_topsis(
        matrix: np.ndarray,
        base_weights: np.ndarray,
        valid_mask: np.ndarray,
        coverage_mask: np.ndarray,
    ) -> np.ndarray:
        """
        Computes secondary TOPSIS benchmark scores based on Euclidean distance to ideal solutions.

        Parameters
        ----------
        matrix : np.ndarray
            Shape [N, M] transformed criteria matrix in [0, 1].
        base_weights : np.ndarray
            Shape [M] base weights vector.
        valid_mask : np.ndarray
            Shape [N, M] boolean mask of valid entries.
        coverage_mask : np.ndarray
            Shape [N] boolean mask of valid coverage.

        Returns
        -------
        np.ndarray
            Shape [N] array of TOPSIS relative closeness scores in [0, 1] (NaN for uncovered).
        """
        n_rows, n_cols = matrix.shape
        topsis_scores = np.full(n_rows, np.nan, dtype=np.float64)

        # Compute column-wise ideal (PIS) and anti-ideal (NIS) reference points over valid entries
        ideal_pos = np.zeros(n_cols, dtype=np.float64)
        ideal_neg = np.zeros(n_cols, dtype=np.float64)

        for j in range(n_cols):
            col_valid = matrix[valid_mask[:, j], j]
            if len(col_valid) > 0:
                ideal_pos[j] = float(np.max(col_valid))
                ideal_neg[j] = float(np.min(col_valid))
            else:
                ideal_pos[j] = 1.0
                ideal_neg[j] = 0.0

        for i in range(n_rows):
            if not coverage_mask[i]:
                continue

            valid_cols = valid_mask[i]
            if not np.any(valid_cols):
                continue

            # Normalized weights for valid criteria
            valid_w = base_weights[valid_cols]
            sum_w = np.sum(valid_w)
            if sum_w <= 0:
                continue
            norm_w = valid_w / sum_w

            # Weighted values
            v_i = norm_w * matrix[i, valid_cols]
            v_pos = norm_w * ideal_pos[valid_cols]
            v_neg = norm_w * ideal_neg[valid_cols]

            # Euclidean separation distances
            d_pos = np.sqrt(np.sum((v_i - v_pos) ** 2))
            d_neg = np.sqrt(np.sum((v_i - v_neg) ** 2))

            total_dist = d_pos + d_neg
            if total_dist > 1e-12:
                closeness = d_neg / total_dist
            else:
                closeness = 0.5

            topsis_scores[i] = np.clip(closeness, 0.0, 1.0)

        return topsis_scores

    @staticmethod
    def assign_ranks(
        scores: np.ndarray,
        ascending: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generates deterministic ranks and percentile rankings with standard competition tie-breaking ('min').

        Parameters
        ----------
        scores : np.ndarray
            Array of scores of length N (higher score gets better/lower rank number by default).
        ascending : bool
            False for descending ranking (score=1.0 gets rank 1); True for ascending.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            - ranks: np.ndarray of shape [N] (float to allow NaN for unranked routes).
            - percentile_ranks: np.ndarray of shape [N] in [0, 100].
        """
        n = len(scores)
        ranks = np.full(n, np.nan, dtype=np.float64)
        percentile_ranks = np.full(n, np.nan, dtype=np.float64)

        valid_idx = np.where(~np.isnan(scores))[0]
        if len(valid_idx) == 0:
            return ranks, percentile_ranks

        valid_scores = scores[valid_idx]
        s_series = pd.Series(valid_scores)

        # Standard competition rank ('min'): 1 is highest priority when ascending=False
        computed_ranks = s_series.rank(ascending=ascending, method="min").to_numpy(dtype=np.float64)
        ranks[valid_idx] = computed_ranks

        # Percentile rank: 100% is top-ranked
        n_valid = len(valid_idx)
        if n_valid > 1:
            if ascending:
                pct = ((n_valid - computed_ranks) / (n_valid - 1)) * 100.0
            else:
                pct = ((n_valid - computed_ranks) / (n_valid - 1)) * 100.0
            percentile_ranks[valid_idx] = np.clip(pct, 0.0, 100.0)
        else:
            percentile_ranks[valid_idx] = 100.0

        return ranks, percentile_ranks
