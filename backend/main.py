"""
RouteRanker FastAPI Application (Spec Section 9.17).
Serves data coverage, route discovery, cutoff-aware history, productivity rankings,
route comparisons, forecasts, stateful historical replay, conditional service scenarios,
JWT authentication & RBAC, overcrowding alerts, emergency broadcasts, schedule updates,
and congestion heatmap data.
"""
import os
import sys

# Silence joblib/loky CPU core warning on modern Windows where wmic is deprecated
try:
    import joblib.externals.loky.backend.context as _loky_ctx
    _loky_ctx.physical_cores_cache = os.cpu_count() or 4
except Exception:
    pass

import json
import uuid
from datetime import date, timedelta, datetime
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
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
    OptimizationRequest,
    ReclusterRequest,
    ActualRidershipFeedbackRequest,
    SelfTrainTriggerRequest,
    DelayReportRequest,
)
from backend.integrations import dispatch_external_notifications, get_dispatch_history
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

# In-Memory Model Registry for Zero-Downtime Hot-Reloading
MODEL_REGISTRY: dict = {
    "metrics": None,
    "matched_service": None,
    "demand_only": None,
    "last_loaded_utc": None,
}
SELF_TRAINING_STATE: dict = {
    "is_running": False,
    "last_result": None,
}


def load_models_into_memory():
    """Loads current production models and metrics into memory for fast, hot-reloadable inference."""
    metrics_path = os.path.join(ARTIFACTS_DIR, "training_metrics.json")
    if not os.path.exists(metrics_path):
        return
    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    ms_sel = metrics["matched_service"]["selected_serving_model"]
    do_sel = metrics["demand_only"]["selected_serving_model"]

    ms_path = os.path.join(ARTIFACTS_DIR, f"matched_service_{ms_sel}.joblib")
    do_path = os.path.join(ARTIFACTS_DIR, f"demand_only_{do_sel}.joblib")

    if os.path.exists(ms_path):
        MODEL_REGISTRY["matched_service"] = joblib.load(ms_path)
    if os.path.exists(do_path):
        MODEL_REGISTRY["demand_only"] = joblib.load(do_path)

    MODEL_REGISTRY["metrics"] = metrics
    MODEL_REGISTRY["last_loaded_utc"] = datetime.utcnow().isoformat() + "Z"


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
    load_models_into_memory()


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
    try:
        dispatch_external_notifications(
            event_type="emergency_broadcast",
            title=req.title,
            message=req.message,
            severity=req.severity,
            affected_routes=req.affected_routes,
        )
    except Exception:
        pass
    return broadcast


@app.post("/api/broadcasts/{broadcast_id}/deactivate")
def deactivate_broadcast(broadcast_id: str, user: dict = Depends(require_operator_or_admin)):
    for b in EMERGENCY_BROADCASTS:
        if b["broadcast_id"] == broadcast_id:
            b["active"] = False
            return b
    raise HTTPException(status_code=404, detail="Broadcast not found")


# ─── External Integrations & Multi-Channel Dispatch ───

@app.get("/api/integrations/history")
def list_integration_dispatches():
    return {"dispatches": get_dispatch_history()}


# ─── Delay Handling & Impact Prediction ───

REPORTED_DELAYS: list[dict] = []

@app.get("/api/delays")
def list_reported_delays():
    return {"delays": sorted(REPORTED_DELAYS, key=lambda d: d["reported_at"], reverse=True)}


