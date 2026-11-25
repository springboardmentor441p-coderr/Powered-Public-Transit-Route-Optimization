"""
AI_RouteRanker - Phase 6.3 Transit Hub Metrics Module
Extracts route-level transit hub interaction and connectivity metrics using
Phase 6.1 spatial stop clustering and Top-100 transit hub rankings.
"""

from typing import Optional, Set
import pandas as pd
import numpy as np

from analytics.ranking.config import RankerConfig


def compute_route_hub_metrics(
    route_stops_df: pd.DataFrame,
    hub_rankings_df: pd.DataFrame,
    top100_hubs_df: pd.DataFrame,
    peripheral_stops_df: Optional[pd.DataFrame] = None,
    w_ratio: float = RankerConfig.HUB_WEIGHT_STOP_RATIO,
    w_importance: float = RankerConfig.HUB_WEIGHT_IMPORTANCE,
) -> pd.DataFrame:
    """
    Computes route-level transit hub connectivity metrics and spatial equity indicators.

    Parameters
    ----------
    route_stops_df : pd.DataFrame
        DataFrame with route-to-stop mapping containing at least ['route_id', 'stop_id'].
    hub_rankings_df : pd.DataFrame
        Phase 6.1 stop-level rankings containing ['stop_id'] and a hub score column
        ('composite_hub_score_a', 'composite_hub_score', or 'hub_score').
    top100_hubs_df : pd.DataFrame
        Phase 6.1 Top-100 transit hubs containing ['stop_id'].
    peripheral_stops_df : Optional[pd.DataFrame]
        Phase 6.1 peripheral / noise stops containing ['stop_id'] for spatial equity calculation.
    w_ratio : float
        Weight for hub stop ratio term in H_r (default 0.40).
    w_importance : float
        Weight for normalized hub importance term in H_r (default 0.60).

    Returns
    -------
    pd.DataFrame
        Route-level metrics DataFrame with unique 'route_id' and columns:
        ['route_id', 'hub_stop_count', 'hub_stop_ratio', 'hub_weighted_importance',
         'hub_connectivity_index', 'spatial_equity_indicator']
    """
    if route_stops_df is None or route_stops_df.empty:
        return pd.DataFrame(columns=[
            "route_id", "hub_stop_count", "hub_stop_ratio",
            "hub_weighted_importance", "hub_connectivity_index", "spatial_equity_indicator"
        ])

    # Work on clean copy to avoid mutating input
    rs_df = route_stops_df[["route_id", "stop_id"]].copy()
    rs_df["route_id"] = rs_df["route_id"].astype(str)
    rs_df["stop_id"] = rs_df["stop_id"].astype(str)
    rs_df = rs_df.drop_duplicates(subset=["route_id", "stop_id"])

    # Identify top-100 hub stop IDs
    top100_ids: Set[str] = set()
    if top100_hubs_df is not None and not top100_hubs_df.empty and "stop_id" in top100_hubs_df.columns:
        top100_ids = set(top100_hubs_df["stop_id"].astype(str).unique())

    # Identify peripheral / noise stop IDs
    peripheral_ids: Set[str] = set()
    if peripheral_stops_df is not None and not peripheral_stops_df.empty and "stop_id" in peripheral_stops_df.columns:
        peripheral_ids = set(peripheral_stops_df["stop_id"].astype(str).unique())

    # Determine hub score column
    score_col = None
    hub_score_map = {}
    if hub_rankings_df is not None and not hub_rankings_df.empty and "stop_id" in hub_rankings_df.columns:
        for candidate in ["composite_hub_score_a", "composite_hub_score", "hub_score", "score"]:
            if candidate in hub_rankings_df.columns:
                score_col = candidate
                break
        if score_col is not None:
            clean_scores = hub_rankings_df[["stop_id", score_col]].dropna().copy()
            clean_scores["stop_id"] = clean_scores["stop_id"].astype(str)
            hub_score_map = dict(zip(clean_scores["stop_id"], clean_scores[score_col].astype(float)))

    # Compute metrics per route
    records = []
    for route_id, group in rs_df.groupby("route_id"):
        stops = set(group["stop_id"].unique())
        total_stops = len(stops)

        if total_stops == 0:
            records.append({
                "route_id": route_id,
                "hub_stop_count": 0,
                "hub_stop_ratio": 0.0,
                "hub_weighted_importance": 0.0,
                "spatial_equity_indicator": 0.0,
            })
            continue

        # Intersect with top-100 hubs
        hub_stops = stops.intersection(top100_ids)
        hub_stop_count = len(hub_stops)
        hub_stop_ratio = float(hub_stop_count / total_stops)

        # Weighted importance: sum of hub scores for intersecting hub stops
        hub_importance = sum(hub_score_map.get(sid, 0.0) for sid in hub_stops)

        # Spatial equity indicator: fraction of stops in peripheral / noise clusters
        periph_stops = stops.intersection(peripheral_ids)
        periph_ratio = float(len(periph_stops) / total_stops)

        records.append({
            "route_id": route_id,
            "hub_stop_count": int(hub_stop_count),
            "hub_stop_ratio": float(np.clip(hub_stop_ratio, 0.0, 1.0)),
            "hub_weighted_importance": float(hub_importance),
            "spatial_equity_indicator": float(np.clip(periph_ratio, 0.0, 1.0)),
        })

    result_df = pd.DataFrame(records)
    if result_df.empty:
        return pd.DataFrame(columns=[
            "route_id", "hub_stop_count", "hub_stop_ratio",
            "hub_weighted_importance", "hub_connectivity_index", "spatial_equity_indicator"
        ])

    # Compute composite Hub Connectivity Index H_r
    max_imp = result_df["hub_weighted_importance"].max()
    if max_imp > 0.0:
        norm_imp = result_df["hub_weighted_importance"] / max_imp
    else:
        norm_imp = pd.Series(0.0, index=result_df.index)

    result_df["hub_connectivity_index"] = (
        w_ratio * result_df["hub_stop_ratio"] + w_importance * norm_imp
    ).clip(0.0, 1.0)

    return result_df


