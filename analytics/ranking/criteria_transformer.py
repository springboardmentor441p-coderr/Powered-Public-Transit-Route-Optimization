"""
AI_RouteRanker - Phase 7 Criteria Transformation Module
Extracts, transforms, validates, and masks MCDM criteria from normalized feature inputs.
Enforces cost-to-benefit direction inversion and strict input DataFrame immutability.
"""

from typing import Dict, List, Set, Tuple, Optional
import numpy as np
import pandas as pd
from analytics.ranking.config import RankerConfig


class CriteriaTransformer:
    """
    Transforms raw normalized transit features into standardized MCDM decision matrices.
    """

    def __init__(
        self,
        cost_criteria: Optional[Set[str]] = None,
        min_valid_weight: float = RankerConfig.MIN_VALID_WEIGHT_THRESHOLD,
    ):
        """
        Parameters
        ----------
        cost_criteria : Optional[Set[str]]
            Set of feature names where lower is better (inverted to 1.0 - x).
            Defaults to RankerConfig.COST_CRITERIA.
        min_valid_weight : float
            Minimum proportion of total criteria weight that must be valid.
        """
        self.cost_criteria = cost_criteria if cost_criteria is not None else set(RankerConfig.COST_CRITERIA)
        self.min_valid_weight = float(min_valid_weight)

    def validate_schema(self, df: pd.DataFrame, required_criteria: List[str]) -> Tuple[bool, List[str]]:
        """
        Verifies that all required criteria exist in the input DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            Input DataFrame to validate.
        required_criteria : List[str]
            List of required feature column names.

        Returns
        -------
        Tuple[bool, List[str]]
            (is_valid, list_of_missing_columns)
        """
        missing = []
        for c in required_criteria:
            if c not in df.columns and not (c.endswith("_norm") and c[:-5] in df.columns):
                missing.append(c)
        return len(missing) == 0, missing

    def transform(
        self,
        df: pd.DataFrame,
        weights: Dict[str, float],
    ) -> Tuple[np.ndarray, np.ndarray, List[str], np.ndarray]:
        """
        Extracts and transforms criteria matrix from input DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            Input feature DataFrame (not mutated).
        weights : Dict[str, float]
            Dictionary of criteria names and base weights.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray, List[str], np.ndarray]
            - matrix: np.ndarray of shape [N, M] with transformed values (NaN preserved).
            - valid_mask: np.ndarray of shape [N, M] (bool), True where value is not NaN.
            - criteria_names: List of M feature names in matrix order.
            - coverage_mask: np.ndarray of shape [N] (bool), True where valid weight >= min_valid_weight.
        """
        if df is None or df.empty:
            raise ValueError("Input DataFrame is empty or None")

        criteria_names = list(weights.keys())
        is_valid, missing = self.validate_schema(df, criteria_names)
        if not is_valid:
            raise KeyError(f"Input DataFrame is missing required criteria columns: {missing}")

        n_rows = len(df)
        n_cols = len(criteria_names)
        matrix = np.full((n_rows, n_cols), np.nan, dtype=np.float64)

        # Extract and transform column by column without mutating input DataFrame
        for col_idx, col_name in enumerate(criteria_names):
            src_col = col_name if col_name in df.columns else (col_name[:-5] if col_name.endswith("_norm") and col_name[:-5] in df.columns else col_name)
            vals = pd.to_numeric(df[src_col], errors="coerce").to_numpy(dtype=np.float64, copy=True)

            if col_name in self.cost_criteria:
                # Cost criterion transformation: 1.0 - x_norm
                valid_idx = ~np.isnan(vals)
                vals[valid_idx] = 1.0 - vals[valid_idx]

            # Bounded verification: clip to [0.0, 1.0] for valid numeric entries
            valid_idx = ~np.isnan(vals)
            vals[valid_idx] = np.clip(vals[valid_idx], 0.0, 1.0)
            matrix[:, col_idx] = vals

        valid_mask = ~np.isnan(matrix)

        # Compute valid weight coverage per route
        weight_vec = np.array([weights[c] for c in criteria_names], dtype=np.float64)
        total_base_weight = np.sum(weight_vec)
        if total_base_weight <= 0:
            raise ValueError("Total base criteria weight must be positive")

        valid_weights = np.dot(valid_mask.astype(np.float64), weight_vec)
        coverage_ratio = valid_weights / total_base_weight
        coverage_mask = coverage_ratio >= self.min_valid_weight

        return matrix, valid_mask, criteria_names, coverage_mask
