"""
AI_RouteRanker - Phase 6.3 Passenger Demand Integrator Module
Integrates pre-trained Milestone 5 Random Forest passenger demand forecasts with
canonical GTFS operational supply metrics while preserving rail ridership as NaN.
"""

from typing import Optional, Any, Dict, List
import pandas as pd
import numpy as np

from analytics.ranking.config import RankerConfig


def integrate_demand_predictions(
    operational_features_df: pd.DataFrame,
    model_ready_features_df: Optional[pd.DataFrame] = None,
    rf_model: Optional[Any] = None,
    service_date: str = RankerConfig.REPRESENTATIVE_DATE,
    feature_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Integrates passenger demand forecasts with scheduled service operations.

    Parameters
    ----------
    operational_features_df : pd.DataFrame
        Route-level operational baseline containing at least:
        ['route_id', 'is_rail', 'scheduled_trips', 'route_length_km',
         'service_span_hours', 'historical_mean_daily_rides'].
    model_ready_features_df : Optional[pd.DataFrame]
        Validated feature records containing historical and scheduled predictors for inference.
        May also contain precomputed 'predicted_rides' or 'forecasted_daily_demand'.
    rf_model : Optional[Any]
        Trained Random Forest estimator supporting .predict(X).
    service_date : str
        Canonical service date for demand alignment (default '2026-06-10').
    feature_cols : Optional[List[str]]
        Explicit list of feature column names required by rf_model.

    Returns
    -------
    pd.DataFrame
        DataFrame with route-level demand integration:
        ['route_id', 'historical_mean_daily_rides', 'forecasted_daily_demand',
         'rides_per_trip', 'load_intensity_factor']
    """
    if operational_features_df is None or operational_features_df.empty:
        return pd.DataFrame(columns=[
            "route_id", "historical_mean_daily_rides", "forecasted_daily_demand",
            "rides_per_trip", "load_intensity_factor"
        ])

    ops_df = operational_features_df.copy()
    ops_df["route_id"] = ops_df["route_id"].astype(str)

    # Determine is_rail flag cleanly
    if "is_rail" not in ops_df.columns:
        ops_df["is_rail"] = ops_df["route_id"].isin(RankerConfig.RAIL_ROUTE_IDS)
    else:
        ops_df["is_rail"] = ops_df["is_rail"].astype(bool) | ops_df["route_id"].isin(RankerConfig.RAIL_ROUTE_IDS)

    # Map of predicted demand per route
    predicted_demand_map: Dict[str, float] = {}

    # Case 1: Model-ready features DataFrame provided
    if model_ready_features_df is not None and not model_ready_features_df.empty:
        mrf = model_ready_features_df.copy()
        if "route_id" in mrf.columns:
            mrf["route_id"] = mrf["route_id"].astype(str)

            # Filter to canonical service date if date column present
            date_col = next((c for c in ["service_date", "date"] if c in mrf.columns), None)
            if date_col is not None:
                date_mask = mrf[date_col].astype(str).str.startswith(service_date)
                if date_mask.any():
                    mrf = mrf[date_mask]

            # If precomputed predictions already exist in mrf
            pred_col = next((c for c in ["predicted_rides", "forecasted_daily_demand", "predicted_demand"] if c in mrf.columns), None)
            if pred_col is not None:
                for _, row in mrf.iterrows():
                    rid = str(row["route_id"])
                    val = row[pred_col]
                    if pd.notna(val):
                        predicted_demand_map[rid] = float(val)

            # If rf_model provided, run inference on model-ready features
            elif rf_model is not None and hasattr(rf_model, "predict"):
                if feature_cols is not None:
                    avail_cols = [c for c in feature_cols if c in mrf.columns]
                else:
                    # Exclude non-feature columns
                    non_feat = {"route_id", "date", "service_date", "day_type", "rides", "target"}
                    avail_cols = [c for c in mrf.columns if c not in non_feat and pd.api.types.is_numeric_dtype(mrf[c])]

                if avail_cols:
                    # Predict per route
                    for rid, group in mrf.groupby("route_id"):
                        X = group[avail_cols].fillna(0.0)
                        preds = rf_model.predict(X)
                        predicted_demand_map[rid] = float(np.mean(preds))

    # Compute demand metrics per route
    records = []
    for _, row in ops_df.iterrows():
        route_id = str(row["route_id"])
        is_rail = bool(row["is_rail"])
        trips = float(row.get("scheduled_trips", 0))
        length_km = float(row.get("route_length_km", 0.0))

        # Preserve historical ridership from ops_df
        raw_hist = row.get("historical_mean_daily_rides", np.nan)
        if is_rail:
            # STRICT POLICY: Rail ridership is NaN (originates in station turnstiles, not bus fareboxes)
            hist_rides = np.nan
            forecasted_demand = np.nan
            rides_per_trip = np.nan
            load_factor = np.nan
        else:
            hist_rides = float(raw_hist) if pd.notna(raw_hist) else np.nan

            # Determine forecasted demand
            if route_id in predicted_demand_map:
                forecasted_demand = float(predicted_demand_map[route_id])
            elif pd.notna(raw_hist):
                # Fallback to historical mean if model forecast not available for this route
                forecasted_demand = float(raw_hist)
            else:
                forecasted_demand = np.nan

            # Rides per scheduled trip
            if pd.notna(forecasted_demand) and trips > 0:
                rides_per_trip = float(forecasted_demand / trips)
            else:
                rides_per_trip = np.nan

            # Demand pressure / Load intensity factor: demand / (trips * length_km)
            if pd.notna(forecasted_demand) and trips > 0 and length_km > 0:
                load_factor = float(forecasted_demand / (trips * length_km))
            else:
                load_factor = np.nan

        records.append({
            "route_id": route_id,
            "historical_mean_daily_rides": hist_rides,
            "forecasted_daily_demand": forecasted_demand,
            "rides_per_trip": rides_per_trip,
            "load_intensity_factor": load_factor,
        })

    return pd.DataFrame(records)
