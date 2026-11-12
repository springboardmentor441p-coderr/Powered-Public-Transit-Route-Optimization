"""
RouteRanker: Analytics, Forecasting & Recommendations REST API
Exposes endpoints for:
- System and route demand forecasting
- Model benchmarks and evaluation metrics
- Smart frequency scenario simulations
- Transit network connectivity analysis
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
import os
import json
import numpy as np
import pandas as pd

from ml.forecasting.demand_forecast_service import demand_forecast_service
from ml.forecasting.crowd_classification_service import crowd_classification_service
from ml.clustering.route_clustering_service import route_clustering_service
from ml.ranking.route_ranking_service import route_ranking_service
from ml.replay.historical_replay_controller import historical_replay_controller
from backend.app.services.smart_recommendations import smart_recommendation_engine

router = APIRouter(prefix="/api", tags=["Analytics, Forecasting & Recommendations"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
PHASE4_DIR = os.path.join(PROCESSED_DIR, "phase4")
REPORTS_DIR = os.path.join(BASE_DIR, "outputs", "reports")
EVAL_DIR = os.path.join(BASE_DIR, "outputs", "evaluation")

@router.get("/forecast/system")
def get_system_forecast(horizon_days: int = Query(14, ge=1, le=30, description="Forecast horizon in days (1-30)")):
    """
    Returns system-wide daily passenger demand forecasts with 95% confidence intervals and day-type indicators.
    """
    fc = demand_forecast_service.get_system_forecast(horizon_days=horizon_days)
    if "error" in fc:
        raise HTTPException(status_code=500, detail=fc["error"])
        
    # Classify each forecast day
    for day in fc["forecast"]:
        class_info = crowd_classification_service.classify_system_demand(day["predicted_total_demand"])
        day["crowd_classification"] = class_info["classification"]
        day["badge_color"] = class_info["badge_color"]
        
    return fc

@router.get("/forecast/route")
def get_route_forecast(route_id: str = Query(..., description="CTA Bus Route ID (e.g. 79, 9, 66)"), horizon_days: int = Query(7, ge=1, le=28)):
    """
    Returns route-level daily demand forecast.
    """
    fc = demand_forecast_service.get_route_forecast(route_id=route_id, horizon_days=horizon_days)
    for day in fc["forecast"]:
        c_info = crowd_classification_service.classify_route_demand(route_id, day["predicted_rides"])
        day["crowd_classification"] = c_info["classification"]
        day["badge_color"] = c_info["badge_color"]
    return fc

@router.get("/forecast/metrics")
def get_model_evaluation_metrics():
    """
    Returns model training and evaluation metrics (MAE, RMSE, MAPE, R2) for all benchmarked algorithms.
    """
    return demand_forecast_service.get_model_benchmark_metrics()

@router.get("/recommendations/simulate")
def simulate_trip_frequency(route_id: str = Query(..., description="CTA Bus Route ID"), proposed_trips: int = Query(..., ge=10, le=400, description="Proposed daily scheduled trips")):
    """
    Simulates service frequency adjustments, headway impacts, passenger loading, and explainable recommendations.
    """
    return smart_recommendation_engine.simulate_frequency_scenario(route_id=route_id, proposed_trips=proposed_trips)

@router.get("/analytics/routes")
def get_route_performance_table(limit: int = Query(25, ge=5, le=130)):
    """
    Returns historical ridership performance ranking for CTA bus corridors.
    """
    bus_path = os.path.join(PHASE4_DIR, "cta_daily_bus_route_forecasting_ready.csv")
    if not os.path.exists(bus_path):
        raise HTTPException(status_code=404, detail="Route dataset not found")
        
    df = pd.read_csv(bus_path, low_memory=False)
    perf = df.groupby(["route_id", "route_long_name"]).agg(
        mean_daily_rides=("rides", "mean"),
        max_daily_rides=("rides", "max"),
        p90_daily_rides=("rides", lambda x: np.percentile(x, 90)),
        days_recorded=("rides", "count"),
        scheduled_trips=("scheduled_trips", "first")
    ).reset_index()
    
    perf["mean_daily_rides"] = perf["mean_daily_rides"].round().astype(int)
    perf["max_daily_rides"] = perf["max_daily_rides"].astype(int)
    perf["p90_daily_rides"] = perf["p90_daily_rides"].round().astype(int)
    perf["scheduled_trips"] = perf["scheduled_trips"].fillna(120).astype(int)
    
    # Classify each route
    perf["demand_tier"] = perf["mean_daily_rides"].map(
        lambda r: crowd_classification_service.classify_route_demand("any", r)["classification"]
    )
    
    perf = perf.sort_values(by="mean_daily_rides", ascending=False).head(limit)
    return {
        "count": len(perf),
        "routes": perf.to_dict(orient="records")
    }

@router.get("/analytics/network")
def get_network_connectivity():
    """
    Returns transit graph metrics, degree centrality, and key multi-modal transit hubs in Chicago.
    """
    conn_path = os.path.join(REPORTS_DIR, "network_connectivity_analysis.json")
    if os.path.exists(conn_path):
        with open(conn_path, "r") as f:
            return json.load(f)
    return {"message": "Network analysis not generated"}

@router.get("/analytics/historical-trend")
def get_historical_trend(days: int = Query(60, ge=7, le=365, description="Number of recent historical days to return")):
    """
    Returns recent daily ridership time-series (bus, rail, total) for trend charting.
    """
    sys_path = os.path.join(PHASE4_DIR, "cta_daily_system_forecasting_ready.csv")
    if not os.path.exists(sys_path):
        raise HTTPException(status_code=404, detail="System dataset not found")
    
    df = pd.read_csv(sys_path)
    df = df.tail(days)
    day_col = "day_type" if "day_type" in df.columns else ("daytype" if "daytype" in df.columns else "day_type_code")
    cols_to_keep = ["date", day_col, "bus", "rail_boardings", "total_rides"]
    sub_df = df[[c for c in cols_to_keep if c in df.columns]].copy()
    if day_col != "day_type":
        sub_df["day_type"] = sub_df[day_col]
    records = sub_df.to_dict(orient="records")
    return {
        "count": len(records),
        "days": records
    }

@router.get("/analytics/stations")
def get_station_performance_table(limit: int = Query(25, ge=5, le=144)):
    """
    Returns historical ridership performance ranking for CTA 'L' rail stations.
    """
    rail_path = os.path.join(PHASE4_DIR, "cta_daily_rail_station_forecasting_ready.csv")
    if not os.path.exists(rail_path):
        raise HTTPException(status_code=404, detail="Rail dataset not found")
        
    df = pd.read_csv(rail_path, low_memory=False)
    perf = df.groupby(["station_id", "stationname", "lines_served"]).agg(
        mean_daily_rides=("rides", "mean"),
        max_daily_rides=("rides", "max"),
        p90_daily_rides=("rides", lambda x: np.percentile(x, 90)),
        days_recorded=("rides", "count")
    ).reset_index()
    
    perf["mean_daily_rides"] = perf["mean_daily_rides"].round().astype(int)
    perf["max_daily_rides"] = perf["max_daily_rides"].astype(int)
    perf["p90_daily_rides"] = perf["p90_daily_rides"].round().astype(int)
    
    perf["demand_tier"] = perf["mean_daily_rides"].map(
        lambda r: crowd_classification_service.classify_station_demand("any", r)["classification"]
    )
    
    perf = perf.sort_values(by="mean_daily_rides", ascending=False).head(limit)
    return {
        "count": len(perf),
        "stations": perf.to_dict(orient="records")
    }

# =========================================================================
# TECHNICAL SPECIFICATION V3.8 ENDPOINTS: CLUSTERING, RANKING & REPLAY
# =========================================================================

@router.get("/route-groups")
def get_route_clusters():
    """
    Returns K-Means route-profile clustering results, centroids, and group explanations.
    (Technical Specification v3.8 Section 9)
    """
    return route_clustering_service.get_cluster_data()

@router.get("/rankings")
def get_route_productivity_rankings(
    day_type: str = Query("W", description="Day type: W (Weekday), A (Saturday), U (Sunday/Holiday)"),
    sort_by: str = Query("rides_per_scheduled_hour", description="Metric: rides_per_scheduled_hour, rides_per_scheduled_trip, mean_daily_rides")
):
    """
    Returns named, independent productivity ranking indicators for CTA bus corridors.
    (Technical Specification v3.8 Section 10)
    """
    return route_ranking_service.get_rankings(day_type=day_type, sort_by=sort_by)

@router.post("/replays")
def create_replay_session(
    reporting_delay_days: int = Query(1, ge=1, le=7, description="Assumed reporting delay in virtual days"),
    playback_speed_sec: int = Query(5, ge=1, le=30, description="Virtual clock duration in seconds per day")
):
    """
    Initializes a stateful historical replay session over the held-out test partition (2026-06-01 to 2026-07-31).
    (Technical Specification v3.8 Section 11)
    """
    return historical_replay_controller.create_session(
        reporting_delay_days=reporting_delay_days,
        playback_speed_sec=playback_speed_sec
    )

@router.get("/replays/{session_id}")
def get_replay_view(
    session_id: str,
    focus_route: str = Query("79", description="Focus route identifier for prediction vs actual evaluation")
):
    """
    Returns the current virtual date, permitted observations, saved prediction, and revealed actuals.
    """
    return historical_replay_controller.get_view_state(session_id=session_id, focus_route=focus_route)

@router.post("/replays/{session_id}/control")
def control_replay_session(
    session_id: str,
    action: str = Query(..., description="Action: START, PAUSE, ADVANCE, RESET, SET_DATE"),
    target_date: Optional[str] = Query(None, description="Target date (YYYY-MM-DD) if action is SET_DATE")
):
    """
    Executes playback controls on the historical replay session.
    """
    return historical_replay_controller.execute_step(
        session_id=session_id,
        action=action,
        target_date=target_date
    )

@router.get("/data/manifest")
def get_source_manifest():
    """
    Returns verified dataset source manifest with SHA-256 fingerprints, schemas, and timezones.
    (Technical Specification v3.8 Section 3)
    """
    manifest_path = os.path.join(BASE_DIR, "data", "source_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Source manifest not found")



