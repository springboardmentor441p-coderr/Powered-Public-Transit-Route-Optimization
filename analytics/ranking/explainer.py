"""
AI_RouteRanker - Phase 7 Explainability Engine
Generates additive criterion contributions, 4-pillar score rollups, waterfall attributions,
and plain-English transit planning narratives without unsupported policy claims.
"""

from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd
from analytics.ranking.config import RankerConfig


class RouteRankerExplainer:
    """
    Translates mathematical MCDM scores into transparent, additive explanations
    and structured JSON payloads for frontend dashboard visualization.
    """

    CRITERION_DISPLAY_NAMES: Dict[str, str] = {
        "forecasted_daily_demand_norm": "Forecasted Passenger Volume",
        "load_intensity_factor_norm": "Passenger Load Intensity",
        "scheduled_trips_norm": "Scheduled Daily Trips",
        "service_span_hours_norm": "Daily Operating Span",
        "am_headway_min_norm": "AM Peak Frequency",
        "hub_stop_ratio_norm": "Transit Hub Connectivity",
        "corridor_duplication_index_norm": "Corridor Co-Routing Duplication",
    }

    @staticmethod
    def compute_pillar_scores(
        contributions: np.ndarray,
        criteria_names: List[str],
        criteria_to_pillar_map: Optional[Dict[str, str]] = None,
    ) -> pd.DataFrame:
        """
        Rolls up additive criterion contributions into four high-level planning pillars.

        Parameters
        ----------
        contributions : np.ndarray
            Shape [N, M] array of additive criterion contributions.
        criteria_names : List[str]
            List of M criteria names corresponding to matrix columns.
        criteria_to_pillar_map : Optional[Dict[str, str]]
            Mapping from criterion name to pillar identifier.

        Returns
        -------
        pd.DataFrame
            DataFrame of shape [N, 4] with columns:
            ['pillar_demand_score', 'pillar_service_score', 'pillar_hub_score', 'pillar_corridor_score']
        """
        if criteria_to_pillar_map is None:
            criteria_to_pillar_map = RankerConfig.CRITERIA_TO_PILLAR_MAP

        n_rows = contributions.shape[0]
        pillar_cols = [
            ("pillar_demand_score", RankerConfig.PILLAR_DEMAND),
            ("pillar_service_score", RankerConfig.PILLAR_SERVICE),
            ("pillar_hub_score", RankerConfig.PILLAR_HUBS),
            ("pillar_corridor_score", RankerConfig.PILLAR_CORRIDOR),
        ]

        result_dict = {}
        for col_name, pillar_id in pillar_cols:
            pillar_indices = [
                idx for idx, c in enumerate(criteria_names)
                if criteria_to_pillar_map.get(c) == pillar_id
            ]
            if pillar_indices:
                pillar_sum = np.sum(contributions[:, pillar_indices], axis=1)
                result_dict[col_name] = np.round(pillar_sum, 6)
            else:
                result_dict[col_name] = np.zeros(n_rows, dtype=np.float64)

        return pd.DataFrame(result_dict)

    @classmethod
    def generate_explanations(
        cls,
        df: pd.DataFrame,
        criteria_matrix: np.ndarray,
        valid_mask: np.ndarray,
        base_weights: Dict[str, float],
        effective_weights: np.ndarray,
        contributions: np.ndarray,
        scores: np.ndarray,
        ranks: np.ndarray,
        percentile_ranks: np.ndarray,
        topsis_scores: Optional[np.ndarray] = None,
        topsis_ranks: Optional[np.ndarray] = None,
        criteria_names: Optional[List[str]] = None,
        track_name: str = RankerConfig.TRACK_BUS_PRIORITY,
        profile_name: str = "BALANCED_DEFAULT",
    ) -> List[Dict[str, Any]]:
        """
        Constructs comprehensive, structured explanation payloads for every route.

        Returns
        -------
        List[Dict[str, Any]]
            List of N explanation dictionaries directly serializable to JSON.
        """
        if criteria_names is None:
            criteria_names = list(base_weights.keys())

        n_routes = len(df)
        total_valid = int(np.sum(~np.isnan(ranks)))
        pillar_df = cls.compute_pillar_scores(contributions, criteria_names)

        explanations = []

        for i in range(n_routes):
            row = df.iloc[i]
            route_id = str(row.get("route_id", f"route_{i}"))
            route_short = str(row.get("route_short_name", route_id))
            route_long = str(row.get("route_long_name", route_short))
            is_rail = bool(row.get("is_rail", False))
            cluster_label = str(row.get("operational_cluster_label", "Unassigned"))
            regional_part = str(row.get("regional_partition", "Unassigned"))

            route_score = float(scores[i]) if not np.isnan(scores[i]) else None
            route_rank = int(ranks[i]) if not np.isnan(ranks[i]) else None
            pct_rank = float(np.round(percentile_ranks[i], 2)) if not np.isnan(percentile_ranks[i]) else None

            top_score = float(topsis_scores[i]) if topsis_scores is not None and not np.isnan(topsis_scores[i]) else None
            top_rank = int(topsis_ranks[i]) if topsis_ranks is not None and not np.isnan(topsis_ranks[i]) else None

            # Collect individual criterion details
            crit_scores = {}
            orig_w = {}
            eff_w = {}
            contrib_map = {}
            missing_crits = []

            for c_idx, c_name in enumerate(criteria_names):
                orig_w[c_name] = float(base_weights.get(c_name, 0.0))
                if valid_mask[i, c_idx]:
                    crit_scores[c_name] = float(np.round(criteria_matrix[i, c_idx], 6))
                    eff_w[c_name] = float(np.round(effective_weights[i, c_idx], 6))
                    contrib_map[c_name] = float(np.round(contributions[i, c_idx], 6))
                else:
                    crit_scores[c_name] = None
                    eff_w[c_name] = 0.0
                    contrib_map[c_name] = 0.0
                    missing_crits.append(c_name)

            # Sort valid criteria by additive contribution to identify drivers
            valid_contribs = [
                (c_name, contrib_map[c_name], crit_scores[c_name])
                for c_name in criteria_names
                if c_name not in missing_crits
            ]
            valid_contribs.sort(key=lambda x: x[1], reverse=True)

            top_positive = []
            top_negative = []

            if valid_contribs:
                for c_name, c_val, c_sc in valid_contribs[:2]:
                    disp = cls.CRITERION_DISPLAY_NAMES.get(c_name, c_name)
                    top_positive.append({
                        "criterion": disp,
                        "feature_key": c_name,
                        "contribution": float(np.round(c_val, 4)),
                        "score": float(np.round(c_sc, 4)) if c_sc is not None else None,
                    })

                for c_name, c_val, c_sc in valid_contribs[-2:]:
                    disp = cls.CRITERION_DISPLAY_NAMES.get(c_name, c_name)
                    top_negative.append({
                        "criterion": disp,
                        "feature_key": c_name,
                        "contribution": float(np.round(c_val, 4)),
                        "score": float(np.round(c_sc, 4)) if c_sc is not None else None,
                    })

            # Pillars
            pillars = {
                "demand_pressure": float(pillar_df.loc[i, "pillar_demand_score"]),
                "service_provision": float(pillar_df.loc[i, "pillar_service_score"]),
                "network_hubs": float(pillar_df.loc[i, "pillar_hub_score"]),
                "corridor_structure": float(pillar_df.loc[i, "pillar_corridor_score"]),
            }

            # Generate plain-English objective narrative
            if route_score is not None and route_rank is not None:
                pos_text = ", ".join([d["criterion"] for d in top_positive]) if top_positive else "balanced attributes"
                narrative = (
                    f"Route {route_short} ({route_long}) ranks #{route_rank} of {total_valid} routes "
                    f"in the {track_name} track under the {profile_name} profile with an overall multi-criteria "
                    f"priority score of {route_score:.4f}. Its evaluation is primarily elevated by strong {pos_text}. "
                    f"This ranking identifies the route for operational planning review and corridor investigation."
                )
                if missing_crits:
                    missing_disp = [cls.CRITERION_DISPLAY_NAMES.get(m, m) for m in missing_crits]
                    narrative += f" Note: {', '.join(missing_disp)} was unavailable and was dynamically re-weighted."
            else:
                narrative = (
                    f"Route {route_short} ({route_long}) has insufficient valid criteria data "
                    f"to compute a reliable priority ranking under the {profile_name} profile."
                )

            explanations.append({
                "route_id": route_id,
                "route_short_name": route_short,
                "route_long_name": route_long,
                "is_rail": is_rail,
                "operational_cluster_label": cluster_label,
                "regional_partition": regional_part,
                "track": track_name,
                "profile": profile_name,
                "overall_score": route_score,
                "rank": route_rank,
                "percentile_rank": pct_rank,
                "topsis_score": top_score,
                "topsis_rank": top_rank,
                "pillars": pillars,
                "criterion_scores": crit_scores,
                "original_weights": orig_w,
                "effective_weights": eff_w,
                "contributions": contrib_map,
                "missing_criteria": missing_crits,
                "top_positive_drivers": top_positive,
                "top_negative_drivers": top_negative,
                "narrative": narrative,
            })

        return explanations
