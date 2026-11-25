"""
AI_RouteRanker - Phase 6.3 Route Ranker Feature Synthesis Module
Harmonizes operational baseline, KMeans typology, transit hub connectivity,
corridor co-routing, and demand forecasts into the canonical 24-feature schema.
"""

from typing import Dict, List, Optional, Tuple, Any, Set
import pandas as pd
import numpy as np

from analytics.ranking.config import RankerConfig


def synthesize_route_ranker_features(
    operational_df: pd.DataFrame,
    kmeans_df: Optional[pd.DataFrame] = None,
    hub_metrics_df: Optional[pd.DataFrame] = None,
    corridor_metrics_df: Optional[pd.DataFrame] = None,
    demand_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Synthesizes all multi-criteria dimensions into the canonical 24-feature schema.

    Parameters
    ----------
    operational_df : pd.DataFrame
        Route-level operational features (133 routes) containing GTFS supply metrics.
    kmeans_df : Optional[pd.DataFrame]
        Champion KMeans operational typology cluster assignments (130 routes).
    hub_metrics_df : Optional[pd.DataFrame]
        Transit hub connectivity and spatial equity metrics.
    corridor_metrics_df : Optional[pd.DataFrame]
        Corridor buffer overlap and shared consecutive stop metrics.
    demand_df : Optional[pd.DataFrame]
        Integrated passenger demand forecasts and load intensity factors.

    Returns
    -------
    pd.DataFrame
        Unified feature master DataFrame with the approved 24 feature dimensions
        plus composite index columns.
    """
    if operational_df is None or operational_df.empty:
        raise ValueError("operational_df cannot be None or empty for feature synthesis.")

    # Start with operational features copy
    master = operational_df.copy()
    master["route_id"] = master["route_id"].astype(str)

    # 1. Merge KMeans Operational Typology
    if kmeans_df is not None and not kmeans_df.empty:
        km = kmeans_df.copy()
        km["route_id"] = km["route_id"].astype(str)

        # Locate cluster columns
        cluster_col = next((c for c in ["operational_cluster_k3", "cluster", "cluster_id"] if c in km.columns), None)
        label_col = next((c for c in ["operational_cluster_label", "cluster_label", "label"] if c in km.columns), None)

        cols_to_merge = ["route_id"]
        if cluster_col and cluster_col != "route_id":
            cols_to_merge.append(cluster_col)
        if label_col and label_col != "route_id":
            cols_to_merge.append(label_col)

        km_sub = km[cols_to_merge].drop_duplicates(subset=["route_id"])
        # Rename if necessary
        rename_dict = {}
        if cluster_col and cluster_col != "operational_cluster_k3":
            rename_dict[cluster_col] = "operational_cluster_k3"
        if label_col and label_col != "operational_cluster_label":
            rename_dict[label_col] = "operational_cluster_label"
        if rename_dict:
            km_sub = km_sub.rename(columns=rename_dict)

        master = master.merge(km_sub, on="route_id", how="left")
    else:
        if "operational_cluster_k3" not in master.columns:
            master["operational_cluster_k3"] = np.nan
        if "operational_cluster_label" not in master.columns:
            master["operational_cluster_label"] = np.nan

    # 2. Merge Transit Hub Metrics
    if hub_metrics_df is not None and not hub_metrics_df.empty:
        hm = hub_metrics_df.copy()
        hm["route_id"] = hm["route_id"].astype(str)
        hm_cols = [c for c in hm.columns if c == "route_id" or c not in master.columns]
        master = master.merge(hm[hm_cols].drop_duplicates(subset=["route_id"]), on="route_id", how="left")

    # Ensure hub metric columns exist with default 0 if missing
    for col in ["hub_stop_count", "hub_stop_ratio", "hub_weighted_importance", "hub_connectivity_index", "spatial_equity_indicator"]:
        if col not in master.columns:
            master[col] = 0.0 if "ratio" in col or "importance" in col or "index" in col or "indicator" in col else 0
        else:
            if "count" in col:
                master[col] = master[col].fillna(0).astype(int)
            else:
                master[col] = master[col].fillna(0.0).astype(float)

    # 3. Merge Corridor Metrics
    if corridor_metrics_df is not None and not corridor_metrics_df.empty:
        cm = corridor_metrics_df.copy()
        cm["route_id"] = cm["route_id"].astype(str)
        cm_cols = [c for c in cm.columns if c == "route_id" or c not in master.columns]
        master = master.merge(cm[cm_cols].drop_duplicates(subset=["route_id"]), on="route_id", how="left")

    # Ensure corridor columns exist
    for col in ["max_corridor_overlap", "mean_corridor_overlap", "corridor_duplication_ratio", "corridor_duplication_index"]:
        if col not in master.columns:
            master[col] = 0.0
        else:
            master[col] = master[col].fillna(0.0).astype(float)

    if "shared_consecutive_stop_count" not in master.columns:
        master["shared_consecutive_stop_count"] = 0
    else:
        master["shared_consecutive_stop_count"] = master["shared_consecutive_stop_count"].fillna(0).astype(int)

    if "regional_partition" not in master.columns:
        master["regional_partition"] = "North Chicago"
    else:
        master["regional_partition"] = master["regional_partition"].fillna("North Chicago").astype(str)

    # 4. Merge Demand Predictions
    if demand_df is not None and not demand_df.empty:
        dm = demand_df.copy()
        dm["route_id"] = dm["route_id"].astype(str)
        # We want to update or fill demand columns
        demand_fields = ["forecasted_daily_demand", "rides_per_trip", "load_intensity_factor"]
        for fld in demand_fields:
            if fld in dm.columns:
                val_map = dict(zip(dm["route_id"], dm[fld]))
                master[fld] = master["route_id"].map(val_map)
            elif fld not in master.columns:
                master[fld] = np.nan
    else:
        for fld in ["forecasted_daily_demand", "rides_per_trip", "load_intensity_factor"]:
            if fld not in master.columns:
                master[fld] = np.nan

    # 5. Route Identity and Rail Policy Enforcement
    if "is_rail" not in master.columns:
        master["is_rail"] = master["route_id"].isin(RankerConfig.RAIL_ROUTE_IDS)
    else:
        master["is_rail"] = master["is_rail"].astype(bool) | master["route_id"].isin(RankerConfig.RAIL_ROUTE_IDS)

    # Rail routes MUST have NaN for ridership and demand metrics
    rail_mask = master["is_rail"] == True
    for ridership_col in ["historical_mean_daily_rides", "forecasted_daily_demand", "rides_per_trip", "load_intensity_factor"]:
        if ridership_col in master.columns:
            master.loc[rail_mask, ridership_col] = np.nan

    # Fill route names if missing
    if "route_short_name" not in master.columns:
        master["route_short_name"] = master["route_id"]
    else:
        master["route_short_name"] = master["route_short_name"].fillna(master["route_id"]).astype(str)

    if "route_long_name" not in master.columns:
        master["route_long_name"] = master["route_short_name"]
    else:
        master["route_long_name"] = master["route_long_name"].fillna(master["route_short_name"]).astype(str)

    if "route_type" not in master.columns:
        # Default: 1 for rail, 3 for bus
        master["route_type"] = master["is_rail"].map(lambda is_r: 1 if is_r else 3)
    else:
        master["route_type"] = master["route_type"].astype(int)

    # Format numeric types cleanly
    int_cols = ["scheduled_trips", "unique_stops_count", "hub_stop_count", "shared_consecutive_stop_count", "route_type"]
    for ic in int_cols:
        if ic in master.columns:
            master[ic] = master[ic].fillna(0).astype(int)

    float_cols = [
        "service_span_hours", "am_headway_min", "route_length_km",
        "historical_mean_daily_rides", "forecasted_daily_demand", "rides_per_trip",
        "hub_stop_ratio", "hub_weighted_importance", "max_corridor_overlap",
        "mean_corridor_overlap", "corridor_duplication_ratio", "load_intensity_factor",
        "hub_connectivity_index", "corridor_duplication_index", "spatial_equity_indicator"
    ]
    for fc in float_cols:
        if fc in master.columns:
            master[fc] = pd.to_numeric(master[fc], errors="coerce")

    # Order columns starting with approved 24 features
    ordered_cols = [c for c in RankerConfig.APPROVED_24_FEATURES if c in master.columns]
    extra_cols = [c for c in master.columns if c not in ordered_cols]
    master = master[ordered_cols + extra_cols]

    return master


def normalize_features(
    df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
    p_min: float = RankerConfig.PERCENTILE_MIN,
    p_max: float = RankerConfig.PERCENTILE_MAX,
    suffix: str = "_norm",
) -> Tuple[pd.DataFrame, Dict[str, Dict[str, float]]]:
    """
    Applies percentile-clipped MinMax normalization to numeric features.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.
    feature_cols : Optional[List[str]]
        Columns to normalize. Defaults to numeric continuous columns in APPROVED_24_FEATURES.
    p_min : float
        Lower percentile clipping bound (default 1.0).
    p_max : float
        Upper percentile clipping bound (default 99.0).
    suffix : str
        Suffix for normalized column names (default '_norm').

    Returns
    -------
    Tuple[pd.DataFrame, Dict[str, Dict[str, float]]]
        DataFrame with added normalized columns, and dictionary of normalization parameters.
    """
    result_df = df.copy()
    norm_params: Dict[str, Dict[str, float]] = {}

    if feature_cols is None:
        # Select numeric columns that are not excluded identifiers/categoricals
        feature_cols = [
            c for c in RankerConfig.APPROVED_24_FEATURES
            if c in result_df.columns
            and c not in RankerConfig.NON_NORMALIZED_COLUMNS
            and pd.api.types.is_numeric_dtype(result_df[c])
        ]

    for col in feature_cols:
        if col not in result_df.columns:
            continue

        s = result_df[col].dropna()
        norm_col_name = f"{col}{suffix}"

        if s.empty:
            result_df[norm_col_name] = np.nan
            norm_params[col] = {"q_low": np.nan, "q_high": np.nan, "is_constant": True}
            continue

        q_low = float(np.percentile(s, p_min))
        q_high = float(np.percentile(s, p_max))

        if q_high > q_low:
            # Normal percentile minmax scaling
            clipped = result_df[col].clip(lower=q_low, upper=q_high)
            result_df[norm_col_name] = (clipped - q_low) / (q_high - q_low)
            norm_params[col] = {"q_low": q_low, "q_high": q_high, "is_constant": False}
        else:
            # Constant-valued column protection: avoid division by zero!
            # If all values identical or q_high == q_low, map non-null to 0.5 (or 0.0)
            result_df[norm_col_name] = result_df[col].map(lambda x: 0.5 if pd.notna(x) else np.nan)
            norm_params[col] = {"q_low": q_low, "q_high": q_high, "is_constant": True}

    return result_df, norm_params


def validate_feature_master(
    df: pd.DataFrame,
    expected_total: int = RankerConfig.EXPECTED_TOTAL_ROUTES,
    expected_bus: int = RankerConfig.EXPECTED_BUS_ROUTES,
    expected_rail: int = RankerConfig.EXPECTED_RAIL_ROUTES,
) -> Dict[str, Any]:
    """
    Validates the synthesized route ranker feature master against project integrity rules.

    Parameters
    ----------
    df : pd.DataFrame
        Synthesized route ranker feature master DataFrame.
    expected_total : int
        Expected total route count (default 133).
    expected_bus : int
        Expected bus route count (default 125).
    expected_rail : int
        Expected rail route count (default 8).

    Returns
    -------
    Dict[str, Any]
        Dictionary with validation results: 'is_valid', 'errors', 'warnings', and 'checks'.
    """
    errors: List[str] = []
    warnings: List[str] = []
    checks: Dict[str, bool] = {}

    # 1. Total row count check
    total_rows = len(df)
    checks["total_route_count"] = (total_rows == expected_total)
    if not checks["total_route_count"]:
        errors.append(f"Total routes mismatch: expected {expected_total}, got {total_rows}")

    # 2. Unique route_id primary key check
    if "route_id" in df.columns:
        unique_ids = df["route_id"].nunique()
        checks["unique_route_ids"] = (unique_ids == total_rows)
        if not checks["unique_route_ids"]:
            errors.append(f"Duplicate route_ids detected: {unique_ids} unique out of {total_rows} rows")
    else:
        checks["unique_route_ids"] = False
        errors.append("Missing primary key column 'route_id'")

    # 3. Rail and bus breakdown check
    if "is_rail" in df.columns:
        rail_count = int(df["is_rail"].sum())
        bus_count = total_rows - rail_count
        checks["rail_count"] = (rail_count == expected_rail)
        checks["bus_count"] = (bus_count == expected_bus)
        if not checks["rail_count"]:
            errors.append(f"Rail route count mismatch: expected {expected_rail}, got {rail_count}")
        if not checks["bus_count"]:
            errors.append(f"Bus route count mismatch: expected {expected_bus}, got {bus_count}")
    else:
        checks["rail_count"] = False
        checks["bus_count"] = False
        errors.append("Missing 'is_rail' column")

    # 4. Required feature schema completeness
    missing_features = [f for f in RankerConfig.APPROVED_24_FEATURES if f not in df.columns]
    checks["schema_completeness"] = (len(missing_features) == 0)
    if missing_features:
        errors.append(f"Missing approved feature columns: {missing_features}")

    # 5. Nullability constraint validation
    for col in df.columns:
        if col in RankerConfig.APPROVED_24_FEATURES and col not in RankerConfig.NULLABLE_COLUMNS:
            null_count = df[col].isnull().sum()
            if null_count > 0:
                errors.append(f"Column '{col}' is non-nullable but contains {null_count} nulls")

    # 6. Rail ridership nullability policy check
    if "is_rail" in df.columns:
        rail_df = df[df["is_rail"] == True]
        for col in ["historical_mean_daily_rides", "forecasted_daily_demand", "rides_per_trip", "load_intensity_factor"]:
            if col in rail_df.columns:
                non_null_rail = rail_df[col].dropna().count()
                if non_null_rail > 0:
                    errors.append(f"Rail policy violation: {non_null_rail} rail routes have non-null '{col}'")

    # 7. Bounded index range checks
    ratio_cols = [
        "hub_stop_ratio", "max_corridor_overlap", "mean_corridor_overlap",
        "corridor_duplication_ratio", "hub_connectivity_index", "corridor_duplication_index",
        "spatial_equity_indicator"
    ]
    for rc in ratio_cols:
        if rc in df.columns:
            s = df[rc].dropna()
            if (s < -1e-6).any() or (s > 1.0 + 1e-6).any():
                errors.append(f"Bounded ratio '{rc}' has values outside [0, 1]: min={s.min():.4f}, max={s.max():.4f}")

    is_valid = len(errors) == 0
    return {
        "is_valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }
