"""Leakage-aware one-day inference for a saved RouteRanker v3 bundle."""

from pathlib import Path

import joblib
import pandas as pd

from .preprocessing_v3 import apply_service_features, make_forecasting_features
from .train_v3 import predict_feature_rows


def predict_daily_routes(
    model_path: str | Path,
    observations: pd.DataFrame,
    target_rows: pd.DataFrame,
    service_rows: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Forecast route rides for one issue date using only available inputs.

    ``observations`` must contain route/date/daytype/rides through the permitted
    reporting cutoff. ``target_rows`` contains route/date/daytype, with all
    target dates equal to the single forecast issue date. For service-aware
    bundles, ``service_rows`` must include exact route/date keys and capture
    provenance; snapshots captured on the issue date or later are rejected.
    """
    bundle = joblib.load(model_path)
    if not isinstance(bundle, dict) or bundle.get("artifact_version") != "3.0.0":
        raise ValueError("Expected a RouteRanker v3.0.0 model bundle")
    if target_rows.empty:
        raise ValueError("target_rows must contain at least one route")
    if not {"route", "date", "daytype"}.issubset(target_rows.columns):
        raise ValueError("target_rows must contain route, date, and known daytype")
    targets = target_rows[["route", "date", "daytype"]].copy()
    targets["route"] = targets["route"].astype("string").str.strip()
    targets["date"] = pd.to_datetime(targets["date"], errors="coerce").dt.normalize()
    targets["daytype"] = targets["daytype"].astype("string").str.strip().str.upper()
    if targets.isna().any().any() or not targets["daytype"].isin(["W", "A", "U"]).all():
        raise ValueError("target_rows contain invalid route/date/daytype values")
    issue_dates = targets["date"].unique()
    if len(issue_dates) != 1:
        raise ValueError("Forecast one issue date at a time; rolling forecasts need fresh prior-day observations")
    issue_date = pd.Timestamp(issue_dates[0])
    reporting_delay = int(bundle["reporting_delay_days"])
    latest_allowed = issue_date - pd.Timedelta(days=reporting_delay)

    history = observations.copy()
    if not {"route", "date", "daytype", "rides"}.issubset(history.columns):
        raise ValueError("observations must contain route, date, daytype, and rides")
    history["date"] = pd.to_datetime(history["date"], errors="coerce").dt.normalize()
    if history["date"].isna().any() or (history["date"] > latest_allowed).any():
        raise ValueError(f"observations may include dates only through {latest_allowed.date()}")

    features = make_forecasting_features(
        history, reporting_delay_days=reporting_delay, target_rows=targets
    )
    if bundle.get("model_requires_schedule"):
        if service_rows is None:
            raise ValueError("The selected v3 model requires forecast-available service rows")
        if "archive_available_from" not in service_rows.columns:
            raise ValueError("service_rows must include archive_available_from provenance")
        features = apply_service_features(features, service_rows)
        if len(features) != len(targets):
            raise ValueError("Service rows must cover every target route/date exactly")

    predictions = predict_feature_rows(bundle, features)
    result = targets[["route", "date"]].copy()
    result["forecast_issue_date"] = issue_date
    result["latest_permitted_ridership_date"] = latest_allowed
    result["predicted_rides"] = predictions
    result["serving_method"] = bundle["serving_method"]
    return result.sort_values(["date", "route"]).reset_index(drop=True)
