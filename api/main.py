"""RouteRanker REST API (FastAPI backend).

    uvicorn api.main:app --reload --port 8000      # docs at http://localhost:8000/docs

All dates/times in requests are IST unless stated; responses include both IST
and the bus network's local time.
"""
from __future__ import annotations

import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402
from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from routeranker import config as C  # noqa: E402
from routeranker.inference import PRESETS, RouteRankerService, ist_to_transit, now_ist  # noqa: E402
from routeranker.optimization import simulate_scenario  # noqa: E402

app = FastAPI(title="RouteRanker API", version="1.0.0",
              description="AI-powered public transit route optimisation - forecasts, rankings, recommendations.")


@lru_cache(maxsize=1)
def svc() -> RouteRankerService:
    """Lazily created singleton RouteRankerService."""
    return RouteRankerService()


def _resolve(date_ist: Optional[str], time_ist: Optional[str]):
    """Turn optional IST date/time strings into (IST datetime, network-local datetime)."""
    n = now_ist()
    d = pd.Timestamp(date_ist).date() if date_ist else n.date()
    t = datetime.strptime(time_ist, "%H:%M").time() if time_ist else n.time()
    dt = datetime.combine(d, t).replace(tzinfo=C.IST)
    return dt, ist_to_transit(dt)


def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe list of dicts (NaN -> null)."""
    return df.replace({float("nan"): None}).to_dict(orient="records")


@app.get("/api/health")
def health():
    """Service status, current IST time and data window."""
    s = svc()
    return {"status": "ok", "now_ist": now_ist().isoformat(), "routes": len(s.routes),
            "data_start": str(s.data_start.date()), "data_end": str(s.data_end.date()),
            "models_built_ist": s.manifest["built_at_ist"]}


@app.get("/api/routes")
def routes(borough: Optional[str] = None, route_type: Optional[str] = None):
    """Route catalogue with segment and KPIs, optionally filtered."""
    ri = svc().route_info
    if borough:
        ri = ri[ri["borough"] == borough]
    if route_type:
        ri = ri[ri["route_type"] == route_type]
    cols = ["route_id", "route_long_name", "borough", "route_type", "cluster_name", "avg_daily_ridership",
            "productivity", "mean_occupancy", "mean_speed_mph", "reliability", "dbscan_outlier"]
    return _records(ri[cols])


@app.get("/api/predict")
def predict(route_id: str, date_ist: Optional[str] = Query(None, description="YYYY-MM-DD (IST)")):
    """24-hour forecast for one route on a date (IST)."""
    s = svc()
    if route_id not in s.routes:
        raise HTTPException(404, f"unknown route {route_id}")
    dt, local = _resolve(date_ist, "12:00")
    f = s.predict_day(local.date(), [route_id])
    cols = ["hour", "ridership", "trips", "occupancy", "productivity", "speed_mph", "avg_wait_min", "pred_class",
            "p_underutilized", "p_balanced", "p_overcrowded"] + (["ridership_actual"] if "ridership_actual" in f else [])
    return {"route_id": route_id, "local_date": str(local.date()), "generated_at_ist": now_ist().isoformat(),
            "hours": _records(f[cols])}


@app.get("/api/best-route")
def best_route(date_ist: Optional[str] = None, time_ist: Optional[str] = Query(None, description="HH:MM IST"),
               window: int = Query(1, ge=0, le=12, description="+/- hours around the time"),
               origin: Optional[str] = None, destination: Optional[str] = None,
               borough: Optional[str] = None, preset: str = "Balanced (default)", validate: bool = True):
    """Best route for a date/time window, with explanation, ranking and back-test validation."""
    s = svc()
    dt, local = _resolve(date_ist, time_ist)
    hours = (max(local.hour - window, 0), min(local.hour + window, 23))
    cand = None
    if origin and destination:
        cand = s.find_routes_between(origin, destination)["route_id"].tolist()
        if len(cand) == 0:
            raise HTTPException(404, "no direct route between these places")
    elif borough:
        cand = s.route_info.loc[s.route_info["borough"] == borough, "route_id"].tolist()
    w = PRESETS.get(preset, C.ScoreWeights())
    rank = s.rank_routes(s.predict_day(local.date()), hours, w, cand)
    if rank.empty:
        raise HTTPException(404, "no service in this window")
    out = {"requested_ist": dt.isoformat(), "network_local": local.isoformat(), "hours_local": hours,
           "generated_at_ist": now_ist().isoformat(), "best_route": rank.iloc[0]["route_id"],
           "why": s.explain(rank, w), "ranking": _records(rank.head(20))}
    if validate:
        out["validation"] = _records(s.validate(rank.iloc[0]["route_id"], local.date(), hours, cand, w).astype(str))
    return out


@app.get("/api/ranking")
def ranking(date_ist: Optional[str] = None, start_hour: int = 6, end_hour: int = 22, top: int = 50):
    """RouteRank league table for a date and hour window."""
    s = svc()
    _, local = _resolve(date_ist, "12:00")
    rank = s.rank_routes(s.predict_day(local.date()), (start_hour, end_hour))
    return {"local_date": str(local.date()), "ranking": _records(rank.head(top))}


@app.get("/api/recommendations")
def recommendations(date_ist: Optional[str] = None, top: int = 50):
    """Optimisation actions and network impact for a date."""
    s = svc()
    _, local = _resolve(date_ist, "12:00")
    _, rec, imp = s.recommendations(local.date())
    return {"local_date": str(local.date()), "impact": imp, "actions": _records(rec.head(top))}


class Scenario(BaseModel):
    """Request body of the scenario simulator."""
    date_ist: Optional[str] = None
    routes: Optional[list[str]] = None
    start_hour: int = Field(6, ge=0, le=23)
    end_hour: int = Field(20, ge=0, le=23)
    demand_change_pct: float = 0
    frequency_multiplier: float = 1.0
    speed_change_pct: float = 0
    capacity: Optional[float] = None


@app.post("/api/simulate")
def simulate(sc: Scenario):
    """Run a what-if scenario and return current vs simulated KPIs."""
    s = svc()
    _, local = _resolve(sc.date_ist, "12:00")
    sim = simulate_scenario(s.predict_day(local.date()), sc.demand_change_pct, sc.frequency_multiplier,
                            sc.speed_change_pct, sc.capacity, sc.routes, (sc.start_hour, sc.end_hour))
    x = sim[sim["in_scenario"] & (sim["trips"] > 0)]
    summ = {k: {"current": float(x[k].mean()), "simulated": float(x[f"{k}_sim"].mean())}
            for k in ("occupancy", "avg_wait_min", "productivity")}
    summ["overcrowded_share"] = {"current": float((x["perf_class"] == "Overcrowded").mean()),
                                 "simulated": float((x["perf_class_sim"] == "Overcrowded").mean())}
    return {"local_date": str(local.date()), "summary": summ, "route_hours": int(len(x))}