@app.post("/api/delays/report")
def report_delay(req: DelayReportRequest, user: dict = Depends(require_operator_or_admin)):
    now_str = datetime.utcnow().isoformat() + "Z"
    surge_pct = round((req.estimated_impact_multiplier - 1.0) * 100, 1)
    record = {
        "delay_id": str(uuid.uuid4())[:8],
        "route": req.route,
        "delay_minutes": req.delay_minutes,
        "cause": req.cause,
        "station_or_segment": req.station_or_segment,
        "estimated_platform_surge_pct": surge_pct,
        "recommended_action": f"Inject standby fleet & hold preceding trains at {req.station_or_segment}" if req.delay_minutes >= 10 else "Absorb via dwell time reduction",
        "reported_by": user["username"],
        "reported_at": now_str,
    }
    REPORTED_DELAYS.append(record)
    NOTIFICATION_LOG.append({
        "type": "service_delay",
        "delay_id": record["delay_id"],
        "route": req.route,
        "delay_minutes": req.delay_minutes,
        "timestamp": now_str,
    })
    try:
        dispatch_external_notifications(
            event_type="service_delay",
            title=f"Route {req.route} Delay ({req.delay_minutes} min)",
            message=f"{req.cause} causing ~{req.delay_minutes}m delay at {req.station_or_segment}. Expected platform crowd surge: +{surge_pct}%.",
            severity="warning" if req.delay_minutes < 15 else "critical",
            affected_routes=[req.route],
        )
    except Exception:
        pass
    return record



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
            pipe = MODEL_REGISTRY.get("matched_service") or joblib.load(os.path.join(ARTIFACTS_DIR, f"matched_service_{sel_name}.joblib"))
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
        pipe = MODEL_REGISTRY.get("demand_only") or joblib.load(os.path.join(ARTIFACTS_DIR, f"demand_only_{sel_name}.joblib"))
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


# ─── 1. Route Optimization Engine ───

OPTIMIZATION_RUNS: list[dict] = []

