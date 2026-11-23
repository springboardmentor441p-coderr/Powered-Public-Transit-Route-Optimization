import os
import json
import uuid
import pickle
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from schemas import ReplayCreateRequest, ReplayControlRequest, ScenarioRequest

app = FastAPI(title="RouteRanker CTA Prototype API", version="3.8.0")

# Enable CORS for React + Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data", "processed"))
MODEL_PATH = os.path.join(BASE_DIR, "models", "xgb_option2_pipeline.pkl")

# Load precomputed artifacts into memory at startup
print("Loading processed RouteRanker artifacts...")
df_boardings_2yr = pd.read_parquet(os.path.join(DATA_DIR, "clean_boardings_2yr.parquet"))
df_boardings_2yr["date_str"] = df_boardings_2yr["date"].dt.strftime("%Y-%m-%d")

df_matched = pd.read_parquet(os.path.join(DATA_DIR, "matched_demand_service.parquet"))
df_schedules = pd.read_parquet(os.path.join(DATA_DIR, "selected_daily_schedules.parquet"))
df_features = pd.read_parquet(os.path.join(DATA_DIR, "demand_features_option2.parquet"))
df_features["date_str"] = df_features["date"].dt.strftime("%Y-%m-%d")

df_profiles = pd.read_parquet(os.path.join(DATA_DIR, "route_daytype_profiles.parquet"))
df_clusters = pd.read_parquet(os.path.join(DATA_DIR, "route_clusters.parquet"))
df_coverage = pd.read_parquet(os.path.join(DATA_DIR, "route_stop_coverage.parquet"))
df_overlap = pd.read_parquet(os.path.join(DATA_DIR, "route_stop_overlap.parquet"))

with open(os.path.join(DATA_DIR, "route_shapes.json"), "r") as f:
    route_shapes = json.load(f)

with open(MODEL_PATH, "rb") as f:
    model_artifact = pickle.load(f)

xgb_model = model_artifact["model"]
model_features = model_artifact["features"]
route_encoding_map = model_artifact["route_encoding"]

# In-memory state stores for Replay Sessions & Saved Scenarios
replay_sessions = {}
saved_scenarios = []

CLUSTER_NAMES = {
    0: "Low-Volume Feeder / Local Coverage",
    1: "High-Density Commuter Trunk",
    2: "Moderate Urban Connector",
    3: "Special Event / Weekend Outlier"
}
df_clusters["cluster_label"] = df_clusters["cluster"].map(CLUSTER_NAMES)

def clean_nans(records):
    """Replace NaN/Inf with None for strict JSON compliance."""
    return json.loads(pd.DataFrame(records).to_json(orient="records"))

# ---------------------------------------------------------
# 1. Data Provenance & Coverage
# ---------------------------------------------------------
@app.get("/api/data/coverage")
def get_data_coverage():
    return {
        "agency": "Chicago Transit Authority (CTA)",
        "timezone": "America/Chicago",
        "dataset_versions": {
            "ridership_window": "2024-08-01 to 2026-07-31 (83,997 route/date rows)",
            "matched_window": "2025-11-23 to 2026-07-31 (251 calendar dates)",
            "gtfs_archives_used": 8,
            "geometry_version": "google_transit_2026_09"
        },
        "reconciliation_counts": {
            "total_scheduled_records": int(len(df_schedules)),
            "matched_demand_service": int(len(df_matched)),
            "distinct_matched_routes": int(df_matched["route"].nunique()),
            "unmatched_schedule_without_rides": 24,  # Route 169
            "unmatched_rides_without_schedule": 424  # Routes 1001, 19, 130, 10, 128, 59, 7
        },
        "model_metadata": {
            "model_version": model_artifact["model_version"],
            "policy": model_artifact["policy"],
            "metrics": model_artifact["metrics"]
        }
    }

# ---------------------------------------------------------
# 2. Route Discovery & History
# ---------------------------------------------------------
@app.get("/api/routes")
def get_routes(cluster: Optional[int] = None):
    merged = pd.merge(df_clusters, df_coverage, on="route", how="left")
    if cluster is not None:
        merged = merged[merged["cluster"] == cluster]
    merged = merged.sort_values("avg_daily_rides", ascending=False)
    return clean_nans(merged)

