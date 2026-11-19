"""Builds replay forecasts with the frozen Step 5 model.

The model file (models/final_forecaster.joblib) is opened read-only. It is never
refitted here.

Information policy for a forecast issued on virtual day D:
- Issue time is the start of D (00:00), before any of D's buses run.
- Horizon is the same service day D, hour by hour.
- Reporting delay is `delay_days`. Boardings from dates up to D - delay_days may
  be used. Anything later is hidden from the model, even though the offline
  file has it.
- Schedule inputs come from the GTFS archive captured on 2026-10-17, which is
  earlier than every replay issue date (2026-10-18 onward).

The lag values themselves (boardings 7, 14, 21 and 28 days earlier, same hour)
are taken from app_data/october_hourly_forecast_vs_actual.parquet. Each lag is
blanked out when its date is later than D - delay_days. With a delay of 7 days
or less every lag is allowed, and the output matches the saved October check.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "models" / "final_forecaster.joblib"

REPLAY_START = "2026-10-18"
REPLAY_END = "2026-10-31"
SCHEDULE_SNAPSHOT = "2026-10-17"
LAG_DAYS = (7, 14, 21, 28)
ALLOWED_DELAYS = (1, 7, 14, 21)


@lru_cache(maxsize=1)
def load_frozen_model(path: str = str(MODEL_PATH)) -> dict:
    bundle = joblib.load(path)
    card = bundle.get("model_card", {}) if isinstance(bundle, dict) else {}
    return {"pipeline": bundle["pipeline"], "model_card": card}


def model_version_label(card: dict) -> str:
    window = str(card.get("training_date_window") or "2026-01-04 to 2026-07-31").split(" (")[0]
    created = str(card.get("created_at_utc") or "")[:10]
    suffix = f", saved {created}" if created else ""
    return f"final_forecaster.joblib (HistGradientBoosting, trained {window}{suffix})"


def model_input_features(card: dict) -> list[str]:
    feats = card.get("input_features")
    if isinstance(feats, str):
        import ast

        feats = ast.literal_eval(feats)
    if feats:
        return list(feats)
    return [
        "route", "day_of_week", "time_band", "trips_running", "trips_starting", "service_hours",
        "route_length_km", "stop_count", "hour_sin", "hour_cos", "is_weekend", "is_public_holiday",
        "holiday_schedule", "is_storm", "is_sbs", "is_24h", "lag_7d", "lag_14d", "lag_21d",
        "lag_28d", "lag_mean_available", "lags_available_count",
    ]


def build_day_inputs(
    october: pd.DataFrame,
    route_features: pd.DataFrame,
    target_date: str,
    delay_days: int,
) -> pd.DataFrame:
    """Return model input rows for one target date with lags limited by the delay policy."""
    day = october[october["date"] == target_date].copy()
    if day.empty:
        return day

    latest_allowed = (pd.Timestamp(target_date) - pd.Timedelta(days=delay_days)).strftime("%Y-%m-%d")
    for k in LAG_DAYS:
        lag_date = (pd.Timestamp(target_date) - pd.Timedelta(days=k)).strftime("%Y-%m-%d")
        if lag_date > latest_allowed:
            day[f"lag_{k}d"] = np.nan

    lag_cols = [f"lag_{k}d" for k in LAG_DAYS]
    day["lags_available_count"] = day[lag_cols].notnull().sum(axis=1).astype("int8")
    mean_val = day[lag_cols].mean(axis=1)
    day["lag_mean_available"] = np.where(day["lags_available_count"] >= 2, mean_val.round(2), np.nan)

    day = day.drop(columns=[c for c in ("route_length_km", "stop_count", "is_sbs", "is_24h") if c in day.columns])
    day = day.merge(route_features, on="route", how="left")
    day["is_weekend"] = day["day_of_week"].isin(["Saturday", "Sunday"])
    day["hour_sin"] = np.sin(2 * np.pi * day["hour"] / 24.0).round(4)
    day["hour_cos"] = np.cos(2 * np.pi * day["hour"] / 24.0).round(4)
    day["latest_ridership_date_used"] = latest_allowed
    return day


def forecast_day(
    october: pd.DataFrame,
    route_features: pd.DataFrame,
    target_date: str,
    delay_days: int,
) -> pd.DataFrame:
    """Run the frozen model for every scheduled route-hour on target_date."""
    bundle = load_frozen_model()
    pipe = bundle["pipeline"]
    feats = model_input_features(bundle["model_card"])
    day = build_day_inputs(october, route_features, target_date, delay_days)
    if day.empty:
        return day
    preds = np.clip(pipe.predict(day[feats]), 0.0, None)
    day["pred_boardings"] = np.round(preds, 3)
    day["baseline_boardings"] = day["lag_mean_available"]
    day["status"] = np.where(
        day["trips_running"] <= 0,
        "unavailable_no_scheduled_trips",
        np.where(day["lags_available_count"] < len(LAG_DAYS), "normal_fewer_lags", "normal"),
    )
    return day
