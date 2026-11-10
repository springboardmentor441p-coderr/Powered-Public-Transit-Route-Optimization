"""HTTP API for saved CTA evaluation results and planning scenarios."""

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt

from .predict_v3 import load_v3_bundle, predict_daily_routes_from_bundle
from .scenarios import optimize_trip_allocation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "outputs" / "reports" / "service_model_comparison.json"
V3_REPORT_PATH = PROJECT_ROOT / "outputs" / "reports" / "model_selection_v3.json"
V3_BUNDLE_DEFAULT = PROJECT_ROOT / "models" / "cta_route_ranker_v3_results.zip"
REFERENCE = "past_four_same_weekdays"

app = FastAPI(
    title="CTA Route Review API",
    description=(
        "Route forecast evaluation, one-day forecasts from the v3 artifact, "
        "and bounded planning scenarios."
    ),
    version="2.0.0",
)


class ScenarioRoute(BaseModel):
    route: str = Field(min_length=1, max_length=20)
    predicted_rides: float = Field(ge=0)
    scheduled_trips: StrictInt = Field(ge=1)


class TripAllocationRequest(BaseModel):
    routes: list[ScenarioRoute] = Field(min_items=1, max_items=300)
    max_shift_pct: float = Field(
        default=0.10, ge=0, le=0.5,
        description="Maximum proportional change per route; 0.10 means 10 percent.",
    )


class ForecastObservation(BaseModel):
    route: str = Field(min_length=1, max_length=20)
    date: date
    daytype: Literal["W", "A", "U"]
    rides: float = Field(ge=0)


class ForecastTarget(BaseModel):
    route: str = Field(min_length=1, max_length=20)
    date: date
    daytype: Literal["W", "A", "U"]


class ForecastServiceRow(BaseModel):
    route: str = Field(min_length=1, max_length=20)
    date: date
    scheduled_trips: float = Field(gt=0)
    scheduled_service_hours: float | None = Field(default=None, ge=0)
    archive_available_from: date
    source_snapshot: str | None = None
    match_status: str | None = None


class OneDayForecastRequest(BaseModel):
    history: list[ForecastObservation] = Field(min_items=1, max_items=10000)
    targets: list[ForecastTarget] = Field(min_items=1, max_items=300)
    service_rows: list[ForecastServiceRow] | None = Field(default=None, max_items=300)


@lru_cache(maxsize=1)
def _cached_v3_bundle(path: str, modified_ns: int, size: int) -> dict:
    del modified_ns, size  # File metadata participates in the cache key.
    return load_v3_bundle(path)


def _v3_bundle_path() -> Path:
    configured = os.environ.get("CTA_RANKER_V3_BUNDLE")
    path = Path(configured).expanduser() if configured else V3_BUNDLE_DEFAULT
    return path.resolve()


def _load_v3_bundle() -> dict:
    path = _v3_bundle_path()
    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail=(
                f"v3 model bundle not found at {path}. Set CTA_RANKER_V3_BUNDLE to the "
                "Colab results ZIP or the extracted cta_ridership_v3.joblib file."
            ),
        )
    try:
        stat = path.stat()
        return _cached_v3_bundle(str(path), stat.st_mtime_ns, stat.st_size)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not load the configured v3 model bundle: {exc}") from exc