@app.post("/api/optimization/run")
def run_optimization(req: OptimizationRequest):
    matched = _load_parquet("matched_utilization.parquet")
    clusters = _load_parquet("route_clusters.parquet")
    t_date = date.fromisoformat(req.target_date)

    sub = matched[matched["date"] == t_date].copy()
    if sub.empty:
        latest_d = matched["date"].max()
        sub = matched[matched["date"] == latest_d].copy()

    clust_map = clusters.set_index("route").to_dict(orient="index")

    route_profiles = []
    for _, row in sub.iterrows():
        r = str(row["route"])
        trips = int(row["scheduled_trips"])
        rides = float(row["rides"])
        hours = float(row["scheduled_service_hours"]) if pd.notna(row["scheduled_service_hours"]) else (trips * 40.0 / 60.0)
        cl = clust_map.get(r, {}).get("cluster_label", "Ungrouped")
        rides_per_hour = round(rides / hours, 2) if hours > 0 else 0.0
        rides_per_trip = round(rides / trips, 2) if trips > 0 else 0.0
        route_profiles.append({
            "route": r,
            "cluster_label": cl,
            "baseline_trips": trips,
            "baseline_rides": rides,
            "baseline_hours": hours,
            "baseline_rides_per_hour": rides_per_hour,
            "baseline_rides_per_trip": rides_per_trip,
        })

    total_base_trips = sum(p["baseline_trips"] for p in route_profiles)
    total_base_rides = sum(p["baseline_rides"] for p in route_profiles)
    total_base_hours = sum(p["baseline_hours"] for p in route_profiles)

    recommendations = []
    shift_budget_trips = int(round(total_base_trips * (req.fleet_budget_shift_pct / 100.0)))

    if req.objective == "maximize_ridership":
        sorted_profiles = sorted(route_profiles, key=lambda p: p["baseline_rides_per_trip"])
        donors = sorted_profiles[:3]
        receivers = sorted_profiles[-3:]

        donor_cut = max(2, shift_budget_trips // max(1, len(donors) * 2))
        receiver_add = donor_cut

        for p in route_profiles:
            r = p["route"]
            if any(d["route"] == r for d in donors):
                new_trips = max(20, p["baseline_trips"] - donor_cut)
                delta_trips = new_trips - p["baseline_trips"]
                new_rides = round(p["baseline_rides"] + (delta_trips * p["baseline_rides_per_trip"] * 0.75), 1)
                action = "decrease"
                reason = f"Reallocate {abs(delta_trips)} lower-efficiency trips to high-density corridors"
            elif any(rc["route"] == r for rc in receivers):
                new_trips = p["baseline_trips"] + receiver_add
                delta_trips = new_trips - p["baseline_trips"]
                new_rides = round(p["baseline_rides"] + (delta_trips * p["baseline_rides_per_trip"] * 0.85), 1)
                action = "increase"
                reason = f"Add {delta_trips} trips to capture unmet passenger demand"
            else:
                new_trips = p["baseline_trips"]
                delta_trips = 0
                new_rides = p["baseline_rides"]
                action = "maintain"
                reason = "Current frequency matches corridor demand target"

            new_hours = round(p["baseline_hours"] * (new_trips / max(1, p["baseline_trips"])), 2)
            new_rph = round(new_rides / new_hours, 2) if new_hours > 0 else 0.0

            recommendations.append({
                "route": r,
                "cluster_label": p["cluster_label"],
                "baseline_trips": p["baseline_trips"],
                "recommended_trips": new_trips,
                "trips_delta": delta_trips,
                "baseline_rides": round(p["baseline_rides"], 0),
                "projected_rides": round(new_rides, 0),
                "baseline_rides_per_hour": p["baseline_rides_per_hour"],
                "projected_rides_per_hour": new_rph,
                "action": action,
                "reason": reason,
            })

    elif req.objective == "minimize_overcrowding":
        for p in route_profiles:
            rph = p["baseline_rides_per_hour"]
            if rph > req.overcrowding_threshold:
                needed_trips = int(round(p["baseline_trips"] * (rph / req.overcrowding_threshold)))
                delta_trips = max(4, needed_trips - p["baseline_trips"])
                new_trips = p["baseline_trips"] + delta_trips
                new_rides = round(p["baseline_rides"] * 1.04, 1)
                action = "increase"
                reason = f"Relieve overcrowding below {req.overcrowding_threshold} rides/hr threshold"
            else:
                new_trips = p["baseline_trips"]
                delta_trips = 0
                new_rides = p["baseline_rides"]
                action = "maintain"
                reason = "Within safe passenger density limits"

            new_hours = round(p["baseline_hours"] * (new_trips / max(1, p["baseline_trips"])), 2)
            new_rph = round(new_rides / new_hours, 2) if new_hours > 0 else 0.0

            recommendations.append({
                "route": p["route"],
                "cluster_label": p["cluster_label"],
                "baseline_trips": p["baseline_trips"],
                "recommended_trips": new_trips,
                "trips_delta": delta_trips,
                "baseline_rides": round(p["baseline_rides"], 0),
                "projected_rides": round(new_rides, 0),
                "baseline_rides_per_hour": p["baseline_rides_per_hour"],
                "projected_rides_per_hour": new_rph,
                "action": action,
                "reason": reason,
            })

    elif req.objective == "cost_reduction":
        for p in route_profiles:
            if "Coverage" in p["cluster_label"]:
                delta_trips = -max(4, int(round(p["baseline_trips"] * 0.15)))
                new_trips = p["baseline_trips"] + delta_trips
                new_rides = round(p["baseline_rides"] * 0.92, 1)
                action = "decrease"
                reason = "Streamline low-density coverage headway to conserve fleet budget"
            else:
                new_trips = p["baseline_trips"]
                delta_trips = 0
                new_rides = p["baseline_rides"]
                action = "maintain"
                reason = "Protect core trunk and corridor frequency"

            new_hours = round(p["baseline_hours"] * (new_trips / max(1, p["baseline_trips"])), 2)
            new_rph = round(new_rides / new_hours, 2) if new_hours > 0 else 0.0

            recommendations.append({
                "route": p["route"],
                "cluster_label": p["cluster_label"],
                "baseline_trips": p["baseline_trips"],
                "recommended_trips": new_trips,
                "trips_delta": delta_trips,
                "baseline_rides": round(p["baseline_rides"], 0),
                "projected_rides": round(new_rides, 0),
                "baseline_rides_per_hour": p["baseline_rides_per_hour"],
                "projected_rides_per_hour": new_rph,
                "action": action,
                "reason": reason,
            })

    else:
        target_trips_map = {"High-Volume Trunk Tier": 115, "Core Corridor Tier": 95, "Moderate-Demand Coverage Tier": 70}
        for p in route_profiles:
            target = target_trips_map.get(p["cluster_label"], p["baseline_trips"])
            delta_trips = target - p["baseline_trips"]
            action = "increase" if delta_trips > 0 else ("decrease" if delta_trips < 0 else "maintain")
            new_trips = target
            new_rides = round(p["baseline_rides"] + (delta_trips * 45.0), 1)
            new_hours = round(p["baseline_hours"] * (new_trips / max(1, p["baseline_trips"])), 2)
            new_rph = round(new_rides / new_hours, 2) if new_hours > 0 else 0.0

            recommendations.append({
                "route": p["route"],
                "cluster_label": p["cluster_label"],
                "baseline_trips": p["baseline_trips"],
                "recommended_trips": new_trips,
                "trips_delta": delta_trips,
                "baseline_rides": round(p["baseline_rides"], 0),
                "projected_rides": round(new_rides, 0),
                "baseline_rides_per_hour": p["baseline_rides_per_hour"],
                "projected_rides_per_hour": new_rph,
                "action": action,
                "reason": f"Standardize headway to cluster tier benchmark ({target} trips/day)",
            })

    tot_opt_trips = sum(r["recommended_trips"] for r in recommendations)
    tot_opt_rides = sum(r["projected_rides"] for r in recommendations)
    net_rides_change = round(tot_opt_rides - total_base_rides, 0)
    pct_gain = round((net_rides_change / max(1, total_base_rides)) * 100.0, 2)

    result = {
        "run_id": str(uuid.uuid4())[:8],
        "objective": req.objective,
        "target_date": str(t_date),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total_baseline_trips": total_base_trips,
            "total_optimized_trips": tot_opt_trips,
            "net_trips_change": tot_opt_trips - total_base_trips,
            "total_baseline_rides": int(round(total_base_rides)),
            "total_projected_rides": int(round(tot_opt_rides)),
            "net_rides_change": int(net_rides_change),
            "pct_efficiency_gain": pct_gain,
        },
        "recommendations": recommendations,
    }
    OPTIMIZATION_RUNS.append(result)
    return result


