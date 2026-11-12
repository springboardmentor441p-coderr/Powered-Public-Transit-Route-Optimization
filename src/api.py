"""HTTP API for saved CTA evaluation results and planning scenarios."""

import json
import os
import re
import time
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
import requests
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .data_loader import load_bus_ridership
from .predict_v3 import load_v3_bundle, predict_daily_routes_from_bundle
from .scenarios import optimize_trip_allocation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "frontend" / "dist"
REPORT_PATH = PROJECT_ROOT / "outputs" / "reports" / "service_model_comparison.json"
V3_REPORT_PATH = PROJECT_ROOT / "outputs" / "reports" / "model_selection_v3.json"
V3_BUNDLE_DEFAULT = PROJECT_ROOT / "models" / "cta_route_ranker_v3_results.zip"
RIDERSHIP_DEFAULT = PROJECT_ROOT / "data" / "raw" / "cta_bus_ridership.csv"
ROUTE_GEOJSON_URLS = (
    (
        "https://data.cityofchicago.org/api/v3/views/6uva-a5ei/query.geojson?accessType=DOWNLOAD",
        "City of Chicago Open Data",
        "https://data.cityofchicago.org/Transportation/CTA-Bus-Routes/6uva-a5ei",
    ),
    (
        "https://data.cityofchicago.org/resource/6uva-a5ei.geojson?$limit=5000",
        "City of Chicago Open Data",
        "https://data.cityofchicago.org/Transportation/CTA-Bus-Routes/6uva-a5ei",
    ),
    (
        "https://gis12.cookcountyil.gov/traditional/rest/services/publicTransit/MapServer/1/query?where=1%3D1&outFields=*&outSR=4326&f=geojson",
        "Cook County CTA route layer",
        "https://gis12.cookcountyil.gov/traditional/rest/services/publicTransit/MapServer/layers",
    ),
)
ROUTE_GEOJSON_BUNDLED = PROJECT_ROOT / "data" / "reference" / "cta_bus_routes.geojson"
BUS_VEHICLES_URL = "https://www.ctabustracker.com/bustime/api/v3/getvehicles"
REFERENCE = "past_four_same_weekdays"

_route_geojson_cache: tuple[float, dict] | None = None

