"""
backend/main.py
RouteRanker FastAPI REST Service

Production-ready backend API connecting to actual processed Parquet datasets,
machine learning evaluation metrics, and operational simulation engines.
"""

import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

# Add project root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from src.optimization.scenario_engine import simulate_frequency_adjustment

app = FastAPI(
    title="RouteRanker API",
    description="Operational Transit Demand Intelligence and Route Optimization REST API for Chicago Transit Authority (CTA) Bus Network",
    version="2.0.0"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROCESSED_DIR = WORKSPACE_ROOT / "data" / "processed"
REPORTS_DIR = WORKSPACE_ROOT / "reports"

# Cached in-memory datasets
DATA_CACHE: Dict[str, Any] = {}

def get_data():
    if not DATA_CACHE:
        try:
            DATA_CACHE["boardings"] = pd.read_parquet(PROCESSED_DIR / "boardings_clean.parquet")
            DATA_CACHE["boardings"]["date_str"] = DATA_CACHE["boardings"]["date"].dt.strftime("%Y-%m-%d")
            DATA_CACHE["rankings"] = pd.read_parquet(PROCESSED_DIR / "productivity_rankings.parquet")
            DATA_CACHE["structure"] = pd.read_parquet(PROCESSED_DIR / "route_structure.parquet")
            DATA_CACHE["overlap"] = pd.read_parquet(PROCESSED_DIR / "route_overlap.parquet")
            DATA_CACHE["preds"] = pd.read_parquet(PROCESSED_DIR / "model_predictions_test.parquet")
            DATA_CACHE["preds"]["date_str"] = DATA_CACHE["preds"]["date"].dt.strftime("%Y-%m-%d")

            with open(REPORTS_DIR / "model_metrics.json", "r") as f:
                DATA_CACHE["metrics"] = json.load(f)
            with open(REPORTS_DIR / "source_manifest.json", "r") as f:
                DATA_CACHE["manifest"] = json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load processed data: {e}")
    return DATA_CACHE

# Pydantic Request Models
class ScenarioRequest(BaseModel):
    route_id: str = Field(..., description="Target bus route identifier, e.g. '8' or '79'")
    percent_trip_change: float = Field(..., ge=-50.0, le=100.0, description="Percentage adjustment to scheduled trips (-50% to +100%)")
    elasticity: Optional[float] = Field(0.42, ge=0.1, le=1.0, description="Transit service frequency elasticity (default: 0.42)")
    cost_per_trip: Optional[float] = Field(85.0, ge=0.0, description="Estimated operating cost per bus revenue trip in USD")

# ========================================================
# ENDPOINTS
# ========================================================

@app.get("/api/health", tags=["System"])
def get_health():
    """Health check endpoint validating service status and dataset availability."""
    data = get_data()
    is_ready = bool(data and "boardings" in data)
    return {
        "status": "healthy" if is_ready else "degraded",
        "service": "RouteRanker Transit Intelligence API",
        "version": "2.0.0",
        "datasets_loaded": is_ready
    }

@app.get("/api/data/coverage", tags=["System"])
def get_coverage():
    """Returns dataset temporal boundaries, row counts, and GTFS coverage."""
    data = get_data()
    if "boardings" not in data:
        raise HTTPException(status_code=500, detail="Data cache not initialized.")

    df_b = data["boardings"]
    return {
        "total_historical_records": len(df_b),
        "unique_historical_routes": df_b["route"].nunique(),
        "date_min": df_b["date_str"].min(),
        "date_max": df_b["date_str"].max(),
        "gtfs_snapshot": "Fall 2026 Schedule Snapshot",
        "gtfs_bus_routes_count": len(data["rankings"]),
        "temporal_gap_days": 42,
        "license": "Chicago Transit Authority Developer License Agreement (Academic / Transit Optimization Permitted)"
    }

@app.get("/api/routes", tags=["Routes"])
def list_routes():
    """Lists all active bus routes with their scheduled metrics, archetypes, and review priority."""
    data = get_data()
    df_r = data["rankings"]
    records = df_r.to_dict(orient="records")
    return {
        "count": len(records),
        "routes": records
    }

@app.get("/api/routes/{route}/history", tags=["Routes"])
def get_route_history(
    route: str,
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    limit: Optional[int] = Query(365, ge=1, le=2000, description="Maximum number of historical days to return")
):
    """Retrieves historical ridership time-series for a specific bus route."""
    data = get_data()
    df_b = data["boardings"]
    sub = df_b[df_b["route"] == route]

    if sub.empty:
        raise HTTPException(status_code=404, detail=f"Route '{route}' not found in ridership records.")

    if start_date:
        sub = sub[sub["date_str"] >= start_date]
    if end_date:
        sub = sub[sub["date_str"] <= end_date]

    sub = sub.sort_values("date", ascending=False).head(limit)
    records = sub[["route", "date_str", "daytype", "rides"]].to_dict(orient="records")

    return {
        "route": route,
        "count": len(records),
        "history": list(reversed(records))
    }

@app.get("/api/rankings", tags=["Analytics"])
def get_rankings(
    tier: Optional[str] = Query(None, description="Filter by tier keyword (e.g. 'Tier 1', 'Tier 2', 'Tier 3')"),
    archetype: Optional[str] = Query(None, description="Filter by route archetype keyword")
):
    """Retrieves route productivity rankings, boardings-per-trip metrics, and review priorities."""
    data = get_data()
    df_r = data["rankings"].copy()

    if tier:
        df_r = df_r[df_r["review_priority"].str.contains(tier, case=False, na=False)]
    if archetype:
        df_r = df_r[df_r["archetype"].str.contains(archetype, case=False, na=False)]

    return {
        "count": len(df_r),
        "rankings": df_r.to_dict(orient="records")
    }

@app.get("/api/forecasts", tags=["Machine Learning"])
def get_forecasts(
    route: Optional[str] = Query(None, description="Bus route identifier (e.g. '79')"),
    limit: Optional[int] = Query(250, ge=1, le=1000)
):
    """Retrieves out-of-sample machine learning forecasts (XGBoost, Random Forest, Ridge, Baseline) for the 2026 test partition."""
    data = get_data()
    df_p = data["preds"]

    if route:
        sub = df_p[df_p["route"] == route].copy()
        if sub.empty:
            raise HTTPException(status_code=404, detail=f"No forecast predictions available for Route '{route}'.")
    else:
        sub = df_p.copy()

    sub = sub.sort_values("date").head(limit)
    return {
        "count": len(sub),
        "route_filter": route,
        "metrics_summary": data["metrics"]["models"],
        "predictions": sub.to_dict(orient="records")
    }

@app.post("/api/scenarios", tags=["Optimization"])
def run_scenario(payload: ScenarioRequest):
    """
    Simulates the ridership, trip frequency, and operational cost impact of a service adjustment.
    """
    data = get_data()
    df_r = data["rankings"]
    match = df_r[df_r["route_id"] == payload.route_id]

    if match.empty:
        raise HTTPException(status_code=404, detail=f"Route '{payload.route_id}' not found in active route registry.")

    route_info = match.iloc[0]
    result = simulate_frequency_adjustment(
        route_id=payload.route_id,
        base_weekday_rides=float(route_info["mean_weekday_rides"]),
        base_scheduled_trips=int(route_info["weekday_scheduled_trips"]),
        percent_trip_change=payload.percent_trip_change,
        elasticity=payload.elasticity or 0.42,
        cost_per_trip=payload.cost_per_trip or 85.0
    )
    return result

@app.get("/api/overlap", tags=["Analytics"])
def get_corridor_overlap(
    route: Optional[str] = Query(None, description="Target route to find all overlapping corridors for"),
    min_jaccard: Optional[float] = Query(0.1, ge=0.0, le=1.0)
):
    """Retrieves pairwise shared stops and Jaccard similarity metrics between routes."""
    data = get_data()
    df_ov = data["overlap"]

    if route:
        sub = df_ov[(df_ov["route_a"] == route) | (df_ov["route_b"] == route)]
    else:
        sub = df_ov

    sub = sub[sub["jaccard_similarity"] >= min_jaccard].sort_values("jaccard_similarity", ascending=False)
    return {
        "count": len(sub),
        "overlap_corridors": sub.head(50).to_dict(orient="records")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