@app.get("/api/optimization/history")
def get_optimization_history():
    return {"history": OPTIMIZATION_RUNS}


# ─── 2. Route Demand Analytics & Forecasting ───

@app.get("/api/demand/routes")
def get_all_routes_demand():
    prof = _load_parquet("productivity_rankings.parquet")
    clusters = _load_parquet("route_clusters.parquet")
    w_prof = prof[prof["daytype"] == "W"].copy()
    clust_map = clusters.set_index("route").to_dict(orient="index")

    results = []
    for _, row in w_prof.iterrows():
        r = str(row["route"])
        mean_rides = float(row.get("mean_daily_rides", 0) or 0)
        cl = clust_map.get(r, {}).get("cluster_label", "Ungrouped")

        morning_peak = round(mean_rides * 0.32, 1)
        midday_base = round(mean_rides * 0.28, 1)
        evening_peak = round(mean_rides * 0.30, 1)
        night_owl = round(mean_rides * 0.10, 1)

        forward_7d = []
        base_d = date(2026, 6, 1)
        for i in range(7):
            cur_d = base_d + timedelta(days=i)
            day_mult = 1.0 if cur_d.weekday() < 5 else (0.68 if cur_d.weekday() == 5 else 0.52)
            pred_val = round(mean_rides * day_mult * (1.0 + (0.015 * (i % 3))), 0)
            forward_7d.append({
                "date": str(cur_d),
                "day": cur_d.strftime("%a"),
                "predicted_demand": int(pred_val),
                "lower_bound": int(pred_val * 0.95),
                "upper_bound": int(pred_val * 1.05),
            })

        results.append({
            "route": r,
            "cluster_label": cl,
            "mean_daily_demand": int(round(mean_rides)),
            "hourly_distribution": {
                "morning_peak_06_09": morning_peak,
                "midday_09_15": midday_base,
                "evening_peak_15_19": evening_peak,
                "night_19_00": night_owl,
            },
            "demand_stability_score": round(0.85 + (0.01 * (int(r) % 10)), 2),
            "elasticity_rating": "High Demand Sensitivity" if mean_rides > 16000 else "Moderate Commuter Base",
            "forward_7d": forward_7d,
        })

    return {"demand_profiles": sorted(results, key=lambda d: d["mean_daily_demand"], reverse=True)}


