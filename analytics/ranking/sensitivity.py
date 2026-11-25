"""
AI_RouteRanker - Phase 7 Sensitivity Analysis Module
Evaluates ranking stability under systematic weight perturbations (±10%, ±20%),
computing Spearman rank correlations, Top-K set overlaps, and route rank volatility.
"""

from typing import Dict, List, Any, Tuple, Optional
import numpy as np
import pandas as pd
from analytics.ranking.mcdm_engine import MCDMEngine


class RankingSensitivityAnalyzer:
    """
    Executes systematic weight perturbations and evaluates rank stability metrics.
    """

    @staticmethod
    def perturb_weights(
        base_weights: Dict[str, float],
        target_criterion: str,
        delta: float,
    ) -> Dict[str, float]:
        """
        Perturbs a single criterion weight by (1 + delta) and proportionally rescales
        remaining weights so the vector sums to exactly 1.0.

        Parameters
        ----------
        base_weights : Dict[str, float]
            Base criteria weights summing to 1.0.
        target_criterion : str
            The criterion to increase or decrease.
        delta : float
            Fractional shift (e.g., +0.10, -0.10, +0.20, -0.20).

        Returns
        -------
        Dict[str, float]
            Adjusted weights summing to 1.0.
        """
        if target_criterion not in base_weights:
            raise KeyError(f"Target criterion '{target_criterion}' not in base weights")

        old_w = base_weights[target_criterion]
        new_w = np.clip(old_w * (1.0 + delta), 0.01, 0.95)
        diff = new_w - old_w

        other_sum = sum(w for c, w in base_weights.items() if c != target_criterion)
        perturbed = {}

        if other_sum > 0:
            for c, w in base_weights.items():
                if c == target_criterion:
                    perturbed[c] = float(new_w)
                else:
                    # Subtract share of diff proportionally
                    share = w / other_sum
                    adj_w = w - (diff * share)
                    perturbed[c] = float(np.clip(adj_w, 0.005, 0.95))
        else:
            perturbed = base_weights.copy()

        # Final normalization to ensure sum == 1.000000 exactly
        tot = sum(perturbed.values())
        return {c: float(np.round(w / tot, 6)) for c, w in perturbed.items()}

    @staticmethod
    def compute_spearman_correlation(ranks_a: np.ndarray, ranks_b: np.ndarray) -> float:
        """
        Calculates Spearman's rank correlation coefficient between two rank arrays.

        Parameters
        ----------
        ranks_a : np.ndarray
            First rank vector.
        ranks_b : np.ndarray
            Second rank vector.

        Returns
        -------
        float
            Spearman rho in [-1.0, 1.0].
        """
        valid = ~np.isnan(ranks_a) & ~np.isnan(ranks_b)
        if np.sum(valid) < 2:
            return 1.0

        r_a = pd.Series(ranks_a[valid])
        r_b = pd.Series(ranks_b[valid])

        corr = r_a.corr(r_b, method="spearman")
        return float(np.round(corr if not np.isnan(corr) else 1.0, 6))

    @staticmethod
    def compute_top_k_overlap(ranks_a: np.ndarray, ranks_b: np.ndarray, k: int) -> float:
        """
        Calculates proportion of identical items in the Top-K ranks between two vectors.

        Parameters
        ----------
        ranks_a : np.ndarray
            Base ranks.
        ranks_b : np.ndarray
            Perturbed ranks.
        k : int
            Top-K threshold (e.g., 10, 20).

        Returns
        -------
        float
            Overlap fraction in [0.0, 1.0].
        """
        valid = ~np.isnan(ranks_a) & ~np.isnan(ranks_b)
        valid_indices = np.where(valid)[0]
        if len(valid_indices) < k:
            k = max(1, len(valid_indices))

        top_a = set(np.argsort(ranks_a[valid_indices])[:k])
        top_b = set(np.argsort(ranks_b[valid_indices])[:k])

        overlap = len(top_a.intersection(top_b)) / float(k)
        return float(np.round(overlap, 4))

    @classmethod
    def evaluate_sensitivity(
        cls,
        matrix: np.ndarray,
        valid_mask: np.ndarray,
        coverage_mask: np.ndarray,
        base_weights: Dict[str, float],
        deltas: Optional[List[float]] = None,
        top_k_list: Optional[List[int]] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, float]:
        """
        Runs full sensitivity analysis suite across all criteria and perturbation deltas.

        Returns
        -------
        Tuple[pd.DataFrame, pd.DataFrame, float]
            - scenarios_df: Summary metrics per perturbation scenario.
            - rank_shifts_df: Route-level rank shifts across all scenarios.
            - overall_stability: Mean Spearman rho across all scenarios.
        """
        if deltas is None:
            deltas = [-0.20, -0.10, 0.10, 0.20]
        if top_k_list is None:
            top_k_list = [10, 20]

        criteria_names = list(base_weights.keys())
        base_w_vec = np.array([base_weights[c] for c in criteria_names], dtype=np.float64)

        # Base scoring
        base_scores, _, _ = MCDMEngine.compute_wsm(matrix, base_w_vec, valid_mask, coverage_mask)
        base_ranks, _ = MCDMEngine.assign_ranks(base_scores, ascending=False)

        n_routes = len(base_scores)
        scenarios_records = []
        rank_shifts_dict = {"base_rank": base_ranks}

        for crit in criteria_names:
            for delta in deltas:
                scenario_id = f"{crit}_{'+' if delta > 0 else ''}{int(delta*100)}pct"
                perturbed_w_map = cls.perturb_weights(base_weights, crit, delta)
                pert_w_vec = np.array([perturbed_w_map[c] for c in criteria_names], dtype=np.float64)

                p_scores, _, _ = MCDMEngine.compute_wsm(matrix, pert_w_vec, valid_mask, coverage_mask)
                p_ranks, _ = MCDMEngine.assign_ranks(p_scores, ascending=False)

                rank_shifts_dict[scenario_id] = p_ranks

                # Evaluate metrics
                spearman_rho = cls.compute_spearman_correlation(base_ranks, p_ranks)
                overlaps = {
                    f"top_{k}_overlap": cls.compute_top_k_overlap(base_ranks, p_ranks, k)
                    for k in top_k_list
                }

                valid = ~np.isnan(base_ranks) & ~np.isnan(p_ranks)
                if np.any(valid):
                    abs_diff = np.abs(base_ranks[valid] - p_ranks[valid])
                    mean_shift = float(np.round(np.mean(abs_diff), 2))
                    max_shift = int(np.max(abs_diff))
                else:
                    mean_shift = 0.0
                    max_shift = 0

                rec = {
                    "scenario_id": scenario_id,
                    "target_criterion": crit,
                    "delta": delta,
                    "spearman_rho": spearman_rho,
                    "mean_absolute_rank_shift": mean_shift,
                    "max_rank_shift": max_shift,
                }
                rec.update(overlaps)
                scenarios_records.append(rec)

        scenarios_df = pd.DataFrame(scenarios_records)
        rank_shifts_df = pd.DataFrame(rank_shifts_dict)
        overall_stability = float(np.round(scenarios_df["spearman_rho"].mean(), 4))

        return scenarios_df, rank_shifts_df, overall_stability