def compute_pattern_hub_metrics(
    pattern_stops_df: pd.DataFrame,
    top100_hubs_df: pd.DataFrame,
    hub_rankings_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Computes directional route-pattern level hub connectivity metrics (N=261 patterns).

    Parameters
    ----------
    pattern_stops_df : pd.DataFrame
        DataFrame with pattern-to-stop mapping containing ['pattern_id', 'route_id', 'direction_id', 'stop_id'].
    top100_hubs_df : pd.DataFrame
        Phase 6.1 Top-100 transit hubs containing ['stop_id'].
    hub_rankings_df : pd.DataFrame
        Phase 6.1 stop-level rankings containing ['stop_id'] and hub score.

    Returns
    -------
    pd.DataFrame
        Pattern-level metrics DataFrame with unique 'pattern_id'.
    """
    if pattern_stops_df is None or pattern_stops_df.empty:
        return pd.DataFrame(columns=[
            "pattern_id", "route_id", "direction_id", "hub_stop_count", "hub_stop_ratio"
        ])

    ps_df = pattern_stops_df.copy()
    ps_df["pattern_id"] = ps_df["pattern_id"].astype(str)
    ps_df["stop_id"] = ps_df["stop_id"].astype(str)

    top100_ids: Set[str] = set()
    if top100_hubs_df is not None and not top100_hubs_df.empty and "stop_id" in top100_hubs_df.columns:
        top100_ids = set(top100_hubs_df["stop_id"].astype(str).unique())

    records = []
    for pattern_id, group in ps_df.groupby("pattern_id"):
        route_id = str(group["route_id"].iloc[0]) if "route_id" in group.columns else pattern_id.split("_")[0]
        direction_id = int(group["direction_id"].iloc[0]) if "direction_id" in group.columns else 0
        stops = set(group["stop_id"].unique())
        total_stops = len(stops)

        hub_stops = stops.intersection(top100_ids)
        hub_count = len(hub_stops)
        hub_ratio = float(hub_count / total_stops) if total_stops > 0 else 0.0

        records.append({
            "pattern_id": pattern_id,
            "route_id": route_id,
            "direction_id": direction_id,
            "hub_stop_count": int(hub_count),
            "hub_stop_ratio": float(np.clip(hub_ratio, 0.0, 1.0)),
        })

    return pd.DataFrame(records)
