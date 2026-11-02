"""Train a retrospective daily CTA route-ridership model with seasonal baselines."""

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
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .data_loader import load_bus_ridership
from .preprocessing import FEATURE_COLUMNS, make_route_features


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    actual = np.asarray(actual, dtype=float)
    predicted = np.maximum(np.asarray(predicted, dtype=float), 0)
    total = actual.sum()
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
        "wape": float(np.abs(actual - predicted).sum() / total) if total > 0 else None,
    }


def _seasonal_predictions(rows: pd.DataFrame, fallback: float) -> dict[str, np.ndarray]:
    """Last week's value and mean of available past same-weekday lags."""
    lag_7 = rows["lag_7"].fillna(rows["lag_1"]).fillna(fallback).to_numpy(dtype=float)
    seasonal_lags = rows[["lag_7", "lag_14", "lag_21", "lag_28"]]
    seasonal_mean = seasonal_lags.mean(axis=1).where(rows["seasonal_lag_count"] >= 2)
    seasonal_mean = seasonal_mean.fillna(rows["lag_7"]).fillna(rows["lag_1"]).fillna(fallback)
    return {"last_week_same_day": lag_7, "past_four_same_weekdays": seasonal_mean.to_numpy(dtype=float)}


def _fixed_origin_forecast(
    model: Pipeline,
    fit_rows: pd.DataFrame,
    observed: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Recursively forecast the test window using no observed test-period rides."""
    routes = sorted(fit_rows["route"].astype(str).unique())
    history = {
        (str(row.route), pd.Timestamp(row.date).normalize()): float(row.rides)
        for row in fit_rows[["route", "date", "rides"]].itertuples(index=False)
    }
    daytypes = observed.groupby("date")["daytype"].agg(lambda values: values.mode().iloc[0]).to_dict()
    predictions, last_week_baseline, seasonal_baseline = [], {}, {}
    fallback = float(fit_rows["rides"].median())
    for date in pd.date_range(start, end, freq="D"):
        daytype = daytypes.get(date, "U" if date.dayofweek == 6 else "A" if date.dayofweek == 5 else "W")
        rows = pd.DataFrame({"route": routes, "date": date, "daytype": daytype})
        rows["day_of_week"] = date.dayofweek
        rows["month"] = date.month
        rows["is_weekend"] = int(date.dayofweek >= 5)
        rows["is_sunday_holiday"] = int(daytype == "U")
        for days in (1, 7, 14, 21, 28):
            rows[f"lag_{days}"] = [
                history.get((route, date - pd.Timedelta(days=days))) for route in routes
            ]
        seasonal = rows[["lag_7", "lag_14", "lag_21", "lag_28"]]
        rows["seasonal_lag_count"] = seasonal.notna().sum(axis=1)
        rows["seasonal_lag_mean"] = seasonal.mean(axis=1).where(rows["seasonal_lag_count"] >= 2)
        model_values = np.maximum(model.predict(rows[FEATURE_COLUMNS]), 0)
        for i, route in enumerate(routes):
            predicted = float(model_values[i])
            key = (route, date)
            predictions.append({"route": route, "date": date, "predicted": predicted})
            history[key] = predicted
            l7 = rows.iloc[i]["lag_7"]
            l1 = rows.iloc[i]["lag_1"]
            last_week_baseline[key] = float(l7 if pd.notna(l7) else l1 if pd.notna(l1) else fallback)
            past = rows.iloc[i][["lag_7", "lag_14", "lag_21", "lag_28"]].dropna()
            seasonal_baseline[key] = float(past.mean() if len(past) >= 2 else l7 if pd.notna(l7) else l1 if pd.notna(l1) else fallback)
    forecast = pd.DataFrame(predictions)
    truth = observed.loc[observed["date"].between(start, end), ["route", "date", "rides", "daytype"]].copy()
    truth["route"] = truth["route"].astype(str)
    scored = truth.merge(forecast, on=["route", "date"], how="inner", validate="one_to_one")
    scored["last_week_same_day"] = [
        last_week_baseline[(route, date)] for route, date in zip(scored["route"], scored["date"])
    ]
    scored["past_four_same_weekdays"] = [
        seasonal_baseline[(route, date)] for route, date in zip(scored["route"], scored["date"])
    ]
    return forecast, scored


def train(
    input_path: str | Path,
    model_path: str | Path,
    report_path: str | Path,
    train_end: str = "2026-01-31",
    validation_start: str = "2026-02-01",
    validation_end: str = "2026-04-30",
    test_start: str = "2026-05-01",
    test_end: str = "2026-07-31",
    history_start: str = "2024-08-01",
) -> dict:
    """Tune on validation dates, refit the chosen estimator, then score test once."""
    raw = load_bus_ridership(input_path)
    featured = make_route_features(raw)
    start, tr_end = pd.Timestamp(history_start), pd.Timestamp(train_end)
    va_start, va_end = pd.Timestamp(validation_start), pd.Timestamp(validation_end)
    te_start, te_end = pd.Timestamp(test_start), pd.Timestamp(test_end)
    if not (start <= tr_end < va_start <= va_end < te_start <= te_end):
        raise ValueError("Date windows must be ordered: history/train, validation, then test")
    featured = featured[featured["date"].between(start, te_end)].copy()
    train_rows = featured[featured["date"].between(start, tr_end)]
    val_rows = featured[featured["date"].between(va_start, va_end)]
    test_rows = featured[featured["date"].between(te_start, te_end)]
    if any(part.empty for part in (train_rows, val_rows, test_rows)):
        raise ValueError("One or more configured date partitions are empty; check source dates and CLI split dates")

    categorical = ["route", "daytype"]
    numeric = [column for column in FEATURE_COLUMNS if column not in categorical]
    prep = ColumnTransformer([
        ("categories", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical),
        ("numeric", SimpleImputer(strategy="median", add_indicator=True), numeric),
    ])
    candidates = {
        "pooled_ridge": Ridge(alpha=1.0),
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            max_iter=150, learning_rate=0.08, l2_regularization=1.0, random_state=42
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=250, min_samples_leaf=3, max_features=0.9,
            n_jobs=-1, random_state=42
        ),
    }
    scores_validation = {}
    best_name, best_mae = None, float("inf")
    y_train, y_val = train_rows["rides"].to_numpy(), val_rows["rides"].to_numpy()
    for name, estimator in candidates.items():
        candidate = Pipeline([("features", prep), ("model", estimator)])
        candidate.fit(train_rows[FEATURE_COLUMNS], y_train)
        pred = np.maximum(candidate.predict(val_rows[FEATURE_COLUMNS]), 0)
        scores_validation[name] = _metrics(y_val, pred)
        if scores_validation[name]["mae"] < best_mae:
            best_name, best_mae = name, scores_validation[name]["mae"]

    # Refit on training plus validation, before scoring the untouched test dates.
    fit_rows = featured[featured["date"].between(start, va_end)]
    selected = Pipeline([("features", prep), ("model", candidates[best_name])])
    selected.fit(fit_rows[FEATURE_COLUMNS], fit_rows["rides"])
    y_test = test_rows["rides"].to_numpy()
    predictions = np.maximum(selected.predict(test_rows[FEATURE_COLUMNS]), 0)
    route_results = pd.DataFrame({
        "route": test_rows["route"].to_numpy(),
        "actual": y_test,
        "predicted": predictions,
    })
    route_mae = {
        str(route): float(mean_absolute_error(group["actual"], group["predicted"]))
        for route, group in route_results.groupby("route")
    }
    detailed_results = route_results.assign(
        daytype=test_rows["daytype"].to_numpy(),
        demand_band=pd.qcut(test_rows["rides"], q=4, duplicates="drop").astype(str).to_numpy(),
    )
    daytype_metrics = {
        str(daytype): _metrics(group["actual"], group["predicted"])
        for daytype, group in detailed_results.groupby("daytype")
    }
    demand_band_metrics = {
        str(band): _metrics(group["actual"], group["predicted"])
        for band, group in detailed_results.groupby("demand_band")
    }
    fallback = float(fit_rows["rides"].median())
    baseline_predictions = _seasonal_predictions(test_rows, fallback)
    baseline_metrics = {name: _metrics(y_test, pred) for name, pred in baseline_predictions.items()}
    _, fixed_origin = _fixed_origin_forecast(selected, fit_rows, raw, te_start, te_end)
    fixed_origin_metrics = {
        "selected_model": _metrics(fixed_origin["rides"], fixed_origin["predicted"]),
        "seasonal_baselines": {
            "last_week_same_day": _metrics(fixed_origin["rides"], fixed_origin["last_week_same_day"]),
            "past_four_same_weekdays": _metrics(fixed_origin["rides"], fixed_origin["past_four_same_weekdays"]),
        },
        "scored_rows": int(len(fixed_origin)),
        "test_observation_rows": int(raw["date"].between(te_start, te_end).sum()),
        "scored_coverage_pct": float(
            100 * len(fixed_origin) / raw["date"].between(te_start, te_end).sum()
        ) if raw["date"].between(te_start, te_end).sum() else None,
        "forecast_origin": str(va_end.date()),
        "daytype_assumption": "CTA daytype is treated as known calendar metadata; operational calendar source still needs confirmation",
    }

    input_path = Path(input_path)
    fingerprint = hashlib.sha256(input_path.read_bytes()).hexdigest()
    model_path, report_path = Path(model_path), Path(report_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "pipeline": selected,
        "features": FEATURE_COLUMNS,
        "model_name": best_name,
        "target": "measured daily route boardings (rides)",
        "training_range": [str(start.date()), str(va_end.date())],
        "source_sha256": fingerprint,
        "artifact_version": "0.2.0",
        "prediction_status": "retrospective experiment; CTA publication delay is unverified",
    }
    joblib.dump(metadata, model_path)
    report = {
        "task": "daily route ridership regression",
        "target": "rides",
        "evaluation_note": "Retrospective only: feature lags use observed route/date history; publication availability is unverified.",
        "source_sha256": fingerprint,
        "splits": {
            "train": {"start": str(start.date()), "end": str(tr_end.date()), "rows": int(len(train_rows))},
            "validation": {"start": str(va_start.date()), "end": str(va_end.date()), "rows": int(len(val_rows))},
            "test": {"start": str(te_start.date()), "end": str(te_end.date()), "rows": int(len(test_rows))},
        },
        "selected_model": best_name,
        "validation_model_metrics": scores_validation,
        "test_metrics": {"selected_model": _metrics(y_test, predictions), "seasonal_baselines": baseline_metrics},
        "test_evaluation_type": "rolling one-step retrospective; each test date can use preceding observed test-date rides",
        "fixed_origin_test_metrics": fixed_origin_metrics,
        "test_route_mae": {key: float(value) for key, value in route_mae.items()},
        "test_metrics_by_daytype": daytype_metrics,
        "test_metrics_by_demand_quartile": demand_band_metrics,
        "fallbacks": {
            "model_missing_values": "training-set median imputation with missing indicators",
            "baseline_missing_history": "lag_7, then lag_1, then training target median",
        },
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/raw/cta_bus_ridership.csv")
    parser.add_argument("--model", default="models/cta_ridership.joblib")
    parser.add_argument("--report", default="outputs/reports/model_metrics.json")
    parser.add_argument("--history-start", default="2024-08-01")
    parser.add_argument("--train-end", default="2026-01-31")
    parser.add_argument("--validation-start", default="2026-02-01")
    parser.add_argument("--validation-end", default="2026-04-30")
    parser.add_argument("--test-start", default="2026-05-01")
    parser.add_argument("--test-end", default="2026-07-31")
    args = parser.parse_args()
    print(json.dumps(train(args.input, args.model, args.report, args.train_end,
                           args.validation_start, args.validation_end, args.test_start,
                           args.test_end, args.history_start), indent=2))


if __name__ == "__main__":
    main()