def _load_report() -> dict:
    if not REPORT_PATH.exists():
        raise HTTPException(status_code=503, detail="Evaluation report is not available")
    try:
        return json.loads(REPORT_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Evaluation report could not be read") from exc


def _mode_data(mode: Literal["fixed_origin", "daily_rolling"], report: dict) -> dict:
    if mode == "fixed_origin":
        try:
            fixed = report["fixed_origin_evaluation"]
            overall = {
                REFERENCE: fixed["seasonal_baselines"][REFERENCE],
                "last_week_same_day": fixed["seasonal_baselines"]["last_week_same_day"],
            }
            routes = {
                REFERENCE: fixed["seasonal_baselines_by_route"][REFERENCE],
                "last_week_same_day": fixed["seasonal_baselines_by_route"]["last_week_same_day"],
            }
            daytypes = {}
            for name in (REFERENCE, "last_week_same_day"):
                for daytype, metrics in fixed["seasonal_baselines_by_daytype"][name].items():
                    daytypes.setdefault(daytype, {})[name] = metrics
            for name, values in fixed["models"].items():
                overall[name] = values["metrics"]
                routes[name] = values["metrics_by_route"]
                for daytype, metrics in values["metrics_by_daytype"].items():
                    daytypes.setdefault(daytype, {})[name] = metrics
            description = {
                "forecast_origin": fixed["forecast_origin"],
                "forecast_window": fixed["forecast_window"],
                "schedule_snapshot": fixed["schedule_snapshot"],
                "schedule_available_from": fixed["schedule_available_from"],
                "scored_rows": fixed["scored_rows"],
                "demand_rows": fixed["test_observation_rows"],
                "coverage_pct": fixed["coverage_pct"],
                "assumption": "Recursive forecast; actual rides from the forecast window are not used as future lags.",
            }
        except KeyError as exc:
            raise HTTPException(status_code=503, detail=f"Fixed-origin report section is incomplete: {exc}") from exc
    else:
        try:
            rolling = report["hybrid_walk_forward_development"]
            overall = rolling["overall_metrics"]
            routes = rolling["metrics_by_route"]
            daytypes = rolling["metrics_by_daytype"]
            description = {
                "fold_count": len(rolling["folds"]),
                "forecast_windows": [fold["forecast_window"] for fold in rolling["folds"]],
                "scored_rows": rolling["matched_rows"],
                "demand_rows": rolling["demand_rows"],
                "coverage_pct": rolling["matched_coverage_pct"],
                "assumption": "Daily rolling one-step development scores with observed earlier rides as lag features.",
            }
        except KeyError as exc:
            raise HTTPException(status_code=503, detail=f"Walk-forward report section is incomplete: {exc}") from exc
    return {
        "mode": mode,
        "description": description,
        "overall_metrics": overall,
        "route_metrics": routes,
        "daytype_metrics": daytypes,
    }


@app.get("/health", tags=["status"])
def health() -> dict:
    """Report whether the API can find its evaluation report."""
    return {
        "status": "ok" if REPORT_PATH.exists() else "report_missing",
        "v3_bundle_available": _v3_bundle_path().is_file(),
    }


@app.get("/api/v1/forecasts/model", tags=["forecasts"])
def forecast_model() -> dict:
    """Describe the validation-selected v3 model and its evaluation caveats."""
    if not V3_REPORT_PATH.exists():
        raise HTTPException(status_code=503, detail="v3 model-selection report is not available")
    try:
        report = json.loads(V3_REPORT_PATH.read_text())
        return {
            "model_selection": report["model_selection"],
            "paired_validation": report["paired_matched_experiment"]["validation_metrics_common_methods"],
            "paired_test": report["paired_matched_experiment"]["test_metrics_common_methods"],
            "source": report["source"],
            "artifact_training": report.get("artifacts", {}).get("final_refit"),
            "information_policy": report["information_policy"],
            "prior_test_history_note": report["prior_test_history_note"],
            "model_artifact_configured": _v3_bundle_path().is_file(),
        }
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise HTTPException(status_code=503, detail=f"v3 model-selection report is incomplete: {exc}") from exc


@app.post("/api/v1/forecasts/one-day", tags=["forecasts"])
def forecast_one_day(request: OneDayForecastRequest) -> dict:
    """Predict one target date from eligible prior rides and optional service."""
    bundle = _load_v3_bundle()
    history = pd.DataFrame([row.model_dump() if hasattr(row, "model_dump") else row.dict()
                            for row in request.history])
    targets = pd.DataFrame([row.model_dump() if hasattr(row, "model_dump") else row.dict()
                            for row in request.targets])
    service = None
    if request.service_rows is not None:
        service = pd.DataFrame([
            row.model_dump() if hasattr(row, "model_dump") else row.dict()
            for row in request.service_rows
        ])
    try:
        predictions = predict_daily_routes_from_bundle(bundle, history, targets, service)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    rows = predictions.to_dict(orient="records")
    for row in rows:
        for column in (
            "date", "forecast_issue_date", "latest_permitted_ridership_date",
            "archive_available_from",
        ):
            value = row.get(column)
            if hasattr(value, "isoformat"):
                row[column] = value.isoformat()
    return {
        "model": {
            "serving_method": bundle["serving_method"],
            "configuration": bundle["configuration"],
            "model_name": bundle["model_name"],
            "reporting_delay_days": bundle["reporting_delay_days"],
            "training_cutoff": bundle.get("training_cutoff"),
            "training_rows": bundle.get("training_rows"),
        },
        "prediction_mode": "daily rolling one-step forecast",
        "predictions": rows,
        "interpretation_limit": (
            "Predicted daily route boardings are a demand forecast; they are not passenger load, "
            "crowding, capacity, or a service-change recommendation."
        ),
    }


@app.get("/api/v1/evaluations", tags=["evaluations"])
def evaluations() -> dict:
    """List available evaluation horizons and candidate methods."""
    report = _load_report()
    modes = []
    for mode in ("fixed_origin", "daily_rolling"):
        data = _mode_data(mode, report)
        modes.append({
            "mode": mode,
            "description": data["description"],
            "methods": list(data["overall_metrics"]),
            "reference_method": REFERENCE,
        })
    return {"evaluations": modes}


@app.get("/api/v1/summary", tags=["evaluations"])
def summary(mode: Literal["fixed_origin", "daily_rolling"] = "fixed_origin") -> dict:
    """Return aggregate scores for every available method in one evaluation."""
    return _mode_data(mode, _load_report())


@app.get("/api/v1/daytypes", tags=["evaluations"])
def daytypes(mode: Literal["fixed_origin", "daily_rolling"] = "fixed_origin") -> dict:
    """Return aggregate error metrics grouped by CTA day type."""
    data = _mode_data(mode, _load_report())
    return {"mode": mode, "daytype_metrics": data["daytype_metrics"]}


@app.get("/api/v1/routes", tags=["routes"])
def routes(
    mode: Literal["fixed_origin", "daily_rolling"] = "fixed_origin",
    model: str = "service_aware",
    sort_by: Literal["largest_loss", "largest_gain", "route"] = "largest_loss",
    limit: int = Query(default=125, ge=1, le=250),
) -> dict:
    """Compare a method with the past-four-weekdays baseline for each route."""
    data = _mode_data(mode, _load_report())
    if model not in data["route_metrics"]:
        raise HTTPException(status_code=404, detail=f"Unknown method for {mode}: {model}")
    result = []
    for route, metrics_by_method in data["route_metrics"].items():
        forecast = metrics_by_method.get(model)
        baseline = metrics_by_method.get(REFERENCE)
        if forecast is None or baseline is None:
            continue
        delta = float(forecast["mae"] - baseline["mae"])
        result.append({
            "route": str(route),
            "method": model,
            "method_metrics": forecast,
            "reference_method": REFERENCE,
            "reference_metrics": baseline,
            "mae_difference": delta,
            "mae_difference_pct": (100 * delta / baseline["mae"]) if baseline["mae"] else None,
        })
    if sort_by == "largest_loss":
        result.sort(key=lambda row: row["mae_difference"], reverse=True)
    elif sort_by == "largest_gain":
        result.sort(key=lambda row: row["mae_difference"])
    else:
        result.sort(key=lambda row: (not row["route"].isdigit(), int(row["route"]) if row["route"].isdigit() else row["route"]))
    return {"mode": mode, "count": len(result), "routes": result[:limit]}


@app.get("/api/v1/routes/{route}", tags=["routes"])
def route_detail(
    route: str,
    mode: Literal["fixed_origin", "daily_rolling"] = "fixed_origin",
) -> dict:
    """Return all available method scores for one route."""
    data = _mode_data(mode, _load_report())
    route_metrics = data["route_metrics"].get(route)
    if route_metrics is None:
        raise HTTPException(status_code=404, detail=f"Route not found for {mode}: {route}")
    comparison = {}
    baseline = route_metrics.get(REFERENCE)
    for method, metrics in route_metrics.items():
        comparison[method] = {
            **metrics,
            "mae_difference_vs_reference": (
                float(metrics["mae"] - baseline["mae"]) if baseline else None
            ),
        }
    return {"mode": mode, "route": route, "reference_method": REFERENCE, "methods": comparison}


@app.post("/api/v1/scenarios/rebalance-trips", tags=["scenarios"])
def rebalance_trips(request: TripAllocationRequest) -> dict:
    """Optimize a bounded, trip-neutral allocation scenario from route forecasts."""
    route_rows = [
        row.model_dump() if hasattr(row, "model_dump") else row.dict()
        for row in request.routes
    ]
    try:
        return optimize_trip_allocation(
            pd.DataFrame(route_rows), max_shift_pct=request.max_shift_pct
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