@app.get("/api/routes/{route}/history")
def get_route_history(
    route: str,
    mode: str = Query("historical", description="historical | replay"),
    max_permitted_date: Optional[str] = Query(None, description="Cutoff date in replay mode")
):
    sub = df_matched[df_matched["route"] == route].copy()
    if sub.empty:
        # Fallback to demand-only if route has no matched GTFS (e.g., Route 1001)
        sub = df_boardings_2yr[df_boardings_2yr["route"] == route].copy()
        sub["service_date"] = sub["date_str"]
        sub["scheduled_trips"] = None
        sub["scheduled_service_hours"] = None
        sub["boardings_per_scheduled_trip"] = None
        sub["boardings_per_scheduled_service_hour"] = None
        sub["source_snapshot"] = "unmatched_schedule"

    if mode == "replay" and max_permitted_date:
        sub = sub[sub["service_date"] <= max_permitted_date]

    sub = sub.sort_values("service_date")
    geometry = route_shapes.get(route, [])
    cov = df_coverage[df_coverage["route"] == route].to_dict(orient="records")

    return {
        "route": route,
        "mode": mode,
        "cutoff_date": max_permitted_date if mode == "replay" else "2026-07-31",
        "coverage": cov[0] if cov else None,
        "geometry_version": "google_transit_2026_09" if geometry else "unavailable",
        "shape_coordinates": geometry,
        "history": clean_nans(sub[[
            "service_date", "daytype", "rides", "scheduled_trips",
            "scheduled_service_hours", "boardings_per_scheduled_trip",
            "boardings_per_scheduled_service_hour", "source_snapshot"
        ]])
    }

# ---------------------------------------------------------
# 3. Rankings, Route Groups & Corridor Comparisons
# ---------------------------------------------------------
@app.get("/api/rankings")
def get_rankings(
    daytype: str = Query("W", description="W | A | U"),
    metric: str = Query("rides_per_scheduled_hour", description="rides_per_scheduled_hour | rides_per_scheduled_trip | total_rides"),
    eligible_only: bool = True
):
    sub = df_profiles[df_profiles["daytype"] == daytype].copy()
    if eligible_only:
        sub = sub[sub["is_eligible"] == True]

    if metric in sub.columns:
        sub = sub.sort_values(metric, ascending=False, na_position="last")

    # Attach cluster label
    sub = pd.merge(sub, df_clusters[["route", "cluster", "cluster_label"]], on="route", how="left")
    return {
        "daytype": daytype,
        "metric": metric,
        "eligibility_rule": "Minimum 20 matched service days within daytype (Section 9.7.2)",
        "results": clean_nans(sub)
    }

@app.get("/api/route-groups")
def get_route_groups():
    summary = df_clusters.groupby(["cluster", "cluster_label"]).agg(
        route_count=("route", "count"),
        mean_daily_rides=("avg_daily_rides", "mean"),
        mean_trips_per_day=("avg_trips_per_day", "mean"),
        mean_boardings_per_trip=("boardings_per_trip", "mean"),
        mean_weekend_ratio=("weekend_weekday_ratio", "mean")
    ).reset_index().round(2)

    return {
        "profile_period": "2024-08-01 to 2026-07-31",
        "algorithm": "KMeans (k=4, StandardScaler)",
        "groups": clean_nans(summary),
        "memberships": clean_nans(df_clusters[["route", "cluster", "cluster_label", "avg_daily_rides", "boardings_per_trip"]])
    }

@app.get("/api/routes/compare")
def compare_routes(route_a: str, route_b: str, daytype: str = "W"):
    prof_a = df_profiles[(df_profiles["route"] == route_a) & (df_profiles["daytype"] == daytype)].to_dict(orient="records")
    prof_b = df_profiles[(df_profiles["route"] == route_b) & (df_profiles["daytype"] == daytype)].to_dict(orient="records")

    overlap_row = df_overlap[
        ((df_overlap["route_a"] == route_a) & (df_overlap["route_b"] == route_b)) |
        ((df_overlap["route_a"] == route_b) & (df_overlap["route_b"] == route_a))
    ].to_dict(orient="records")

    return {
        "daytype": daytype,
        "geometry_version": "google_transit_2026_09",
        "route_a": {
            "profile": prof_a[0] if prof_a else None,
            "shape": route_shapes.get(route_a, [])
        },
        "route_b": {
            "profile": prof_b[0] if prof_b else None,
            "shape": route_shapes.get(route_b, [])
        },
        "overlap": overlap_row[0] if overlap_row else {
            "shared_stop_count": 0,
            "jaccard_overlap": 0.0,
            "smaller_route_overlap": 0.0
        }
    }

