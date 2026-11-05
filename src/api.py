"""Read-only HTTP API for saved CTA route evaluation results."""

import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query

REPORT_PATH = Path(__file__).resolve().parents[1] / "outputs" / "reports" / "service_model_comparison.json"
REFERENCE = "past_four_same_weekdays"

app = FastAPI(
    title="CTA Route Review API",
    description=(
        "Read-only route and day-type forecast evaluation results. "
        "Endpoints return saved evaluation metrics, not live forecasts."
    ),
    version="1.0.0",
)


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
    return {"status": "ok" if REPORT_PATH.exists() else "report_missing"}


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
