"""
RouteRanker FastAPI Application (Spec Section 9.17).
Serves data coverage, route discovery, cutoff-aware history, productivity rankings,
route comparisons, forecasts, stateful historical replay, conditional service scenarios,
JWT authentication & RBAC, overcrowding alerts, emergency broadcasts, schedule updates,
and congestion heatmap data.
"""
import os
import json
import uuid
from datetime import date, timedelta, datetime
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware

from backend.config import PROCESSED_DIR, ARTIFACTS_DIR
from backend.schemas import (
    LoginRequest,
    AlertConfigRequest,
    EmergencyBroadcastRequest,
    ScheduleUpdateRequest,
    ForecastRequest,
    ReplayCreateRequest,
    ReplayControlRequest,
    ScenarioRequest,
)
from backend.auth import (
    authenticate_user,
    create_jwt_token,
    get_current_user,
    require_authenticated_user,
    require_operator_or_admin,
)
from src.models import DEMAND_FEATURES, SERVICE_FEATURES
from src.scenarios import calculate_service_scenario

app = FastAPI(title="RouteRanker API", version="4.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

REPLAY_SESSIONS: dict[str, dict] = {}
SAVED_FORECASTS: dict[str, dict] = {}
SAVED_SCENARIOS: list[dict] = []

# Alert & Notification Stores
ALERT_CONFIGS: list[dict] = []
ACTIVE_ALERTS: list[dict] = []
EMERGENCY_BROADCASTS: list[dict] = []
SCHEDULE_UPDATES: list[dict] = []
NOTIFICATION_LOG: list[dict] = []

# Default overcrowding thresholds (auto-seeded on startup)
DEFAULT_THRESHOLDS = [
    {"route": "79", "metric": "rides_per_scheduled_hour", "threshold": 300.0, "condition": "above", "severity": "critical", "message": "Route 79 overcrowding: rides/hour exceeds 300"},
    {"route": "66", "metric": "rides_per_scheduled_hour", "threshold": 270.0, "condition": "above", "severity": "warning", "message": "Route 66 high utilization: rides/hour exceeds 270"},
    {"route": "8", "metric": "rides_per_scheduled_hour", "threshold": 260.0, "condition": "above", "severity": "warning", "message": "Route 8 high utilization: rides/hour exceeds 260"},
]


def _load_parquet(name: str) -> pd.DataFrame:
    path = os.path.join(PROCESSED_DIR, name)
    if not os.path.exists(path):
        raise HTTPException(status_code=503, detail=f"Processed dataset {name} not built yet.")
    return pd.read_parquet(path)


def _evaluate_alerts():
    """Check all alert configs against current data and generate active alerts."""
    global ACTIVE_ALERTS
    try:
        prof = _load_parquet("productivity_rankings.parquet")
    except Exception:
        return

    new_alerts = []
    for cfg in ALERT_CONFIGS:
        route_data = prof[prof["route"] == cfg["route"]]
        if route_data.empty:
            continue
        for _, row in route_data.iterrows():
            metric_val = row.get(cfg["metric"])
            if metric_val is None or pd.isna(metric_val):
                continue
            triggered = (cfg["condition"] == "above" and metric_val > cfg["threshold"]) or \
                        (cfg["condition"] == "below" and metric_val < cfg["threshold"])
            if triggered:
                alert = {
                    "alert_id": str(uuid.uuid4())[:8],
                    "route": cfg["route"],
                    "metric": cfg["metric"],
                    "metric_value": round(float(metric_val), 2),
                    "threshold": cfg["threshold"],
                    "condition": cfg["condition"],
                    "severity": cfg["severity"],
                    "message": cfg.get("message") or f"Route {cfg['route']}: {cfg['metric']} = {round(float(metric_val), 2)} ({cfg['condition']} {cfg['threshold']})",
                    "daytype": str(row.get("daytype", "W")),
                    "triggered_at": datetime.utcnow().isoformat() + "Z",
                    "acknowledged": False,
                }
                new_alerts.append(alert)
    ACTIVE_ALERTS = new_alerts


@app.on_event("startup")
def seed_default_alerts():
    for t in DEFAULT_THRESHOLDS:
        ALERT_CONFIGS.append(t)
    _evaluate_alerts()


# ─── Authentication Endpoints ───

@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_jwt_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }


