"""Train/evaluate the forecasting experiment specified in RouteRanker guide v3."""

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data_loader import load_bus_ridership
from .preprocessing_v3 import (
    DEMAND_FEATURES,
    LAG_COLUMNS,
    SEASONAL_COLUMNS,
    SERVICE_FEATURES,
    apply_service_features,
    make_forecasting_features,
)

REFERENCE_RIDERSHIP_SHA256 = "6a999ea344084036310a779886bc6a72de6bad24cbb696e90822c83a337e608a"
MODEL_CANDIDATES = ("pooled_linear_regression", "random_forest", "hist_gradient_boosting_reference")
BASELINE_CANDIDATES = ("last_week_same_day", "past_four_same_weekdays")


def _score(actual, predicted) -> dict:
    actual_values = np.asarray(actual, dtype=float)
    predicted_values = np.maximum(np.asarray(predicted, dtype=float), 0)
    total = float(actual_values.sum())
    return {
        "mae": float(mean_absolute_error(actual_values, predicted_values)),
        "rmse": float(mean_squared_error(actual_values, predicted_values) ** 0.5),
        "wape": float(np.abs(actual_values - predicted_values).sum() / total) if total > 0 else None,
        "rows": int(len(actual_values)),
    }


def _new_estimator(name: str):
    if name == "pooled_linear_regression":
        return LinearRegression()
    if name == "random_forest":
        return RandomForestRegressor(
            n_estimators=300, min_samples_leaf=3, max_features=0.9,
            n_jobs=-1, random_state=42,
        )
    if name == "hist_gradient_boosting_reference":
        # Retained as a development reference because the earlier project used
        # histogram boosting; it is selected only if validation supports it.
        return HistGradientBoostingRegressor(
            max_iter=150, learning_rate=0.08, l2_regularization=1.0, random_state=42,
        )
    raise ValueError(f"Unknown estimator: {name}")


def _new_pipeline(feature_columns: list[str], estimator_name: str) -> Pipeline:
    categorical = ["route"]
    numeric = [column for column in feature_columns if column not in categorical]
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
        ("scale", StandardScaler()),
    ])
    preprocessing = ColumnTransformer([
        ("route", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical),
        ("numeric", numeric_pipeline, numeric),
    ])
    return Pipeline([("features", preprocessing), ("model", _new_estimator(estimator_name))])


def _route_day_fallbacks(fit_rows: pd.DataFrame) -> tuple[dict, float]:
    by_route_daytype = fit_rows.groupby(["route", "daytype"])["rides"].median().to_dict()
    global_median = float(fit_rows["rides"].median())
    return by_route_daytype, global_median


