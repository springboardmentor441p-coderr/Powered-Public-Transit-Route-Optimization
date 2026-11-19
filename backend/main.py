import json
import os
import pickle
import uuid
from datetime import date, timedelta
from typing import Optional
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DATA_DIR = "data/processed/v1"
ARTIFACT_DIR = "artifacts/v1"

app = FastAPI(title="RouteRanker API", version="3.8.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load versioned artifacts and datasets into memory (or query from PostgreSQL in production)
features_df = pd.read_csv(os.path.join(DATA_DIR, "expanded_demand_service_features.csv"))
features_df["date"] = pd.to_datetime(features_df["date"]).dt.date
profiles_df = pd.read_csv(os.path.join(DATA_DIR, "expanded_utilization_profiles.csv"))
clusters_df = pd.read_csv(os.path.join(DATA_DIR, "route_clusters.csv"))

with open(os.path.join(ARTIFACT_DIR, "service_forecaster.pkl"), "rb") as f:
    service_artifact = pickle.load(f)
with open(os.path.join(ARTIFACT_DIR, "forecast_eval_report.json")) as f:
    eval_report = json.load(f)

# In-memory session & audit stores (backed by PostgreSQL tables in deployment)
REPLAY_SESSIONS: dict[str, dict] = {}
SAVED_FORECASTS: dict[tuple, dict] = {}
SAVED_SCENARIOS: list[dict] = []

class ReplayCreateRequest(BaseModel):
    start_date: date = date(2026, 6, 1)
    end_date: date = date(2026, 7, 31)
    reporting_delay_days: int = 1
    speed_seconds_per_day: float = 5.0

class ReplayControlRequest(BaseModel):
    action: str  # "start", "pause", "advance", "reset"

class ScenarioRequest(BaseModel):
    route: str
    target_date: date
    baseline_rides: float
    baseline_trips: int
    proposed_trips: int = Field(ge=0)
    assumed_trip_duration_minutes: float = Field(gt=0)
    demand_stress_pct: float = 0.0

def generate_and_store_forecast(session_id: str, route: str, target_date: date, virtual_date: date, delay_days: int) -> dict:
    key = (session_id, route, target_date)
    if key in SAVED_FORECASTS:
        return SAVED_FORECASTS[key]

    latest_permitted_date = virtual_date - timedelta(days=delay_days)
    row = features_df[(features_df["route"] == route) & (features_df["date"] == target_date)]
    if row.empty:
        res = {
            "route": route, "target_date": str(target_date), "issued_at": str(virtual_date),
            "status": "unavailable", "reason": "No scheduled service or observation record for route/date",
            "predicted_rides": None, "model_version": service_artifact["version"]
        }
        SAVED_FORECASTS[key] = res
        return res

    r = row.iloc[0].copy()
    # Enforce issue-time availability: verify lag_1d is not newer than latest_permitted_date
    if (target_date - timedelta(days=1)) > latest_permitted_date:
        r["rides_1_day_before"] = np.nan

    # Apply Option 2 missing-history rule
    r["rides_28_days_before_available"] = 1 if pd.notna(r["rides_28_days_before"]) else 0
    if pd.isna(r["rides_28_days_before"]):
        donors = [r[c] for c in ["rides_7_days_before", "rides_14_days_before", "rides_21_days_before"] if pd.notna(r[c])]
        r["rides_28_days_before"] = np.mean(donors) if donors else np.nan

    req_cols = service_artifact["features"]
    if any(pd.isna(r[c]) for c in req_cols):
        res = {
            "route": route, "target_date": str(target_date), "issued_at": str(virtual_date),
            "status": "insufficient_history",
            "reason": "Missing permitted historical lags or scheduled service inputs",
            "predicted_rides": None,
            "scheduled_trips": int(r["scheduled_trips"]),
            "scheduled_service_hours": round(float(r["scheduled_service_hours"]), 2) if pd.notna(r["scheduled_service_hours"]) else None,
            "model_version": service_artifact["version"],
            "latest_permitted_ride_date": str(latest_permitted_date),
        }
    else:
        X = pd.DataFrame([r[req_cols]])
        pred = max(0.0, float(service_artifact["pipeline"].predict(X)[0]))
        res = {
            "route": route, "target_date": str(target_date), "issued_at": str(virtual_date),
            "status": "predicted",
            "predicted_rides": round(pred, 1),
            "scheduled_trips": int(r["scheduled_trips"]),
            "scheduled_service_hours": round(float(r["scheduled_service_hours"]), 2),
            "model_version": service_artifact["version"],
            "latest_permitted_ride_date": str(latest_permitted_date),
        }

    SAVED_FORECASTS[key] = res
    return res

@app.get("/api/data/coverage")
def get_coverage():
    return {
        "network": "Chicago Transit Authority (CTA) Buses",
        "ridership_range": ["2001-01-01", "2026-07-31"],
        "matched_analysis_range": ["2025-11-23", "2026-07-31"],
        "matched_rows": 28374,
        "unmatched_rides_rows": 424,
        "unmatched_schedule_rows": 24,
        "evaluation_summary": eval_report,
    }

@app.get("/api/routes")
def list_routes():
    routes = sorted(profiles_df["route"].unique().tolist())
    return {"routes": routes, "count": len(routes)}

@app.get("/api/rankings")
def get_rankings(daytype: str = "W", metric: str = "rides_per_scheduled_hour"):
    sub = profiles_df[profiles_df["daytype"] == daytype].copy()
    sub = sub.merge(clusters_df[["route", "cluster_label"]], on="route", how="left")
    sub["cluster_label"] = sub["cluster_label"].fillna("Ungrouped")
    sub = sub.sort_values(by=["is_ranking_eligible", metric], ascending=[False, False])
    return sub.replace({np.nan: None}).to_dict(orient="records")

@app.get("/api/routes/{route}/history")
def get_route_history(route: str, session_id: Optional[str] = None):
    sub = features_df[features_df["route"] == route].sort_values("date").copy()
    if sub.empty:
        raise HTTPException(status_code=404, detail="Route not found")

    if session_id and session_id in REPLAY_SESSIONS:
        sess = REPLAY_SESSIONS[session_id]
        cutoff = sess["virtual_date"] - timedelta(days=sess["reporting_delay_days"])
        # Hide actual rides after the reporting cutoff (Section 9.16.3)
        sub["rides"] = sub.apply(lambda r: r["rides"] if r["date"] <= cutoff else None, axis=1)

    return sub[["route", "date", "daytype", "rides", "scheduled_trips", "scheduled_service_hours"]].replace({np.nan: None}).to_dict(orient="records")

@app.post("/api/replays")
def create_replay(req: ReplayCreateRequest):
    sid = str(uuid.uuid4())[:8]
    REPLAY_SESSIONS[sid] = {
        "session_id": sid,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "virtual_date": req.start_date,
        "reporting_delay_days": req.reporting_delay_days,
        "speed_seconds_per_day": req.speed_seconds_per_day,
        "status": "paused",
    }
    return REPLAY_SESSIONS[sid]

@app.post("/api/replays/{session_id}/control")
def control_replay(session_id: str, req: ReplayControlRequest):
    if session_id not in REPLAY_SESSIONS:
        raise HTTPException(status_code=404, detail="Replay session not found")
    sess = REPLAY_SESSIONS[session_id]

    if req.action == "start":
        sess["status"] = "running"
    elif req.action == "pause":
        sess["status"] = "paused"
    elif req.action == "advance":
        if sess["virtual_date"] < sess["end_date"]:
            sess["virtual_date"] += timedelta(days=1)
        else:
            sess["status"] = "completed"
    elif req.action == "reset":
        sess["virtual_date"] = sess["start_date"]
        sess["status"] = "paused"
    return sess

@app.get("/api/replays/{session_id}/forecast/{route}")
def get_replay_forecast(session_id: str, route: str):
    if session_id not in REPLAY_SESSIONS:
        raise HTTPException(status_code=404, detail="Replay session not found")
    sess = REPLAY_SESSIONS[session_id]
    vdate = sess["virtual_date"]
    forecast = generate_and_store_forecast(session_id, route, vdate, vdate, sess["reporting_delay_days"])

    # Also return yesterday's forecast vs newly revealed actual (if permitted)
    prev_date = vdate - timedelta(days=1)
    prev_forecast = SAVED_FORECASTS.get((session_id, route, prev_date))
    prev_actual = None
    if prev_date <= (vdate - timedelta(days=sess["reporting_delay_days"])):
        act_row = features_df[(features_df["route"] == route) & (features_df["date"] == prev_date)]
        if not act_row.empty:
            prev_actual = int(act_row.iloc[0]["rides"])

    return {
        "session": sess,
        "current_forecast": forecast,
        "previous_day_comparison": {
            "date": str(prev_date),
            "saved_prediction": prev_forecast["predicted_rides"] if prev_forecast else None,
            "revealed_actual_rides": prev_actual,
        }
    }

@app.post("/api/scenarios")
def run_scenario(req: ScenarioRequest):
    base_hours = (req.baseline_trips * req.assumed_trip_duration_minutes) / 60.0
    prop_hours = (req.proposed_trips * req.assumed_trip_duration_minutes) / 60.0
    stressed_demand = req.baseline_rides * (1.0 + req.demand_stress_pct / 100.0)

    result = {
        "scenario_id": str(uuid.uuid4())[:8],
        "route": req.route,
        "target_date": str(req.target_date),
        "assumptions": {
            "assumed_trip_duration_minutes": req.assumed_trip_duration_minutes,
            "demand_stress_pct": req.demand_stress_pct,
            "note": "Conditional arithmetic under fixed/stressed demand; does not imply causal elasticity or vehicle/crew feasibility."
        },
        "baseline": {
            "rides": round(req.baseline_rides, 1),
            "scheduled_trips": req.baseline_trips,
            "scheduled_trip_hours": round(base_hours, 2),
            "rides_per_scheduled_trip": round(req.baseline_rides / req.baseline_trips, 2) if req.baseline_trips > 0 else None,
            "rides_per_scheduled_hour": round(req.baseline_rides / base_hours, 2) if base_hours > 0 else None,
        },
        "proposed": {
            "assumed_rides": round(stressed_demand, 1),
            "scheduled_trips": req.proposed_trips,
            "scheduled_trip_hours": round(prop_hours, 2),
            "rides_per_scheduled_trip": round(stressed_demand / req.proposed_trips, 2) if req.proposed_trips > 0 else None,
            "rides_per_scheduled_hour": round(stressed_demand / prop_hours, 2) if prop_hours > 0 else None,
        }
    }
    SAVED_SCENARIOS.append(result)
    return result