app = FastAPI(
    title="CTA Route Review API",
    description=(
        "Route forecast evaluation, one-day forecasts from the v3 artifact, "
        "and bounded planning scenarios."
    ),
    version="2.0.0",
)
app.mount("/assets", StaticFiles(directory=WEB_ROOT / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    """Serve the browser dashboard; all data operations use this API."""
    return FileResponse(WEB_ROOT / "index.html")


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


def _read_bus_tracker_key() -> str | None:
    return os.environ.get("CTA_BUS_TRACKER_API_KEY", "").strip() or None


@app.get("/api/v1/map/geometry", tags=["map"])
def map_geometry() -> dict:
    """Return official CTA route geometry, cached for one day."""
    configured_path = os.environ.get("CTA_ROUTE_GEOJSON_PATH")
    local_path = Path(configured_path).expanduser() if configured_path else None
    if local_path and local_path.is_file():
        try:
            payload = json.loads(local_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=503, detail="Local CTA route GeoJSON could not be read") from exc
        source_metadata = {"label": f"Local route file · {local_path.name}", "url": None}
    else:
        global _route_geojson_cache
        now = time.time()
        if _route_geojson_cache and now - _route_geojson_cache[0] < 86400:
            return _route_geojson_cache[1]
        payload = None
        source_metadata = None
        for url, label, source_url in ROUTE_GEOJSON_URLS:
            try:
                response = requests.get(url, timeout=(5, 20))
                response.raise_for_status()
                if len(response.content) > 100 * 1024 * 1024:
                    raise HTTPException(status_code=502, detail="CTA route geometry exceeds the 100 MB safety limit")
                candidate = response.json()
                if candidate.get("type") != "FeatureCollection" or not isinstance(candidate.get("features"), list):
                    continue
                payload = candidate
                source_metadata = {"label": label, "url": source_url}
                break
            except (requests.RequestException, ValueError):
                continue
        if payload is None:
            try:
                payload = json.loads(ROUTE_GEOJSON_BUNDLED.read_text())
                source_metadata = {
                    "label": "Cook County CTA route layer · bundled fallback",
                    "url": "https://gis12.cookcountyil.gov/traditional/rest/services/publicTransit/MapServer/layers",
                }
            except (OSError, json.JSONDecodeError) as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Route geometry is unavailable. Check the network or set CTA_ROUTE_GEOJSON_PATH.",
                ) from exc
        payload = {**payload, "source_metadata": source_metadata}
        _route_geojson_cache = (now, payload)
    if source_metadata and "source_metadata" not in payload:
        payload = {**payload, "source_metadata": source_metadata}
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise HTTPException(status_code=502, detail="CTA route geometry is not a GeoJSON FeatureCollection")
    return payload


@lru_cache(maxsize=2)
def _route_demand_summary(path: str, modified_ns: int, size: int) -> dict:
    del modified_ns, size
    frame = load_bus_ridership(path)
    latest = frame["date"].max()
    start = max(frame["date"].min(), latest - pd.Timedelta(days=83))
    recent = frame.loc[frame["date"].between(start, latest)]
    means = recent.groupby("route")["rides"].mean()
    totals = recent.groupby("route")["rides"].sum()
    return {
        "available": True,
        "source_latest_date": latest.date().isoformat(),
        "period_start": start.date().isoformat(),
        "period_end": latest.date().isoformat(),
        "route_count": int(frame["route"].nunique()),
        "mean_daily_boardings": {str(route): float(value) for route, value in means.items()},
        "period_boardings": {str(route): int(value) for route, value in totals.items()},
    }


@lru_cache(maxsize=2)
def _server_ridership_history(path: str, modified_ns: int, size: int) -> pd.DataFrame:
    del modified_ns, size
    return load_bus_ridership(path)


@app.get("/api/v1/map/demand", tags=["map"])
def map_demand() -> dict:
    """Return recent route-level demand for map coloring when the CSV is configured."""
    path = Path(os.environ.get("CTA_RIDERSHIP_CSV", RIDERSHIP_DEFAULT)).expanduser().resolve()
    if not path.is_file():
        return {"available": False, "detail": "Configure CTA_RIDERSHIP_CSV to enable demand coloring."}
    stat = path.stat()
    try:
        return _route_demand_summary(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=503, detail=f"Ridership data could not be loaded: {exc}") from exc


@app.get("/api/v1/map/vehicles", tags=["map"])
def map_vehicles(routes: list[str] = Query(default=[])) -> dict:
    """Return CTA Bus Tracker vehicle locations for up to ten requested routes."""
    key = _read_bus_tracker_key()
    if not key:
        raise HTTPException(status_code=503, detail="Live buses require CTA_BUS_TRACKER_API_KEY in server secrets.")
    routes = list(dict.fromkeys(route.strip() for route in routes if route.strip()))
    if not 1 <= len(routes) <= 10 or any(not re.fullmatch(r"[A-Za-z0-9-]{1,10}", route) for route in routes):
        raise HTTPException(status_code=422, detail="Provide one to ten valid CTA route codes.")
    try:
        response = requests.get(
            BUS_VEHICLES_URL,
            params={"key": key, "rt": ",".join(routes), "format": "json", "tmres": "s"},
            timeout=(5, 15),
        )
        response.raise_for_status()
        body = response.json().get("bustime-response", {})
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="CTA Bus Tracker could not be reached.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="CTA Bus Tracker returned invalid JSON.") from exc
    if body.get("error"):
        raise HTTPException(status_code=502, detail="CTA Bus Tracker rejected the key or route request.")
    vehicles = body.get("vehicle", [])
    if isinstance(vehicles, dict):
        vehicles = [vehicles]
    return {"timestamp": body.get("tmst"), "vehicles": vehicles}


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


@app.post("/api/v1/forecasts/predict-one", tags=["forecasts"])
def forecast_one_from_server(target: ForecastTarget) -> dict:
    """Make a one-route forecast from the server-configured trained model and CSV."""
    history_path = Path(os.environ.get("CTA_RIDERSHIP_CSV", RIDERSHIP_DEFAULT)).expanduser().resolve()
    if not history_path.is_file():
        raise HTTPException(
            status_code=503,
            detail="Ridership history is not configured. Set CTA_RIDERSHIP_CSV on the API server.",
        )
    bundle = _load_v3_bundle()
    try:
        stat = history_path.stat()
        history = _server_ridership_history(str(history_path), stat.st_mtime_ns, stat.st_size)
        targets = pd.DataFrame([target.model_dump() if hasattr(target, "model_dump") else target.dict()])
        prediction = predict_daily_routes_from_bundle(bundle, history, targets)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=422, detail=f"One-day forecast could not be generated: {exc}") from exc
    result = prediction.iloc[0].to_dict()
    for column, value in list(result.items()):
        if hasattr(value, "isoformat"):
            result[column] = value.isoformat()
    return {
        "model": bundle["serving_method"],
        "history_latest_date": history["date"].max().date().isoformat(),
        "prediction": result,
        "interpretation_limit": (
            "Predicted daily boardings are not passenger load, crowding, capacity, "
            "or a service-change recommendation."
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