# ---------------------------------------------------------
# 4. Option 2 Demand Forecasting Inference
# ---------------------------------------------------------
def run_option2_forecast(route: str, target_date: str, max_permitted_ride_date: str):
    row = df_features[(df_features["route"] == route) & (df_features["date_str"] == target_date)]
    sched_row = df_schedules[(df_schedules["route"] == route) & (df_schedules["service_date"] == target_date)]

    scheduled_trips = int(sched_row.iloc[0]["scheduled_trips"]) if not sched_row.empty else None
    scheduled_hours = float(sched_row.iloc[0]["scheduled_service_hours"]) if (not sched_row.empty and pd.notna(sched_row.iloc[0]["scheduled_service_hours"])) else None
    snapshot_id = str(sched_row.iloc[0]["source_snapshot"]) if not sched_row.empty else "unavailable"

    if row.empty:
        return {
            "route": route,
            "target_date": target_date,
            "status": "unavailable",
            "reason": "No feature record exists for target date",
            "predicted_rides": None,
            "scheduled_trips": scheduled_trips,
            "scheduled_service_hours": scheduled_hours,
            "source_snapshot": snapshot_id
        }

    r = row.iloc[0]
    target_dt = pd.to_datetime(target_date)
    permitted_dt = pd.to_datetime(max_permitted_ride_date)

    # Check if required 1-day lag violates the replay reporting delay boundary
    lag1_date = target_dt - timedelta(days=1)
    if lag1_date > permitted_dt or not bool(r["forecast_eligible"]):
        return {
            "route": route,
            "target_date": target_date,
            "status": "insufficient_history",
            "reason": "Required historical lag unavailable under reporting delay or Option 2 policy",
            "predicted_rides": None,
            "scheduled_trips": scheduled_trips,
            "scheduled_service_hours": scheduled_hours,
            "source_snapshot": snapshot_id
        }

    # Build exact feature vector
    input_dict = {col: r[col] for col in model_features if col != "route_encoded"}
    input_dict["route_encoded"] = route_encoding_map.get(route, 0)
    X_in = pd.DataFrame([input_dict])[model_features]

    pred_val = max(0.0, float(xgb_model.predict(X_in)[0]))

    # Reveal actual rides ONLY if target_date <= max_permitted_ride_date
    actual_rides = int(r["rides"]) if target_dt <= permitted_dt else None

    return {
        "route": route,
        "target_date": target_date,
        "status": "predicted",
        "model_version": model_artifact["model_version"],
        "policy": "Option 2 (D-01)",
        "latest_permitted_ride_date": max_permitted_ride_date,
        "predicted_rides": round(pred_val, 1),
        "actual_rides": actual_rides,
        "rides_28_days_before_available": int(r["rides_28_days_before_available"]),
        "scheduled_trips": scheduled_trips,
        "scheduled_service_hours": scheduled_hours,
        "predicted_rides_per_trip": round(pred_val / scheduled_trips, 2) if scheduled_trips else None,
        "source_snapshot": snapshot_id
    }

@app.get("/api/forecasts")
def get_forecast(route: str, target_date: str, permitted_until: str = "2026-07-31"):
    return run_option2_forecast(route, target_date, permitted_until)

# ---------------------------------------------------------
# 5. Historical Replay State Machine (Section 9.14)
# ---------------------------------------------------------
@app.post("/api/replays")
def create_replay_session(req: ReplayCreateRequest):
    session_id = str(uuid.uuid4())[:8]
    replay_sessions[session_id] = {
        "session_id": session_id,
        "virtual_date": req.start_date,
        "min_date": "2026-06-01",
        "max_date": "2026-07-31",
        "reporting_delay_days": req.reporting_delay_days,
        "speed_seconds": req.speed_seconds,
        "status": "paused",
        "model_version": model_artifact["model_version"]
    }
    return replay_sessions[session_id]