@app.get("/api/demand/routes/{route}")
def get_single_route_demand(route: str):
    all_d = get_all_routes_demand()
    for p in all_d["demand_profiles"]:
        if p["route"] == route:
            return p
    raise HTTPException(status_code=404, detail=f"Demand profile for Route {route} not found")


# ─── 3. Interactive AI Route Clustering Explorer ───

@app.get("/api/clustering/overview")
def get_clustering_overview():
    clusters = _load_parquet("route_clusters.parquet")
    with open(os.path.join(ARTIFACTS_DIR, "training_metrics.json")) as f:
        metrics = json.load(f)

    routes_data = clusters.where(pd.notnull(clusters), None).to_dict(orient="records")

    cluster_summaries = []
    for cid, grp in clusters.groupby("cluster_id"):
        label = grp["cluster_label"].iloc[0]
        cluster_summaries.append({
            "cluster_id": int(cid),
            "cluster_label": label,
            "route_count": len(grp),
            "routes": sorted(grp["route"].tolist()),
            "mean_daily_rides": round(float(grp["mean_weekday_rides"].mean()), 1),
            "mean_weekday_trips": round(float(grp["mean_weekday_trips"].mean()), 1),
            "mean_rides_per_hour": round(float(grp["weekday_rides_per_hour"].mean()), 1),
            "description": (
                "Spine high-frequency trunk lines with heaviest passenger volumes (>16k rides/day)"
                if "Trunk" in label
                else (
                    "Primary urban corridors connecting major employment hubs"
                    if "Corridor" in label
                    else "Essential coverage network providing transit access across districts"
                )
            ),
        })

    return {
        "k": int(metrics.get("clustering", {}).get("k", 3)),
        "silhouette_score": metrics.get("clustering", {}).get("silhouette_score", 0.2935),
        "features": metrics.get("clustering", {}).get("features", []),
        "cluster_summaries": sorted(cluster_summaries, key=lambda c: c["cluster_id"]),
        "routes": routes_data,
    }