@app.get("/api/auth/me")
def get_me(user: dict = Depends(require_authenticated_user)):
    return user


# ─── Alert & Notification Endpoints ───

@app.get("/api/alerts")
def list_alerts():
    _evaluate_alerts()
    return {"alerts": ACTIVE_ALERTS, "total": len(ACTIVE_ALERTS)}


@app.get("/api/alerts/configs")
def list_alert_configs():
    return {"configs": ALERT_CONFIGS}


@app.post("/api/alerts/configs")
def create_alert_config(req: AlertConfigRequest, user: dict = Depends(require_operator_or_admin)):
    cfg = {
        "config_id": str(uuid.uuid4())[:8],
        "route": req.route,
        "metric": req.metric,
        "threshold": req.threshold,
        "condition": req.condition,
        "severity": req.severity,
        "message": req.message,
        "created_by": user["username"],
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    ALERT_CONFIGS.append(cfg)
    _evaluate_alerts()
    return cfg


@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    for a in ACTIVE_ALERTS:
        if a["alert_id"] == alert_id:
            a["acknowledged"] = True
            NOTIFICATION_LOG.append({
                "type": "alert_acknowledged",
                "alert_id": alert_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })
            return a
    raise HTTPException(status_code=404, detail="Alert not found")


# ─── Emergency Broadcast Endpoints ───

@app.get("/api/broadcasts")
def list_broadcasts():
    return {"broadcasts": EMERGENCY_BROADCASTS}


@app.post("/api/broadcasts")
def create_broadcast(req: EmergencyBroadcastRequest, user: dict = Depends(require_operator_or_admin)):
    broadcast = {
        "broadcast_id": str(uuid.uuid4())[:8],
        "title": req.title,
        "message": req.message,
        "severity": req.severity,
        "affected_routes": req.affected_routes,
        "active": req.active,
        "created_by": user["username"],
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    EMERGENCY_BROADCASTS.append(broadcast)
    NOTIFICATION_LOG.append({
        "type": "emergency_broadcast",
        "broadcast_id": broadcast["broadcast_id"],
        "title": req.title,
        "timestamp": broadcast["created_at"],
    })
    return broadcast


@app.post("/api/broadcasts/{broadcast_id}/deactivate")
def deactivate_broadcast(broadcast_id: str, user: dict = Depends(require_operator_or_admin)):
    for b in EMERGENCY_BROADCASTS:
        if b["broadcast_id"] == broadcast_id:
            b["active"] = False
            return b
    raise HTTPException(status_code=404, detail="Broadcast not found")


# ─── Schedule Update Endpoints ───

@app.get("/api/schedule-updates")
def list_schedule_updates():
    return {"updates": SCHEDULE_UPDATES}


@app.post("/api/schedule-updates")
def create_schedule_update(req: ScheduleUpdateRequest, user: dict = Depends(require_operator_or_admin)):
    update = {
        "update_id": str(uuid.uuid4())[:8],
        "route": req.route,
        "service_date": req.service_date,
        "new_scheduled_trips": req.new_scheduled_trips,
        "reason": req.reason,
        "status": "applied",
        "created_by": user["username"],
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    SCHEDULE_UPDATES.append(update)
    NOTIFICATION_LOG.append({
        "type": "schedule_update",
        "update_id": update["update_id"],
        "route": req.route,
        "timestamp": update["created_at"],
    })
    return update


# ─── Notification Log ───

@app.get("/api/notifications")
def list_notifications():
    return {"notifications": sorted(NOTIFICATION_LOG, key=lambda n: n.get("timestamp", ""), reverse=True)}


# ─── Congestion Heatmap Data ───

@app.get("/api/heatmap")
def get_heatmap_data(daytype: str = Query(default="W", pattern="^(W|A|U)$")):
    prof = _load_parquet("productivity_rankings.parquet")
    structure = _load_parquet("route_structure.parquet")
    with open(os.path.join(PROCESSED_DIR, "route_shapes.json")) as f:
        shapes_doc = json.load(f)

    sub = prof[prof["daytype"] == daytype].copy()
    struct_map = structure.set_index("route").to_dict(orient="index")

    heatmap_points = []
    for _, row in sub.iterrows():
        route = row["route"]
        coords = shapes_doc["shapes"].get(route, [])
        intensity = float(row.get("rides_per_scheduled_hour", 0) or 0)
        rides = float(row.get("mean_daily_rides", 0) or 0)
        st = struct_map.get(route, {})
        for c in coords:
            heatmap_points.append({
                "route": route,
                "lat": c[0],
                "lng": c[1],
                "intensity": round(intensity, 2),
                "rides": round(rides, 0),
                "stop_count": st.get("served_stop_count"),
                "congestion_level": "critical" if intensity > 280 else ("high" if intensity > 200 else ("moderate" if intensity > 140 else "low")),
            })
    return {
        "daytype": daytype,
        "points": heatmap_points,
        "summary": {
            "total_routes": len(sub),
            "critical_routes": len(set(p["route"] for p in heatmap_points if p["congestion_level"] == "critical")),
            "high_routes": len(set(p["route"] for p in heatmap_points if p["congestion_level"] == "high")),
        },
    }


# ─── Original Data Endpoints (unchanged) ───

@app.get("/api/data/coverage")
def get_data_coverage():
    reg = _load_parquet("source_register.parquet")
    boardings = _load_parquet("boardings_clean.parquet")
    matched = _load_parquet("matched_utilization.parquet")
    unmatched_b = _load_parquet("unmatched_boardings.parquet")
    unmatched_s = _load_parquet("unmatched_schedule.parquet")

    with open(os.path.join(ARTIFACTS_DIR, "training_metrics.json")) as f:
        metrics = json.load(f)

    return {
        "sources": reg.to_dict(orient="records"),
        "ridership_summary": {
            "clean_rows": len(boardings),
            "routes": int(boardings["route"].nunique()),
            "min_date": str(boardings["date"].min()),
            "max_date": str(boardings["date"].max()),
            "genuine_zero_rows": int((boardings["rides"] == 0).sum()),
        },
        "matched_reconciliation": {
            "matched_rows": len(matched),
            "matched_routes": int(matched["route"].nunique()),
            "matched_dates": int(matched["date"].nunique()),
            "min_matched_date": str(matched["date"].min()),
            "max_matched_date": str(matched["date"].max()),
            "ridership_without_schedule_rows": len(unmatched_b),
            "schedule_without_ridership_rows": len(unmatched_s),
        },
        "model_evaluation": metrics,
    }


@app.get("/api/routes")
def list_routes():
    structure = _load_parquet("route_structure.parquet")
    clusters = _load_parquet("route_clusters.parquet")
    boardings = _load_parquet("boardings_clean.parquet")

    all_ids = sorted(set(boardings["route"]).union(set(structure["route"])))
    struct_map = structure.set_index("route").to_dict(orient="index")
    clust_map = clusters.set_index("route").to_dict(orient="index")

    out = []
    for r in all_ids:
        st = struct_map.get(r, {})
        cl = clust_map.get(r, {})
        out.append({
            "route": r,
            "has_gtfs_schedule": r in struct_map,
            "served_stop_count": st.get("served_stop_count"),
            "exclusive_stop_count": st.get("exclusive_stop_count"),
            "exclusive_stop_fraction": st.get("exclusive_stop_fraction"),
            "cluster_id": cl.get("cluster_id"),
            "cluster_label": cl.get("cluster_label", "Ungrouped"),
        })
    return {"routes": out}


@app.get("/api/routes/{route}/history")
def get_route_history(
    route: str,
    cutoff_date: str | None = Query(default=None, description="Enforces replay visibility cutoff"),
):
    boardings = _load_parquet("boardings_clean.parquet")
    matched = _load_parquet("matched_utilization.parquet")
    with open(os.path.join(PROCESSED_DIR, "route_shapes.json")) as f:
        shapes_doc = json.load(f)

    b_sub = boardings[boardings["route"] == route].copy()
    if cutoff_date:
        c_dt = date.fromisoformat(cutoff_date)
        b_sub = b_sub[b_sub["date"] <= c_dt]

    m_sub = matched[matched["route"] == route].copy()
    if cutoff_date:
        c_dt = date.fromisoformat(cutoff_date)
        m_sub = m_sub[m_sub["date"] <= c_dt]

    merged = b_sub.merge(
        m_sub[["date", "scheduled_trips", "scheduled_service_hours", "rides_per_scheduled_trip", "rides_per_scheduled_hour", "source_snapshot"]],
        on="date",
        how="left",
    ).sort_values("date")

    merged["date"] = merged["date"].astype(str)
    records = merged.where(pd.notnull(merged), None).to_dict(orient="records")

    return {
        "route": route,
        "cutoff_date": cutoff_date,
        "geometry_snapshot_id": shapes_doc["snapshot_id"],
        "coordinates": shapes_doc["shapes"].get(route, []),
        "history": records,
    }


@app.get("/api/rankings")
def get_rankings(daytype: str = Query(default="W", pattern="^(W|A|U)$")):
    prof = _load_parquet("productivity_rankings.parquet")
    sub = prof[prof["daytype"] == daytype].copy()
    sub = sub.sort_values(
        by=["eligible_for_ranking", "rides_per_scheduled_hour"],
        ascending=[False, False],
    )
    sub["date_min"] = sub["date_min"].astype(str)
    sub["date_max"] = sub["date_max"].astype(str)
    return {
        "daytype": daytype,
        "metric": "rides_per_scheduled_hour",
        "rankings": sub.where(pd.notnull(sub), None).to_dict(orient="records"),
    }


@app.get("/api/routes/compare")
def compare_routes(route_a: str, route_b: str, daytype: str = "W"):
    prof = _load_parquet("productivity_rankings.parquet")
    overlap = _load_parquet("route_overlap.parquet")

    pa = prof[(prof["route"] == route_a) & (prof["daytype"] == daytype)]
    pb = prof[(prof["route"] == route_b) & (prof["daytype"] == daytype)]

    ov = overlap[
        ((overlap["route_a"] == route_a) & (overlap["route_b"] == route_b))
        | ((overlap["route_a"] == route_b) & (overlap["route_b"] == route_a))
    ]
    return {
        "daytype": daytype,
        "route_a_profile": pa.where(pd.notnull(pa), None).to_dict(orient="records"),
        "route_b_profile": pb.where(pd.notnull(pb), None).to_dict(orient="records"),
        "stop_overlap": ov.to_dict(orient="records"),
    }


@app.post("/api/forecasts")
def generate_forecast(req: ForecastRequest):
    t_date = date.fromisoformat(req.target_date)
    v_date = date.fromisoformat(req.virtual_date) if req.virtual_date else t_date
    latest_permitted_ride_date = v_date - timedelta(days=req.reporting_delay_days)

    key = f"{req.route}|{req.target_date}|{v_date}"
    if key in SAVED_FORECASTS:
        return SAVED_FORECASTS[key]

    feats = _load_parquet("daily_forecasting_features.parquet")
    sched = _load_parquet("selected_schedule.parquet")

    row_df = feats[(feats["route"] == req.route) & (feats["date"] == t_date)].copy()
    if row_df.empty:
        res = {
            "route": req.route,
            "target_date": req.target_date,
            "issued_at_virtual_date": str(v_date),
            "latest_available_ride_date": str(latest_permitted_ride_date),
            "forecast_status": "insufficient_history",
            "predicted_rides": None,
            "reason": "No feature row exists for route/target_date",
        }
        SAVED_FORECASTS[key] = res
        return res

    if (t_date - timedelta(days=1)) > latest_permitted_ride_date:
        row_df["rides_1_day_before"] = None

    s_row = sched[(sched["route"] == req.route) & (sched["service_date"] == t_date) & (sched["archive_available_from"] < v_date)]
    with open(os.path.join(ARTIFACTS_DIR, "training_metrics.json")) as f:
        metrics = json.load(f)

    if not s_row.empty and row_df[DEMAND_FEATURES].notna().all(axis=1).iloc[0]:
        merged = row_df.merge(s_row[["route", "service_date", "scheduled_trips", "scheduled_service_hours", "source_snapshot"]], left_on=["route", "date"], right_on=["route", "service_date"])
        if merged[SERVICE_FEATURES].notna().all(axis=1).iloc[0]:
            sel_name = metrics["matched_service"]["selected_serving_model"]
            pipe = joblib.load(metrics["matched_service"]["models"][sel_name]["artifact_path"])
            pred = max(0.0, float(pipe.predict(merged[SERVICE_FEATURES])[0]))
            res = {
                "route": req.route,
                "target_date": req.target_date,
                "issued_at_virtual_date": str(v_date),
                "latest_available_ride_date": str(latest_permitted_ride_date),
                "forecast_status": "ok_service_aware",
                "model_used": f"matched_service_{sel_name}",
                "schedule_snapshot": str(merged["source_snapshot"].iloc[0]),
                "predicted_rides": round(pred, 1),
                "units": "rides/day",
            }
            SAVED_FORECASTS[key] = res
            return res

    if row_df[DEMAND_FEATURES].notna().all(axis=1).iloc[0]:
        sel_name = metrics["demand_only"]["selected_serving_model"]
        pipe = joblib.load(metrics["demand_only"]["models"][sel_name]["artifact_path"])
        pred = max(0.0, float(pipe.predict(row_df[DEMAND_FEATURES])[0]))
        res = {
            "route": req.route,
            "target_date": req.target_date,
            "issued_at_virtual_date": str(v_date),
            "latest_available_ride_date": str(latest_permitted_ride_date),
            "forecast_status": "fallback_demand_only",
            "model_used": f"demand_only_{sel_name}",
            "predicted_rides": round(pred, 1),
            "units": "rides/day",
        }
        SAVED_FORECASTS[key] = res
        return res

    res = {
        "route": req.route,
        "target_date": req.target_date,
        "issued_at_virtual_date": str(v_date),
        "latest_available_ride_date": str(latest_permitted_ride_date),
        "forecast_status": "insufficient_history",
        "predicted_rides": None,
        "reason": "Required historical lags unavailable at issue time",
    }
    SAVED_FORECASTS[key] = res
    return res


@app.post("/api/replays")
def create_replay(req: ReplayCreateRequest):
    sid = str(uuid.uuid4())[:8]
    REPLAY_SESSIONS[sid] = {
        "session_id": sid,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "current_virtual_date": req.start_date,
        "reporting_delay_days": req.reporting_delay_days,
        "speed_seconds": req.speed_seconds,
        "status": "paused",
    }
    return REPLAY_SESSIONS[sid]


@app.get("/api/replays/{session_id}")
def get_replay(session_id: str):
    if session_id not in REPLAY_SESSIONS:
        raise HTTPException(status_code=404, detail="Replay session not found")
    return REPLAY_SESSIONS[session_id]


@app.post("/api/replays/{session_id}/control")
def control_replay(session_id: str, req: ReplayControlRequest):
    if session_id not in REPLAY_SESSIONS:
        raise HTTPException(status_code=404, detail="Replay session not found")
    sess = REPLAY_SESSIONS[session_id]
    if req.action == "start":
        sess["status"] = "running"
    elif req.action == "pause":
        sess["status"] = "paused"
    elif req.action == "reset":
        sess["status"] = "paused"
        sess["current_virtual_date"] = sess["start_date"]
    elif req.action == "advance":
        cur = date.fromisoformat(sess["current_virtual_date"])
        end = date.fromisoformat(sess["end_date"])
        if cur < end:
            sess["current_virtual_date"] = str(cur + timedelta(days=1))
        else:
            sess["status"] = "completed"
    return sess


@app.post("/api/scenarios")
def run_scenario(req: ScenarioRequest):
    matched = _load_parquet("matched_utilization.parquet")
    s_date = date.fromisoformat(req.service_date)
    sub = matched[(matched["route"] == req.route) & (matched["date"] == s_date)]
    if sub.empty:
        raise HTTPException(status_code=404, detail="No matched baseline schedule/demand found for route/date.")

    row = sub.iloc[0]
    calc = calculate_service_scenario(
        baseline_rides=float(row["rides"]),
        baseline_trips=int(row["scheduled_trips"]),
        baseline_hours=float(row["scheduled_service_hours"]) if pd.notna(row["scheduled_service_hours"]) else None,
        proposed_trips=req.proposed_trips,
        demand_multiplier=req.demand_multiplier,
        assumed_trip_duration_minutes=req.assumed_trip_duration_minutes,
    )
    record = {
        "scenario_id": str(uuid.uuid4())[:8],
        "route": req.route,
        "service_date": req.service_date,
        "source_snapshot": str(row["source_snapshot"]),
        **calc,
    }
    SAVED_SCENARIOS.append(record)
    return record


@app.get("/api/scenarios")
def list_scenarios():
    return {"scenarios": SAVED_SCENARIOS}
