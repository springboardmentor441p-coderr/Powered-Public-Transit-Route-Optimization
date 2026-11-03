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
SEASONAL_LAGS = (7, 14, 21, 28)


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


def _fixed_origin_results(
    models: dict,
    fit_rows: pd.DataFrame,
    demand: pd.DataFrame,
    fixed_service: pd.DataFrame,
    origin: pd.Timestamp,
    test_start: pd.Timestamp,
    test_end: pd.Timestamp,
) -> dict:
    """Evaluate both models recursively with one schedule version and no test rides as lags."""
    required = {"route", "date", *SERVICE_FEATURES, "source_snapshot", "archive_available_from"}
    if not required.issubset(fixed_service.columns):
        raise ValueError(f"Fixed-origin service table must contain {sorted(required)}")
    fixed_service = fixed_service.copy()
    fixed_service["date"] = pd.to_datetime(fixed_service["date"], errors="coerce").dt.normalize()
    fixed_service = fixed_service.loc[
        fixed_service["scheduled_trips"].notna()
        & fixed_service["date"].between(test_start, test_end)
    ].copy()
    if fixed_service.empty:
        raise ValueError("Fixed-origin schedule table has no service rows for the test window")
    fixed_service["scheduled_trips"] = pd.to_numeric(fixed_service["scheduled_trips"], errors="coerce")
    fixed_service["scheduled_service_hours"] = pd.to_numeric(
        fixed_service["scheduled_service_hours"], errors="coerce"
    )
    if fixed_service.duplicated(["route", "date"]).any():
        raise ValueError("Fixed-origin schedule table contains duplicate route/date rows")
    snapshots = fixed_service["source_snapshot"].dropna().astype(str).unique().tolist()
    available_dates = pd.to_datetime(fixed_service["archive_available_from"], errors="coerce")
    if len(snapshots) != 1:
        raise ValueError(f"Expected exactly one frozen schedule snapshot; found {snapshots}")
    if available_dates.isna().any() or (available_dates > origin).any():
        raise ValueError("Fixed-origin schedule includes a snapshot unavailable at the forecast origin")

    observed = demand.loc[demand["date"].le(origin)].copy()
    date_daytype = demand.groupby("date")["daytype"].agg(lambda values: values.mode().iloc[0]).to_dict()
    history_by_model = {
        name: {
            (str(row.route), pd.Timestamp(row.date).normalize()): float(row.rides)
            for row in observed[["route", "date", "rides"]].itertuples(index=False)
        }
        for name in models
    }
    baseline_week_history = {
        (str(row.route), pd.Timestamp(row.date).normalize()): float(row.rides)
        for row in observed[["route", "date", "rides"]].itertuples(index=False)
    }
    baseline_mean_history = baseline_week_history.copy()
    fallback = float(fit_rows["rides"].median())
    model_outputs = {name: [] for name in models}
    baseline_week, baseline_mean = [], []
    for date in pd.date_range(test_start, test_end, freq="D"):
        schedule_day = fixed_service.loc[fixed_service["date"].eq(date)]
        if schedule_day.empty:
            continue
        default_daytype = "U" if date.dayofweek == 6 else "A" if date.dayofweek == 5 else "W"
        daytype = date_daytype.get(date, default_daytype)
        routes = schedule_day["route"].astype(str).tolist()
        future = pd.DataFrame({
            "route": routes,
            "date": date,
            "daytype": daytype,
            "scheduled_trips": schedule_day["scheduled_trips"].to_numpy(),
            "scheduled_service_hours": schedule_day["scheduled_service_hours"].to_numpy(),
        })
        future["day_of_week"] = date.dayofweek
        future["month"] = date.month
        future["is_weekend"] = int(date.dayofweek >= 5)
        future["is_sunday_holiday"] = int(daytype == "U")
        # Demand-history features differ after each model starts feeding back its predictions.
        rows_by_model = {}
        for name in models:
            rows = future.copy()
            for days in (1, 7, 14, 21, 28):
                rows[f"lag_{days}"] = [
                    history_by_model[name].get((route, date - pd.Timedelta(days=days)))
                    for route in routes
                ]
            seasonal = rows[[f"lag_{days}" for days in SEASONAL_LAGS]]
            rows["seasonal_lag_count"] = seasonal.notna().sum(axis=1)
            rows["seasonal_lag_mean"] = seasonal.mean(axis=1).where(rows["seasonal_lag_count"] >= 2)
            feature_columns = models[name]["features"]
            values = np.maximum(models[name]["pipeline"].predict(rows[feature_columns]), 0)
            rows["predicted"] = values
            rows_by_model[name] = rows
            model_outputs[name].extend(rows[["route", "date", "predicted"]].to_dict("records"))
        # Each baseline has its own recursive history, independent of observed test rides.
        for row in future.itertuples(index=False):
            route = str(row.route)
            key = (route, date)
            week_lag = baseline_week_history.get((route, date - pd.Timedelta(days=7)))
            one_lag = baseline_week_history.get((route, date - pd.Timedelta(days=1)))
            week_value = week_lag if week_lag is not None else one_lag if one_lag is not None else fallback
            baseline_week.append({"route": route, "date": date, "predicted": float(week_value)})
            baseline_week_history[key] = float(week_value)
            seasonal_values = [
                baseline_mean_history.get((route, date - pd.Timedelta(days=days)))
                for days in SEASONAL_LAGS
            ]
            available = [value for value in seasonal_values if value is not None]
            seasonal_value = (
                float(np.mean(available)) if len(available) >= 2
                else week_lag if week_lag is not None
                else one_lag if one_lag is not None
                else fallback
            )
            baseline_mean.append({"route": route, "date": date, "predicted": float(seasonal_value)})
            baseline_mean_history[key] = float(seasonal_value)
        for name, rows in rows_by_model.items():
            for row in rows[["route", "predicted"]].itertuples(index=False):
                history_by_model[name][(str(row.route), date)] = float(row.predicted)

    truth = demand.loc[demand["date"].between(test_start, test_end), ["route", "date", "rides", "daytype"]].copy()
    truth["route"] = truth["route"].astype(str)
    baseline_week_frame = pd.DataFrame(baseline_week).rename(columns={"predicted": "last_week_same_day"})
    baseline_mean_frame = pd.DataFrame(baseline_mean).rename(columns={"predicted": "past_four_same_weekdays"})
    forecast_frames = {
        name: truth.merge(pd.DataFrame(values), on=["route", "date"], how="inner", validate="one_to_one")
        for name, values in model_outputs.items()
    }
    scored_keys = set.intersection(*[
        set(zip(frame["route"], frame["date"])) for frame in forecast_frames.values()
    ])
    scored_frames = {}
    for name, frame in forecast_frames.items():
        frame = frame.loc[
            pd.MultiIndex.from_frame(frame[["route", "date"]]).isin(
                pd.MultiIndex.from_tuples(sorted(scored_keys))
            )
        ].copy()
        frame = frame.merge(baseline_week_frame, on=["route", "date"], validate="one_to_one")
        frame = frame.merge(baseline_mean_frame, on=["route", "date"], validate="one_to_one")
        scored_frames[name] = frame
    denominator = int(demand["date"].between(test_start, test_end).sum())
    metrics = {
        name: {
            "metrics": _score(frame["rides"], frame["predicted"].to_numpy()),
            "metrics_by_daytype": {
                str(daytype): _score(group["rides"], group["predicted"].to_numpy())
                for daytype, group in frame.groupby("daytype")
            },
            "scored_rows": int(len(frame)),
        }
        for name, frame in scored_frames.items()
    }
    common = next(iter(scored_frames.values()))
    return {
        "forecast_origin": origin.date().isoformat(),
        "forecast_window": [test_start.date().isoformat(), test_end.date().isoformat()],
        "schedule_snapshot": snapshots[0],
        "schedule_available_from": str(available_dates.min().date()),
        "test_observation_rows": denominator,
        "scored_rows": int(len(common)),
        "coverage_pct": float(100 * len(common) / denominator) if denominator else None,
        "models": metrics,
        "seasonal_baselines": {
            "last_week_same_day": _score(common["rides"], common["last_week_same_day"].to_numpy()),
            "past_four_same_weekdays": _score(common["rides"], common["past_four_same_weekdays"].to_numpy()),
        },
        "daytype_assumption": "CTA daytype is treated as known date/calendar metadata; confirm the operational calendar source",
    }


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
    fixed_origin_service_path: str | Path | None = None,
    fixed_origin: str = "2026-05-31",
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
    if fixed_origin_service_path is not None:
        fixed_origin_service = pd.read_csv(
            fixed_origin_service_path, dtype={"route": "string", "source_snapshot": "string"}
        )
        fit_rows = aligned.loc[aligned["date"].between(start, va_end)]
        report["fixed_origin_evaluation"] = _fixed_origin_results(
            artifacts, fit_rows, demand, fixed_origin_service,
            pd.Timestamp(fixed_origin), te_start, te_end,
        )
        report["source_sha256"]["fixed_origin_schedule_table"] = hashlib.sha256(
            Path(fixed_origin_service_path).read_bytes()
        ).hexdigest()
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ridership", default="data/raw/cta_bus_ridership.csv")
    parser.add_argument("--service-data", default="data/processed/cta_route_date_demand_service.csv")
    parser.add_argument("--report", default="outputs/reports/service_model_comparison.json")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--fixed-origin-service-data")
    parser.add_argument("--fixed-origin", default="2026-05-31")
    args = parser.parse_args()
    print(json.dumps(compare(
        args.ridership, args.service_data, args.report, args.model_dir,
        fixed_origin_service_path=args.fixed_origin_service_data,
        fixed_origin=args.fixed_origin,
    ), indent=2))


if __name__ == "__main__":
    main()
