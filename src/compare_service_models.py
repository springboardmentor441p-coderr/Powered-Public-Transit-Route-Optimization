"""Compare demand-only and schedule-aware models on identical matched CTA rows."""

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .data_loader import load_bus_ridership
from .preprocessing import FEATURE_COLUMNS, make_route_features

SERVICE_FEATURES = ["scheduled_trips", "scheduled_service_hours"]


def _score(actual: pd.Series, predicted: np.ndarray) -> dict:
    actual_values = actual.to_numpy(dtype=float)
    predicted = np.maximum(np.asarray(predicted, dtype=float), 0)
    total = actual_values.sum()
    return {
        "mae": float(mean_absolute_error(actual_values, predicted)),
        "rmse": float(mean_squared_error(actual_values, predicted) ** 0.5),
        "wape": float(np.abs(actual_values - predicted).sum() / total) if total > 0 else None,
    }


def _pipeline(features: list[str]) -> Pipeline:
    categorical = ["route", "daytype"]
    numeric = [column for column in features if column not in categorical]
    transform = ColumnTransformer([
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical),
        ("numeric", SimpleImputer(strategy="median", add_indicator=True), numeric),
    ])
    return Pipeline([
        ("features", transform),
        ("model", HistGradientBoostingRegressor(
            max_iter=150, learning_rate=0.08, l2_regularization=1.0, random_state=42
        )),
    ])