@app.get("/api/replays/{session_id}")
def get_replay_state(session_id: str, route: str = "22"):
    if session_id not in replay_sessions:
        raise HTTPException(status_code=404, detail="Replay session not found")

    sess = replay_sessions[session_id]
    v_dt = pd.to_datetime(sess["virtual_date"])
    permitted_dt = v_dt - timedelta(days=sess["reporting_delay_days"])
    permitted_str = permitted_dt.strftime("%Y-%m-%d")

    forecast_payload = run_option2_forecast(route, sess["virtual_date"], permitted_str)

    return {
        "session": sess,
        "permitted_history_through": permitted_str,
        "active_route_forecast": forecast_payload
    }

@app.post("/api/replays/{session_id}/control")
def control_replay_session(session_id: str, req: ReplayControlRequest):
    if session_id not in replay_sessions:
        raise HTTPException(status_code=404, detail="Replay session not found")

    sess = replay_sessions[session_id]
    action = req.action.lower()

    if action == "start":
        sess["status"] = "running"
    elif action == "pause":
        sess["status"] = "paused"
    elif action == "reset":
        sess["status"] = "paused"
        sess["virtual_date"] = req.target_date if req.target_date else sess["min_date"]
    elif action == "advance":
        curr = pd.to_datetime(sess["virtual_date"])
        nxt = curr + timedelta(days=1)
        if nxt > pd.to_datetime(sess["max_date"]):
            sess["status"] = "completed"
        else:
            sess["virtual_date"] = nxt.strftime("%Y-%m-%d")
    else:
        raise HTTPException(status_code=400, detail="Invalid replay action")

    return sess

# ---------------------------------------------------------
# 6. Conditional Service Scenario Engine (Section 9.15)
# ---------------------------------------------------------
@app.post("/api/scenarios")
def evaluate_scenario(req: ScenarioRequest):
    # Derive mean trip duration in minutes
    if req.assumed_trip_duration_mins is not None:
        mean_dur_mins = req.assumed_trip_duration_mins
    elif req.baseline_hours and req.baseline_trips > 0:
        mean_dur_mins = (req.baseline_hours * 60.0) / req.baseline_trips
    else:
        mean_dur_mins = None

    # Stressed demand arithmetic
    stressed_rides = req.baseline_rides * (1.0 + req.demand_stress_pct / 100.0)
    scenario_hours = round((req.proposed_trips * mean_dur_mins) / 60.0, 2) if mean_dur_mins is not None else None

    base_rides_per_trip = round(req.baseline_rides / req.baseline_trips, 2) if req.baseline_trips > 0 else None
    scen_rides_per_trip = round(stressed_rides / req.proposed_trips, 2) if req.proposed_trips > 0 else None

    base_rides_per_hour = round(req.baseline_rides / req.baseline_hours, 2) if (req.baseline_hours and req.baseline_hours > 0) else None
    scen_rides_per_hour = round(stressed_rides / scenario_hours, 2) if (scenario_hours and scenario_hours > 0) else None

    result = {
        "scenario_id": str(uuid.uuid4())[:8],
        "route": req.route,
        "service_date": req.service_date,
        "daytype": req.daytype,
        "assumptions": {
            "demand_stress_pct": req.demand_stress_pct,
            "assumed_mean_trip_duration_mins": round(mean_dur_mins, 1) if mean_dur_mins else None,
            "note": "Conditional planning arithmetic; assumes fixed demand elasticity and constant trip duration."
        },
        "baseline": {
            "rides": round(req.baseline_rides, 1),
            "scheduled_trips": req.baseline_trips,
            "scheduled_hours": req.baseline_hours,
            "rides_per_trip": base_rides_per_trip,
            "rides_per_hour": base_rides_per_hour
        },
        "scenario": {
            "rides": round(stressed_rides, 1),
            "proposed_trips": req.proposed_trips,
            "proposed_hours": scenario_hours,
            "rides_per_trip": scen_rides_per_trip,
            "rides_per_hour": scen_rides_per_hour
        }
    }
    saved_scenarios.append(result)
    return result

@app.get("/api/scenarios")
def list_saved_scenarios():
    return saved_scenarios