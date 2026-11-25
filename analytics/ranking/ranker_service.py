"""
AI_RouteRanker - Phase 7 Master Ranking Service Module
Coordinates criteria transformation, WSM scoring, TOPSIS benchmarks, explainability generation,
and sensitivity analysis across three distinct transit ranking tracks:
1. Track 1: Bus Network Priority (125 bus routes, 7 criteria)
2. Track 2: Heavy Rail Operational Priority (8 rail lines, 4 operational criteria)
3. Track 3: Unified Network Operational Supply (133 routes, 4 mode-agnostic criteria)
"""

from typing import Dict, List, Any, Optional, Tuple
import os
import json
from pathlib import Path
import numpy as np
import pandas as pd

from analytics.ranking.config import RankerConfig
from analytics.ranking.criteria_transformer import CriteriaTransformer
from analytics.ranking.mcdm_engine import MCDMEngine
from analytics.ranking.explainer import RouteRankerExplainer
from analytics.ranking.sensitivity import RankingSensitivityAnalyzer


class RouteRankerService:
    """
    Master service orchestrator for multi-criteria route ranking, explainability,
    and sensitivity evaluations.
    """

    def __init__(
        self,
        config: Optional[RankerConfig] = None,
        min_valid_weight: float = RankerConfig.MIN_VALID_WEIGHT_THRESHOLD,
    ):
        self.config = config or RankerConfig()
        self.min_valid_weight = min_valid_weight
        self.transformer = CriteriaTransformer(min_valid_weight=self.min_valid_weight)

    def select_track_population(
        self,
        df: pd.DataFrame,
        track: str,
    ) -> pd.DataFrame:
        """
        Filters input DataFrame to the specified route track population without mutating original.

        Parameters
        ----------
        df : pd.DataFrame
            Complete route feature DataFrame.
        track : str
            One of TRACK_BUS_PRIORITY, TRACK_RAIL_PRIORITY, TRACK_UNIFIED_SUPPLY.

        Returns
        -------
        pd.DataFrame
            Filtered DataFrame copy.
        """
        if "is_rail" not in df.columns:
            raise KeyError("Input DataFrame is missing required boolean column 'is_rail'")

        if track == RankerConfig.TRACK_BUS_PRIORITY:
            subset = df[df["is_rail"] == False].copy()
        elif track == RankerConfig.TRACK_RAIL_PRIORITY:
            subset = df[df["is_rail"] == True].copy()
        elif track == RankerConfig.TRACK_UNIFIED_SUPPLY:
            subset = df.copy()
        else:
            raise ValueError(f"Unknown ranking track '{track}'")

        return subset.reset_index(drop=True)

    def get_track_weights(
        self,
        track: str,
        profile_name: str = "BALANCED_DEFAULT",
        custom_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """
        Resolves the appropriate criteria weight dictionary for a track and profile.
        """
        if custom_weights is not None:
            # Validate custom weights sum to ~1.0
            tot = sum(custom_weights.values())
            if not np.isclose(tot, 1.0, atol=1e-3):
                raise ValueError(f"Custom weights must sum to 1.0 (got {tot})")
            return custom_weights

        if track == RankerConfig.TRACK_RAIL_PRIORITY:
            return dict(RankerConfig.RAIL_PROFILE_WEIGHTS)
        elif track == RankerConfig.TRACK_UNIFIED_SUPPLY:
            return dict(RankerConfig.UNIFIED_SUPPLY_WEIGHTS)
        else:
            # Bus Priority track supports all defined stakeholder profiles
            if profile_name in RankerConfig.WEIGHT_PROFILES:
                return dict(RankerConfig.WEIGHT_PROFILES[profile_name])
            raise KeyError(f"Unknown weight profile '{profile_name}' for track '{track}'")

    def run_ranking(
        self,
        df: pd.DataFrame,
        track: str = RankerConfig.TRACK_BUS_PRIORITY,
        profile_name: str = "BALANCED_DEFAULT",
        custom_weights: Optional[Dict[str, float]] = None,
        run_sensitivity: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes end-to-end multi-criteria ranking for a specified track and profile.

        Parameters
        ----------
        df : pd.DataFrame
            Input feature master DataFrame (immutable; will not be modified).
        track : str
            Target ranking track.
        profile_name : str
            Target weight profile.
        custom_weights : Optional[Dict[str, float]]
            Optional user-specified custom weight dictionary.
        run_sensitivity : bool
            Whether to run systematic sensitivity analysis.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing:
            - 'rankings_df': Complete ranked tabular DataFrame.
            - 'explanations': List of structured explanation dicts.
            - 'sensitivity_scenarios': pd.DataFrame of sensitivity scenarios (if run).
            - 'sensitivity_shifts': pd.DataFrame of route rank shifts (if run).
            - 'overall_stability': float (mean Spearman rho).
            - 'topsis_correlation': float (Spearman rho between WSM and TOPSIS).
        """
        # 1. Filter population
        track_df = self.select_track_population(df, track)
        if track_df.empty:
            raise ValueError(f"Track population for '{track}' is empty")

        weights = self.get_track_weights(track, profile_name, custom_weights)
        criteria_names = list(weights.keys())
        base_w_vec = np.array([weights[c] for c in criteria_names], dtype=np.float64)

        # 2. Extract and transform criteria
        matrix, valid_mask, criteria_list, coverage_mask = self.transformer.transform(track_df, weights)

        # 3. Compute Primary WSM Scores
        wsm_scores, eff_weights, contribs = MCDMEngine.compute_wsm(
            matrix, base_w_vec, valid_mask, coverage_mask
        )
        wsm_ranks, pct_ranks = MCDMEngine.assign_ranks(wsm_scores, ascending=False)

        # 4. Compute Secondary TOPSIS Benchmark
        topsis_scores = MCDMEngine.compute_topsis(
            matrix, base_w_vec, valid_mask, coverage_mask
        )
        topsis_ranks, _ = MCDMEngine.assign_ranks(topsis_scores, ascending=False)

        # Cross-method correlation
        topsis_corr = RankingSensitivityAnalyzer.compute_spearman_correlation(wsm_ranks, topsis_ranks)

        # 5. Compute 4 Pillar Scores
        pillar_df = RouteRankerExplainer.compute_pillar_scores(contribs, criteria_list)

        # 6. Build Master Output DataFrame
        result_df = track_df.copy()
        result_df["track"] = track
        result_df["profile"] = profile_name
        result_df["overall_score"] = np.round(wsm_scores, 6)
        result_df["rank"] = wsm_ranks
        result_df["percentile_rank"] = np.round(pct_ranks, 2)
        result_df["topsis_score"] = np.round(topsis_scores, 6)
        result_df["topsis_rank"] = topsis_ranks

        # Attach pillar scores
        for p_col in pillar_df.columns:
            result_df[p_col] = pillar_df[p_col]

        # Attach individual additive criterion contributions
        for c_idx, c_name in enumerate(criteria_list):
            col_key = f"contrib_{c_name.replace('_norm', '')}"
            result_df[col_key] = np.round(contribs[:, c_idx], 6)

        # Sort primarily by rank ascending (rank 1 first), putting NaNs at end
        result_df = result_df.sort_values(
            by=["rank", "route_id"],
            ascending=[True, True],
            na_position="last"
        ).reset_index(drop=True)

        # 7. Generate Explanations
        explanations = RouteRankerExplainer.generate_explanations(
            df=track_df,
            criteria_matrix=matrix,
            valid_mask=valid_mask,
            base_weights=weights,
            effective_weights=eff_weights,
            contributions=contribs,
            scores=wsm_scores,
            ranks=wsm_ranks,
            percentile_ranks=pct_ranks,
            topsis_scores=topsis_scores,
            topsis_ranks=topsis_ranks,
            criteria_names=criteria_list,
            track_name=track,
            profile_name=profile_name,
        )

        # 8. Run Sensitivity Analysis (Optional)
        sens_scenarios = None
        sens_shifts = None
        stability = None
        if run_sensitivity:
            sens_scenarios, sens_shifts, stability = RankingSensitivityAnalyzer.evaluate_sensitivity(
                matrix=matrix,
                valid_mask=valid_mask,
                coverage_mask=coverage_mask,
                base_weights=weights,
                deltas=RankerConfig.PERTURBATION_DELTAS,
                top_k_list=RankerConfig.TOP_K_BENCHMARKS,
            )

        return {
            "track": track,
            "profile": profile_name,
            "rankings_df": result_df,
            "explanations": explanations,
            "sensitivity_scenarios": sens_scenarios,
            "sensitivity_shifts": sens_shifts,
            "overall_stability": stability,
            "topsis_correlation": topsis_corr,
        }

    def save_deliverables(
        self,
        results: Dict[str, Any],
        output_dir: Optional[Path] = None,
    ) -> Dict[str, str]:
        """
        Saves ranking results to Parquet and JSON deliverables.

        Parameters
        ----------
        results : Dict[str, Any]
            Output dictionary from run_ranking.
        output_dir : Optional[Path]
            Destination directory. Defaults to RankerConfig.RANKING_RESULTS_DIR.

        Returns
        -------
        Dict[str, str]
            Map of artifact name to written file path.
        """
        if output_dir is None:
            output_dir = Path(RankerConfig.RANKING_RESULTS_DIR)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        paths = {}

        # 1. Parquet master
        parquet_path = output_dir / "route_rankings_master.parquet"
        results["rankings_df"].to_parquet(parquet_path, index=False)
        paths["rankings_parquet"] = str(parquet_path)

        # 2. JSON explanations
        json_path = output_dir / "route_ranking_explanations.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results["explanations"], f, indent=2)
        paths["explanations_json"] = str(json_path)

        # 3. Sensitivity Parquet (if available)
        if results.get("sensitivity_scenarios") is not None:
            sens_path = output_dir / "ranking_sensitivity_analysis.parquet"
            results["sensitivity_scenarios"].to_parquet(sens_path, index=False)
            paths["sensitivity_parquet"] = str(sens_path)

        return paths