def compare(
    ridership_path: str | Path,
    service_path: str | Path,
    report_path: str | Path,
    model_dir: str | Path,
    train_start: str = "2025-11-23",
    train_end: str = "2026-03-31",
    validation_start: str = "2026-04-01",
    validation_end: str = "2026-05-31",
    test_start: str = "2026-06-01",
    test_end: str = "2026-07-31",
) -> dict:
    """Fit both feature sets on the same matched route/date partitions."""
    demand = load_bus_ridership(ridership_path)
    featured = make_route_features(demand)
    service = pd.read_csv(service_path, dtype={"route": "string", "source_snapshot": "string"})
    required = {"route", "date", "scheduled_trips", "scheduled_service_hours", "match_status"}
    if not required.issubset(service.columns):
        raise ValueError(f"Service table must contain {sorted(required)}")
    service["date"] = pd.to_datetime(service["date"], errors="coerce").dt.normalize()
    service = service.loc[service["match_status"].eq("matched")].copy()
    if service.duplicated(["route", "date"]).any():
        raise ValueError("Matched service table has duplicate route/date rows")
    service["scheduled_trips"] = pd.to_numeric(service["scheduled_trips"], errors="coerce")
    service["scheduled_service_hours"] = pd.to_numeric(service["scheduled_service_hours"], errors="coerce")
    aligned = featured.merge(
        service[["route", "date", *SERVICE_FEATURES, "source_snapshot", "archive_available_from"]],
        on=["route", "date"], how="inner", validate="one_to_one",
    )
    if aligned.empty:
        raise ValueError("No exact route/date demand-service matches were found")

    start, tr_end = pd.Timestamp(train_start), pd.Timestamp(train_end)
    va_start, va_end = pd.Timestamp(validation_start), pd.Timestamp(validation_end)
    te_start, te_end = pd.Timestamp(test_start), pd.Timestamp(test_end)
    if not (start <= tr_end < va_start <= va_end < te_start <= te_end):
        raise ValueError("Train, validation, and test dates must be ordered without overlap")
    aligned = aligned.loc[aligned["date"].between(start, te_end)].copy()
    train = aligned.loc[aligned["date"].between(start, tr_end)]
    validation = aligned.loc[aligned["date"].between(va_start, va_end)]
    test = aligned.loc[aligned["date"].between(te_start, te_end)]
    if any(part.empty for part in (train, validation, test)):
        raise ValueError("A matched train/validation/test partition is empty; inspect archive coverage")
    fallback = float(train["rides"].median())
    seasonal_week = test["lag_7"].fillna(test["lag_1"]).fillna(fallback).to_numpy(dtype=float)
    same_weekday = test[["lag_7", "lag_14", "lag_21", "lag_28"]]
    seasonal_mean = same_weekday.mean(axis=1).where(test["seasonal_lag_count"] >= 2)
    seasonal_mean = seasonal_mean.fillna(test["lag_7"]).fillna(test["lag_1"]).fillna(fallback).to_numpy(dtype=float)

    results, artifacts = {}, {}
    for name, feature_columns in (
        ("demand_only", FEATURE_COLUMNS),
        ("service_aware", [*FEATURE_COLUMNS, *SERVICE_FEATURES]),
    ):
        model = _pipeline(feature_columns)
        model.fit(train[feature_columns], train["rides"])
        validation_pred = np.maximum(model.predict(validation[feature_columns]), 0)
        # Both alternatives use the same validation and test observations.
        fitted = _pipeline(feature_columns)
        fit_rows = aligned.loc[aligned["date"].between(start, va_end)]
        fitted.fit(fit_rows[feature_columns], fit_rows["rides"])
        test_pred = np.maximum(fitted.predict(test[feature_columns]), 0)
        row_metrics = _score(test["rides"], test_pred)
        route_errors = pd.DataFrame({
            "route": test["route"].astype(str).to_numpy(),
            "actual": test["rides"].to_numpy(),
            "predicted": test_pred,
        })
        results[name] = {
            "validation_metrics": _score(validation["rides"], validation_pred),
            "test_metrics": row_metrics,
            "test_metrics_by_daytype": {
                str(daytype): _score(group["rides"], group["predicted"].to_numpy())
                for daytype, group in pd.DataFrame({
                    "daytype": test["daytype"].to_numpy(),
                    "rides": test["rides"].to_numpy(),
                    "predicted": test_pred,
                }).groupby("daytype")
            },
            "test_route_mae": {
                str(route): float(mean_absolute_error(group["actual"], group["predicted"]))
                for route, group in route_errors.groupby("route")
            },
        }
        artifacts[name] = {"pipeline": fitted, "features": feature_columns, "model_name": name}

    report_path, model_dir = Path(report_path), Path(model_dir)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    for name, artifact in artifacts.items():
        joblib.dump(artifact, model_dir / f"cta_{name}.joblib")

    test_demand_rows = int(demand["date"].between(te_start, te_end).sum())
    report = {
        "task": "matched-date demand-only versus schedule-aware ridership regression",
        "evaluation_type": "retrospective rolling one-step; prior observed rides can include earlier test dates",
        "target": "measured daily route boardings (rides)",
        "source_sha256": {
            "ridership": hashlib.sha256(Path(ridership_path).read_bytes()).hexdigest(),
            "demand_service_table": hashlib.sha256(Path(service_path).read_bytes()).hexdigest(),
        },
        "partitions": {
            "train": {"start": train_start, "end": train_end, "matched_rows": int(len(train))},
            "validation": {"start": validation_start, "end": validation_end, "matched_rows": int(len(validation))},
            "test": {"start": test_start, "end": test_end, "matched_rows": int(len(test))},
        },
        "matched_test_coverage_pct": float(100 * len(test) / test_demand_rows) if test_demand_rows else None,
        "matched_test_demand_rows": int(len(test)),
        "test_demand_rows": test_demand_rows,
        "seasonal_baselines_on_matched_test_rows": {
            "last_week_same_day": _score(test["rides"], seasonal_week),
            "past_four_same_weekdays": _score(test["rides"], seasonal_mean),
        },
        "service_feature_missingness": {
            column: int(test[column].isna().sum()) for column in SERVICE_FEATURES
        },
        "test_schedule_snapshots": sorted(test["source_snapshot"].dropna().astype(str).unique().tolist()),
        "test_schedule_availability_range": [
            str(pd.to_datetime(test["archive_available_from"]).min().date()),
            str(pd.to_datetime(test["archive_available_from"]).max().date()),
        ],
        "models": results,
        "interpretation": "The comparison measures association/predictive value on historically matched dates. It is not causal and does not establish an operational fixed-origin forecast.",
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ridership", default="data/raw/cta_bus_ridership.csv")
    parser.add_argument("--service-data", default="data/processed/cta_route_date_demand_service.csv")
    parser.add_argument("--report", default="outputs/reports/service_model_comparison.json")
    parser.add_argument("--model-dir", default="models")
    args = parser.parse_args()
    print(json.dumps(compare(args.ridership, args.service_data, args.report, args.model_dir), indent=2))


if __name__ == "__main__":
    main()