def _baseline_predictions(rows: pd.DataFrame, fit_rows: pd.DataFrame) -> tuple[dict[str, np.ndarray], dict]:
    """Baselines with the guide's explicit missing-history fallback order."""
    route_day_median, global_median = _route_day_fallbacks(fit_rows)
    route_day_values = np.asarray([
        route_day_median.get((row.route, row.daytype), global_median)
        for row in rows[["route", "daytype"]].itertuples(index=False)
    ], dtype=float)
    seasonal_lags = rows[SEASONAL_COLUMNS]
    count = rows["seasonal_lag_observations"].to_numpy(dtype=int)
    lag7 = pd.to_numeric(rows[LAG_COLUMNS[7]], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    seasonal_mean = seasonal_lags.mean(axis=1).to_numpy(dtype=float, na_value=np.nan)

    last_week_missing = ~np.isfinite(lag7)
    last_week = np.where(last_week_missing, route_day_values, lag7)
    seasonal_usable = (count >= 2) & np.isfinite(seasonal_mean)
    seasonal = np.where(seasonal_usable, seasonal_mean, lag7)
    seasonal_missing = ~np.isfinite(seasonal)
    seasonal = np.where(seasonal_missing, route_day_values, seasonal)

    predictions = {
        "last_week_same_day": np.maximum(last_week, 0),
        "past_four_same_weekdays": np.maximum(seasonal, 0),
    }
    has_route_day = np.asarray([
        (row.route, row.daytype) in route_day_median
        for row in rows[["route", "daytype"]].itertuples(index=False)
    ], dtype=bool)
    fallback_counts = {
        "last_week_same_day": {
            "lag_7": int((~last_week_missing).sum()),
            "route_daytype_median": int((last_week_missing & has_route_day).sum()),
            "global_median": int((last_week_missing & ~has_route_day).sum()),
        },
        "past_four_same_weekdays": {
            "seasonal_mean": int(seasonal_usable.sum()),
            "lag_7": int(((~seasonal_usable) & np.isfinite(lag7)).sum()),
            "route_daytype_median": int((seasonal_missing & has_route_day).sum()),
            "global_median": int((seasonal_missing & ~has_route_day).sum()),
        },
    }
    return predictions, fallback_counts


def predict_feature_rows(bundle: dict, rows: pd.DataFrame) -> np.ndarray:
    """Serve rows built with preprocessing_v3's feature contract."""
    method = bundle["serving_method"]
    if bundle.get("pipeline") is not None:
        prediction = bundle["pipeline"].predict(rows[bundle["features"]])
        return np.maximum(np.asarray(prediction, dtype=float), 0)

    route_day_median = bundle["baseline_route_day_median"]
    global_median = float(bundle["baseline_global_median"])
    fallback = np.asarray([
        route_day_median.get((str(row.route), str(row.daytype)), global_median)
        for row in rows[["route", "daytype"]].itertuples(index=False)
    ], dtype=float)
    lag7 = pd.to_numeric(rows[LAG_COLUMNS[7]], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    if method == "last_week_same_day":
        return np.maximum(np.where(np.isfinite(lag7), lag7, fallback), 0)
    if method == "past_four_same_weekdays":
        seasonal = rows[SEASONAL_COLUMNS].mean(axis=1).to_numpy(dtype=float, na_value=np.nan)
        count = rows["seasonal_lag_observations"].to_numpy(dtype=int)
        seasonal = np.where((count >= 2) & np.isfinite(seasonal), seasonal, lag7)
        return np.maximum(np.where(np.isfinite(seasonal), seasonal, fallback), 0)
    raise ValueError(f"The selected serving method is not recognized: {method}")


def _window_rows(features, start, end):
    return features.loc[features["date"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()


def _run_configuration(
    rows: pd.DataFrame,
    feature_columns: list[str],
    train_range: tuple[str, str],
    validation_range: tuple[str, str],
    test_range: tuple[str, str],
) -> dict:
    train_start, train_end = map(pd.Timestamp, train_range)
    validation_start, validation_end = map(pd.Timestamp, validation_range)
    test_start, test_end = map(pd.Timestamp, test_range)
    train_rows = rows.loc[rows["date"].between(train_start, train_end)].copy()
    validation_rows = rows.loc[rows["date"].between(validation_start, validation_end)].copy()
    test_rows = rows.loc[rows["date"].between(test_start, test_end)].copy()
    if any(part.empty for part in (train_rows, validation_rows, test_rows)):
        raise ValueError("Train, validation, or test partition is empty; check source data and matched coverage")

    validation_predictions, validation_metrics = {}, {}
    pipelines = {}
    for name in MODEL_CANDIDATES:
        candidate = _new_pipeline(feature_columns, name)
        candidate.fit(train_rows[feature_columns], train_rows["rides"])
        prediction = np.maximum(candidate.predict(validation_rows[feature_columns]), 0)
        validation_predictions[name] = prediction
        validation_metrics[name] = _score(validation_rows["rides"], prediction)

    validation_baselines, validation_fallback_counts = _baseline_predictions(validation_rows, train_rows)
    validation_predictions.update(validation_baselines)
    validation_metrics.update({
        name: _score(validation_rows["rides"], values)
        for name, values in validation_baselines.items()
    })
    selected_method = min(validation_metrics, key=lambda name: validation_metrics[name]["mae"])

    refit_rows = rows.loc[rows["date"].between(train_start, validation_end)].copy()
    test_predictions = {}
    for name in MODEL_CANDIDATES:
        pipeline = _new_pipeline(feature_columns, name)
        pipeline.fit(refit_rows[feature_columns], refit_rows["rides"])
        pipelines[name] = pipeline
        test_predictions[name] = np.maximum(pipeline.predict(test_rows[feature_columns]), 0)
    test_baselines, test_fallback_counts = _baseline_predictions(test_rows, refit_rows)
    test_predictions.update(test_baselines)
    test_metrics = {
        name: _score(test_rows["rides"], values)
        for name, values in test_predictions.items()
    }
    unseen_routes = ~test_rows["route"].isin(set(refit_rows["route"].astype(str)))
    selected_test_prediction = test_predictions[selected_method]
    selected_test_frame = test_rows[["route", "date", "daytype", "rides"]].copy()
    selected_test_frame["route"] = selected_test_frame["route"].astype(str)
    selected_test_frame["predicted_rides"] = selected_test_prediction
    selected_route_metrics = {
        str(route): _score(group["rides"], group["predicted_rides"])
        for route, group in selected_test_frame.groupby("route")
    }
    selected_daytype_metrics = {
        str(daytype): _score(group["rides"], group["predicted_rides"])
        for daytype, group in selected_test_frame.groupby("daytype")
    }
    return {
        "feature_columns": feature_columns,
        "partitions": {
            "train": {"start": train_range[0], "end": train_range[1], "rows": int(len(train_rows))},
            "validation": {"start": validation_range[0], "end": validation_range[1], "rows": int(len(validation_rows))},
            "test": {"start": test_range[0], "end": test_range[1], "rows": int(len(test_rows))},
        },
        "validation_metrics": validation_metrics,
        "validation_fallback_counts": validation_fallback_counts,
        "selected_method": selected_method,
        "test_metrics_by_method": test_metrics,
        "test_fallback_counts": test_fallback_counts,
        "selected_test_metrics": test_metrics[selected_method],
        "selected_route_metrics": selected_route_metrics,
        "selected_daytype_metrics": selected_daytype_metrics,
        "unseen_test_routes": {
            "rows": int(unseen_routes.sum()),
            "routes": sorted(test_rows.loc[unseen_routes, "route"].astype(str).unique().tolist()),
        },
        "test_rows": test_rows,
        "test_predictions": test_predictions,
        "pipelines": pipelines,
        "refit_rows": refit_rows,
    }


def _jsonable_configuration(result: dict) -> dict:
    """Remove in-memory pipelines and row-level frames from a run result."""
    keys = (
        "feature_columns", "partitions", "validation_metrics", "validation_fallback_counts",
        "selected_method", "test_metrics_by_method", "test_fallback_counts",
        "selected_test_metrics", "selected_route_metrics", "selected_daytype_metrics",
        "unseen_test_routes",
    )
    return {key: result[key] for key in keys}


def run_v3_experiment(
    ridership_path: str | Path,
    service_path: str | Path,
    model_path: str | Path = "models/cta_ridership_v3.joblib",
    report_path: str | Path = "outputs/reports/model_selection_v3.json",
    replay_forecasts_path: str | Path = "outputs/predictions/cta_june_july_replay_v3.csv",
    reporting_delay_days: int = 1,
    expected_reference_sha256: str | None = REFERENCE_RIDERSHIP_SHA256,
) -> dict:
    """Run the guide-v3 demand-only and paired service experiments.

    Candidate selection uses validation MAE across model families and both
    seasonal baselines. June-July paired test results are reported only after
    that choice is frozen. Target-date features follow the assumed reporting
    delay and schedule rows must come from a snapshot captured strictly before
    each target date.
    """
    ridership_path, service_path = Path(ridership_path), Path(service_path)
    source_sha256 = hashlib.sha256(ridership_path.read_bytes()).hexdigest()
    source = load_bus_ridership(ridership_path)
    features = make_forecasting_features(source, reporting_delay_days=reporting_delay_days)
    features = features.loc[features["date"].between("2024-08-01", "2026-07-31")].copy()
    if features.empty or features["date"].min() > pd.Timestamp("2024-08-01"):
        raise ValueError("The v3 reference window requires ridership history through at least 2024-08-01")
    if features["date"].max() < pd.Timestamp("2026-07-31"):
        raise ValueError("The v3 reference experiment requires observations through 2026-07-31")

    demand_reference = _run_configuration(
        features,
        DEMAND_FEATURES,
        ("2024-08-01", "2026-01-31"),
        ("2026-02-01", "2026-04-30"),
        ("2026-05-01", "2026-07-31"),
    )

    service_raw = pd.read_csv(service_path, dtype={"route": "string", "source_snapshot": "string"})
    if "archive_available_from" not in service_raw.columns:
        raise ValueError("Service table must record archive snapshot availability for v3 replay provenance")
    matched = apply_service_features(features, service_raw)
    if "archive_available_from" not in matched.columns:
        raise ValueError("Service table must retain archive_available_from for v3 replay provenance")
    # Enforce the conservative capture-date rule even if a source table was
    # generated by another tool or edited after import.
    available = pd.to_datetime(matched["archive_available_from"], errors="coerce").dt.normalize()
    if available.isna().any() or (available >= matched["date"]).any():
        raise ValueError("Matched schedule snapshots must be captured strictly before their target date")

    matched = matched.loc[matched["date"].between("2025-11-23", "2026-07-31")].copy()
    matched_demand = matched.drop(columns=[*SERVICE_FEATURES, "source_snapshot", "archive_available_from", "match_status"], errors="ignore")
    # Keep availability/provenance out of predictors and keep the same exact
    # train/validation/test route/date rows for both feature configurations.
    demand_fit = _run_configuration(
        matched_demand,
        DEMAND_FEATURES,
        ("2025-11-23", "2026-03-31"),
        ("2026-04-01", "2026-05-31"),
        ("2026-06-01", "2026-07-31"),
    )
    service_fit = _run_configuration(
        matched,
        [*DEMAND_FEATURES, *SERVICE_FEATURES],
        ("2025-11-23", "2026-03-31"),
        ("2026-04-01", "2026-05-31"),
        ("2026-06-01", "2026-07-31"),
    )

    paired_validation = {
        "last_week_same_day": demand_fit["validation_metrics"]["last_week_same_day"],
        "past_four_same_weekdays": demand_fit["validation_metrics"]["past_four_same_weekdays"],
    }
    paired_test = {
        "last_week_same_day": demand_fit["test_metrics_by_method"]["last_week_same_day"],
        "past_four_same_weekdays": demand_fit["test_metrics_by_method"]["past_four_same_weekdays"],
    }
    paired_test_predictions = {
        "last_week_same_day": demand_fit["test_predictions"]["last_week_same_day"],
        "past_four_same_weekdays": demand_fit["test_predictions"]["past_four_same_weekdays"],
    }
    for configuration, result in (("demand_only", demand_fit), ("service_aware", service_fit)):
        for method in MODEL_CANDIDATES:
            paired_validation[f"{configuration}::{method}"] = result["validation_metrics"][method]
            paired_test[f"{configuration}::{method}"] = result["test_metrics_by_method"][method]
            paired_test_predictions[f"{configuration}::{method}"] = result["test_predictions"][method]
    selected_method = min(paired_validation, key=lambda name: paired_validation[name]["mae"])
    if "::" in selected_method:
        selected_configuration, selected_estimator = selected_method.split("::", 1)
        selected_run = demand_fit if selected_configuration == "demand_only" else service_fit
        selected_pipeline = selected_run["pipelines"][selected_estimator]
        selected_features = selected_run["feature_columns"]
        requires_schedule = selected_configuration == "service_aware"
    else:
        selected_configuration = "baseline"
        selected_estimator = selected_method
        selected_pipeline = None
        selected_features = []
        requires_schedule = False

    test_actual_rows = demand_fit["test_rows"]
    selected_prediction = paired_test_predictions[selected_method]
    selected_test_diagnostics = test_actual_rows[["route", "date", "daytype", "rides"]].copy()
    selected_test_diagnostics["predicted_rides"] = np.maximum(
        np.asarray(selected_prediction, dtype=float), 0
    )
    selected_route_metrics = {
        str(route): _score(group["rides"], group["predicted_rides"])
        for route, group in selected_test_diagnostics.groupby("route")
    }
    selected_daytype_metrics = {
        str(daytype): _score(group["rides"], group["predicted_rides"])
        for daytype, group in selected_test_diagnostics.groupby("daytype")
    }
    selected_forecasts = pd.DataFrame({
        "route": test_actual_rows["route"].astype(str).to_numpy(),
        "target_date": test_actual_rows["date"].dt.strftime("%Y-%m-%d").to_numpy(),
        "forecast_issue_date": test_actual_rows["date"].dt.strftime("%Y-%m-%d").to_numpy(),
        "latest_permitted_ridership_date": (
            test_actual_rows["date"] - pd.Timedelta(days=reporting_delay_days)
        ).dt.strftime("%Y-%m-%d").to_numpy(),
        "predicted_rides": np.maximum(np.asarray(selected_prediction, dtype=float), 0),
        "serving_method": selected_method,
    })
    if requires_schedule:
        schedule_info = service_fit["test_rows"][[
            "route", "date", "scheduled_trips", "scheduled_service_hours",
            "source_snapshot", "archive_available_from",
        ]].copy()
        schedule_info["route"] = schedule_info["route"].astype(str)
        schedule_info["target_date"] = schedule_info["date"].dt.strftime("%Y-%m-%d")
        schedule_info["archive_available_from"] = pd.to_datetime(
            schedule_info["archive_available_from"]
        ).dt.strftime("%Y-%m-%d")
        selected_forecasts = selected_forecasts.merge(
            schedule_info[[
                "route", "target_date", "scheduled_trips", "scheduled_service_hours",
                "source_snapshot", "archive_available_from",
            ]], on=["route", "target_date"], how="left", validate="one_to_one",
        )
    else:
        selected_forecasts["scheduled_trips"] = pd.NA
        selected_forecasts["scheduled_service_hours"] = pd.NA
        selected_forecasts["source_snapshot"] = pd.NA
        selected_forecasts["archive_available_from"] = pd.NA
    selected_forecasts["reporting_delay_days"] = reporting_delay_days
    selected_forecasts["prediction_mode"] = "daily rolling one-step historical replay"

    outcomes = test_actual_rows[["route", "date", "daytype", "rides"]].copy()
    outcomes["route"] = outcomes["route"].astype(str)
    outcomes["date"] = outcomes["date"].dt.strftime("%Y-%m-%d")

    model_path, report_path, replay_forecasts_path = map(Path, (model_path, report_path, replay_forecasts_path))
    model_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    replay_forecasts_path.parent.mkdir(parents=True, exist_ok=True)
    outcomes_path = replay_forecasts_path.with_name(replay_forecasts_path.stem + "_actuals_for_scoring.csv")
    selected_forecasts.to_csv(replay_forecasts_path, index=False)
    outcomes.to_csv(outcomes_path, index=False)

    reference_match = (
        source_sha256 == expected_reference_sha256 if expected_reference_sha256 else None
    )
    baseline_route_day_median, baseline_global_median = _route_day_fallbacks(demand_fit["refit_rows"])
    bundle = {
        "pipeline": selected_pipeline,
        "features": selected_features,
        "serving_method": selected_method,
        "configuration": selected_configuration,
        "model_name": selected_estimator,
        "model_requires_schedule": requires_schedule,
        "baseline_route_day_median": baseline_route_day_median,
        "baseline_global_median": baseline_global_median,
        "target": "measured daily CTA route rides",
        "target_units": "rides per route per day",
        "reporting_delay_days": reporting_delay_days,
        "calendar_assumption": "CTA daytype is known at forecast issue time; validate the calendar source before operational use.",
        "missing_history_policy": "seasonal mean when >=2 same-weekday lags, then lag 7, then training route/daytype median, then global training median",
        "prediction_clip_minimum": 0,
        "training_cutoff": "2026-05-31",
        "data_sha256": source_sha256,
        "service_table_sha256": hashlib.sha256(service_path.read_bytes()).hexdigest(),
        "artifact_version": "3.0.0",
    }
    joblib.dump(bundle, model_path)

    demand_test_rows = int(features["date"].between("2026-05-01", "2026-07-31").sum())
    matched_test_rows = int(len(demand_fit["test_rows"]))
    service_demand_denominator = int(matched["date"].between("2026-06-01", "2026-07-31").sum())
    report = {
        "project_guide": "RouteRanker Intern Guide v3.0, 2026-11-10",
        "task": "daily CTA route rides forecasting; pooled regression with seasonal baselines",
        "target": "rides, the source's measured daily route boardings",
        "target_units": "rides per route per day",
        "source": {
            "ridership_sha256": source_sha256,
            "mentor_reference_sha256": expected_reference_sha256,
            "matches_mentor_reference": reference_match,
            "ridership_date_range_used": [
                str(features["date"].min().date()), str(features["date"].max().date())
            ],
            "service_table_sha256": bundle["service_table_sha256"],
        },
        "information_policy": {
            "reporting_delay_days": reporting_delay_days,
            "assumption": f"At issue date D, ride observations through D-{reporting_delay_days} may be used.",
            "publication_timing_verified": False,
            "schedule_snapshot_policy": "Use a whole-network GTFS snapshot captured strictly before the target/issue date for daily replay.",
            "same_day_capture_dates_are_excluded": True,
            "daytype": bundle["calendar_assumption"],
        },
        "model_selection": {
            "selected_on": "validation MAE only; no test-period model selection",
            "paired_matched_validation_winner": selected_method,
            "selected_validation_metrics": paired_validation[selected_method],
            "serving_configuration": selected_configuration,
            "serving_estimator": selected_estimator,
            "serving_model_requires_schedule": requires_schedule,
        },
        "demand_only_reference_experiment": _jsonable_configuration(demand_reference),
        "paired_matched_experiment": {
            "purpose": "Estimate the added value of schedule features on identical route/date partitions and rows.",
            "coverage": {
                "demand_test_rows": int(features["date"].between("2026-06-01", "2026-07-31").sum()),
                "matched_test_rows": matched_test_rows,
                "matched_test_coverage_pct": float(
                    100 * matched_test_rows / features["date"].between("2026-06-01", "2026-07-31").sum()
                ) if features["date"].between("2026-06-01", "2026-07-31").sum() else None,
            },
            "validation_metrics_by_configuration": {
                "demand_only": demand_fit["validation_metrics"],
                "service_aware": service_fit["validation_metrics"],
            },
            "test_metrics_by_configuration": {
                "demand_only": demand_fit["test_metrics_by_method"],
                "service_aware": service_fit["test_metrics_by_method"],
            },
            "validation_metrics_common_methods": paired_validation,
            "test_metrics_common_methods": paired_test,
            "selected_test_diagnostics": {
                "route": selected_route_metrics,
                "daytype": selected_daytype_metrics,
            },
            "demand_only": _jsonable_configuration(demand_fit),
            "service_aware": _jsonable_configuration(service_fit),
            "service_schedule_rows_matched": service_demand_denominator,
        },
        "replay_export": {
            "forecasts_csv": str(replay_forecasts_path),
            "actuals_for_offline_scoring_csv": str(outcomes_path),
            "forecast_rows": int(len(selected_forecasts)),
            "actuals_are_separate_from_forecasts": True,
            "forecast_export_contains_target_actuals": False,
        },
        "artifacts": {
            "model_bundle": str(model_path),
            "report": str(report_path),
        },
        "prior_test_history_note": (
            "The June-July dates were evaluated in previous project iterations. This v3-aligned run is development evidence, "
            "not an untouched final holdout; freeze later choices before a future-period evaluation."
        ),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ridership", default="data/raw/cta_bus_ridership.csv")
    parser.add_argument("--service-data", default="data/processed/cta_route_date_demand_service_v3.csv")
    parser.add_argument("--model", default="models/cta_ridership_v3.joblib")
    parser.add_argument("--report", default="outputs/reports/model_selection_v3.json")
    parser.add_argument("--replay-forecasts", default="outputs/predictions/cta_june_july_replay_v3.csv")
    parser.add_argument("--reporting-delay-days", type=int, default=1)
    args = parser.parse_args()
    result = run_v3_experiment(
        args.ridership, args.service_data, args.model, args.report,
        args.replay_forecasts, args.reporting_delay_days,
    )
    print(json.dumps({
        "selected": result["model_selection"],
        "demand_only_test": result["demand_only_reference_experiment"]["selected_test_metrics"],
        "paired_test": result["paired_matched_experiment"]["test_metrics_common_methods"],
        "source": result["source"],
    }, indent=2))


if __name__ == "__main__":
    main()