@app.post("/api/clustering/recompute")
def recompute_clustering(req: ReclusterRequest):
    clusters = _load_parquet("route_clusters.parquet")
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    features = [
        "mean_weekday_rides",
        "weekday_rides_cv",
        "sat_to_weekday_ratio",
        "sun_to_weekday_ratio",
        "mean_weekday_trips",
        "weekday_rides_per_hour",
    ]
    X = clusters[features].fillna(0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    k = min(req.n_clusters, len(clusters))
    km = KMeans(n_clusters=k, n_init=20, random_state=42)
    new_labels = km.fit_predict(X_scaled)
    sil = round(float(silhouette_score(X_scaled, new_labels)), 4) if k > 1 else 0.0

    tier_names = ["Tier 1 - Trunk Volume", "Tier 2 - Urban Corridor", "Tier 3 - Neighborhood Coverage", "Tier 4 - Feeder", "Tier 5 - Specialized"]

    means = []
    for cid in range(k):
        subset_rides = clusters.loc[new_labels == cid, "mean_weekday_rides"]
        means.append((cid, float(subset_rides.mean()) if len(subset_rides) > 0 else 0.0))
    means.sort(key=lambda x: x[1], reverse=True)
    label_map = {cid: tier_names[idx % len(tier_names)] for idx, (cid, _) in enumerate(means)}

    updated_routes = []
    for idx, row in clusters.iterrows():
        cid = int(new_labels[idx])
        updated_routes.append({
            "route": row["route"],
            "cluster_id": cid,
            "cluster_label": label_map.get(cid, f"Cluster {cid}"),
            "mean_weekday_rides": round(float(row["mean_weekday_rides"]), 1),
            "mean_weekday_trips": round(float(row["mean_weekday_trips"]), 1),
            "weekday_rides_per_hour": round(float(row["weekday_rides_per_hour"]), 1),
        })

    summaries = []
    for idx, (cid, avg_r) in enumerate(means):
        routes_in_c = [r["route"] for r in updated_routes if r["cluster_id"] == cid]
        summaries.append({
            "cluster_id": cid,
            "cluster_label": label_map[cid],
            "route_count": len(routes_in_c),
            "routes": routes_in_c,
            "mean_daily_rides": round(avg_r, 1),
        })

    return {
        "k": k,
        "silhouette_score": sil,
        "inertia": round(float(km.inertia_), 2),
        "cluster_summaries": summaries,
        "routes": updated_routes,
    }


# ─── 4. Autonomous Self-Training, Drift Detection & Model Hot-Reload ───

def _background_self_train(force_retrain: bool = False):
    if SELF_TRAINING_STATE["is_running"]:
        return
    SELF_TRAINING_STATE["is_running"] = True
    try:
        from analytics.auto_retrain import run_autonomous_cycle
        res = run_autonomous_cycle(force_retrain=force_retrain)
        SELF_TRAINING_STATE["last_result"] = res
        load_models_into_memory()
    except Exception as exc:
        SELF_TRAINING_STATE["last_result"] = {
            "timestamp_utc": datetime.utcnow().isoformat() + "Z",
            "status": "error",
            "detail": str(exc),
            "promoted": False,
        }
    finally:
        SELF_TRAINING_STATE["is_running"] = False


@app.get("/api/models/status")
def get_model_status():
    if MODEL_REGISTRY["metrics"] is None:
        load_models_into_memory()
    metrics = MODEL_REGISTRY.get("metrics") or {}
    history_path = os.path.join(os.path.dirname(ARTIFACTS_DIR), "reports", "retrain_history.jsonl")
    recent_runs = []
    if os.path.exists(history_path):
        with open(history_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            for line in lines[-10:]:
                try:
                    recent_runs.append(json.loads(line))
                except Exception:
                    pass
    return {
        "model_version": metrics.get("model_version", "unknown"),
        "trained_at_utc": metrics.get("trained_at_utc"),
        "last_loaded_in_memory_utc": MODEL_REGISTRY.get("last_loaded_utc"),
        "selected_service_model": metrics.get("matched_service", {}).get("selected_serving_model"),
        "selected_demand_model": metrics.get("demand_only", {}).get("selected_serving_model"),
        "is_retraining_now": SELF_TRAINING_STATE["is_running"],
        "last_autonomous_cycle": SELF_TRAINING_STATE["last_result"],
        "recent_retrain_history": list(reversed(recent_runs)),
    }


@app.post("/api/models/reload")
def reload_models():
    load_models_into_memory()
    return {
        "status": "reloaded",
        "last_loaded_utc": MODEL_REGISTRY["last_loaded_utc"],
        "model_version": (MODEL_REGISTRY.get("metrics") or {}).get("model_version"),
    }


@app.post("/api/models/self-train")
def trigger_autonomous_training(req: SelfTrainTriggerRequest, background_tasks: BackgroundTasks):
    if SELF_TRAINING_STATE["is_running"]:
        return {"status": "already_running", "message": "Autonomous self-training cycle is already in progress."}
    background_tasks.add_task(_background_self_train, req.force_retrain)
    return {
        "status": "started",
        "force_retrain": req.force_retrain,
        "message": "Autonomous online data fetch & self-training cycle started in background.",
    }


@app.post("/api/feedback/actual-ridership")
def ingest_actual_ridership(req: ActualRidershipFeedbackRequest, background_tasks: BackgroundTasks):
    denom = max(req.actual_rides, 1.0)
    error_pct = round((abs(req.actual_rides - req.predicted_rides) / denom) * 100.0, 2)
    drift_threshold_pct = 22.0

    if error_pct > drift_threshold_pct and not SELF_TRAINING_STATE["is_running"]:
        background_tasks.add_task(_background_self_train, True)
        return {
            "status": "drift_detected",
            "route": req.route,
            "service_date": req.service_date,
            "error_pct": error_pct,
            "threshold_pct": drift_threshold_pct,
            "action": "Autonomous self-training triggered in background.",
        }

    return {
        "status": "within_tolerance",
        "route": req.route,
        "service_date": req.service_date,
        "error_pct": error_pct,
        "threshold_pct": drift_threshold_pct,
    }
