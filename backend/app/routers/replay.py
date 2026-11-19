"""Historical replay with a virtual clock (2026-10-18 to 2026-10-31).

How one virtual day D works:
1. The clock moves to D. The forecast issue time is 00:00 on D.
2. Lags are limited to boardings dated D - delay_days or earlier.
3. The frozen model forecasts every scheduled route-hour on D. Each row is
   saved once with its issue time, model version, schedule snapshot, the latest
   boardings date it was allowed to use, and a status. Saved rows are never
   overwritten.
4. Recorded boardings for a date are only returned once the clock has passed
   that date by delay_days. The backend applies this rule, not the screen.

The replay runs over October 18-31 because those dates were never used for
training, validation or the one official test run. The Aug-Sep test period is
not replayed, so the test set is not scored again.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.app.data import clean_records
from backend.app.forecasting import (
    ALLOWED_DELAYS,
    REPLAY_END,
    REPLAY_START,
    SCHEDULE_SNAPSHOT,
    forecast_day,
    load_frozen_model,
    model_version_label,
)

router = APIRouter(prefix="/api", tags=["replay"])

MIN_SPEED, MAX_SPEED = 1.0, 60.0


class ReplayCreate(BaseModel):
    start_date: str = Field(default=REPLAY_START)
    delay_days: int = Field(default=1)
    speed_seconds: float = Field(default=5.0, ge=MIN_SPEED, le=MAX_SPEED)


class ReplayControl(BaseModel):
    action: str = Field(..., description="start, pause, advance, reset or speed")
    speed_seconds: float | None = Field(default=None, ge=MIN_SPEED, le=MAX_SPEED)
    start_date: str | None = None
    delay_days: int | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_day(d: str) -> str:
    return (pd.Timestamp(d) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def _validate_start(d: str) -> str:
    try:
        d = pd.Timestamp(d).strftime("%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="start_date must look like YYYY-MM-DD.") from exc
    if not (REPLAY_START <= d <= REPLAY_END):
        raise HTTPException(
            status_code=422,
            detail=f"Replay dates are {REPLAY_START} to {REPLAY_END} (the unseen October check). You asked for {d}.",
        )
    return d


def _validate_delay(v: int) -> int:
    if v not in ALLOWED_DELAYS:
        raise HTTPException(status_code=422, detail=f"delay_days must be one of {list(ALLOWED_DELAYS)}.")
    return v


def _get_session(request: Request, session_id: str) -> dict:
    rows = request.app.state.runtime.query("SELECT * FROM replay_sessions WHERE session_id = ?", (session_id,))
    if not rows:
        raise HTTPException(status_code=404, detail=f"Replay session '{session_id}' not found.")
    return rows[0]


def _issue_forecasts(request: Request, session: dict, target_date: str) -> int:
    """Save forecasts for target_date once. Returns rows inserted (0 if already saved)."""
    rt = request.app.state.runtime
    existing = rt.query(
        "SELECT COUNT(*) AS n FROM replay_forecasts WHERE session_id = ? AND target_date = ?",
        (session["session_id"], target_date),
    )[0]["n"]
    if existing:
        return 0
    store = request.app.state.store
    day = forecast_day(
        store.october_hourly_forecast_vs_actual, store.model_route_features, target_date, int(session["delay_days"])
    )
    saved_at = _now_iso()
    issued_at = f"{target_date}T00:00:00 (virtual)"
    rows = [
        (
            session["session_id"], target_date, str(r.route), int(r.hour), issued_at, saved_at,
            str(r.latest_ridership_date_used), int(session["delay_days"]), session["model_version"],
            session["schedule_snapshot"], float(r.trips_running),
            None if pd.isna(r.trips_starting) else float(r.trips_starting), float(r.service_hours),
            int(r.lags_available_count), float(r.pred_boardings),
            None if pd.isna(r.baseline_boardings) else float(r.baseline_boardings), str(r.status),
        )
        for r in day.itertuples(index=False)
    ]
    return rt.executemany(
        "INSERT OR IGNORE INTO replay_forecasts (session_id, target_date, route, hour, issued_at, saved_at_wall, "
        "latest_ridership_date_used, delay_days, model_version, schedule_snapshot, trips_running, trips_starting, "
        "service_hours, lags_available_count, pred_boardings, baseline_boardings, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _advance_one(request: Request, session: dict) -> dict:
    rt = request.app.state.runtime
    if session["status"] == "completed":
        return session
    nxt = _next_day(session["clock_date"])
    if nxt > session["end_date"]:
        rt.execute(
            "UPDATE replay_sessions SET clock_date = ?, status = 'completed' WHERE session_id = ?",
            (nxt, session["session_id"]),
        )
    else:
        rt.execute("UPDATE replay_sessions SET clock_date = ? WHERE session_id = ?", (nxt, session["session_id"]))
        session = {**session, "clock_date": nxt}
        _issue_forecasts(request, session, nxt)
    return _get_session(request, session["session_id"])


def _tick(request: Request, session: dict) -> dict:
    """Advance a playing session by however many virtual days the wall clock allows."""
    if session["status"] != "playing" or session["last_tick_wall"] is None:
        return session
    now = time.time()
    speed = float(session["speed_seconds"])
    steps = int((now - float(session["last_tick_wall"])) // speed)
    if steps <= 0:
        return session
    for _ in range(steps):
        session = _advance_one(request, session)
        if session["status"] == "completed":
            break
    request.app.state.runtime.execute(
        "UPDATE replay_sessions SET last_tick_wall = ? WHERE session_id = ?",
        (float(session["last_tick_wall"] or now) + steps * speed, session["session_id"]),
    )
    return _get_session(request, session["session_id"])


def _create_session(request: Request, start_date: str, delay_days: int, speed_seconds: float) -> dict:
    store = request.app.state.store
    card = load_frozen_model()["model_card"]
    sid = uuid.uuid4().hex[:12]
    session = {
        "session_id": sid,
        "created_at": _now_iso(),
        "start_date": start_date,
        "end_date": REPLAY_END,
        "clock_date": start_date,
        "delay_days": delay_days,
        "speed_seconds": speed_seconds,
        "status": "paused",
        "last_tick_wall": None,
        "model_version": model_version_label(card),
        "schedule_snapshot": f"GTFS {SCHEDULE_SNAPSHOT} (captured before the first replay issue date)",
        "data_version": str(store.version.get("export_date", "unknown")),
        "replaced_by": None,
    }
    request.app.state.runtime.execute(
        "INSERT INTO replay_sessions (session_id, created_at, start_date, end_date, clock_date, delay_days, "
        "speed_seconds, status, last_tick_wall, model_version, schedule_snapshot, data_version, replaced_by) "
        "VALUES (:session_id, :created_at, :start_date, :end_date, :clock_date, :delay_days, :speed_seconds, "
        ":status, :last_tick_wall, :model_version, :schedule_snapshot, :data_version, :replaced_by)",
        session,
    )
    _issue_forecasts(request, session, start_date)
    return _get_session(request, sid)


def _latest_revealed(session: dict) -> str:
    return (pd.Timestamp(session["clock_date"]) - pd.Timedelta(days=int(session["delay_days"]))).strftime("%Y-%m-%d")


def _wape(pred: pd.Series, actual: pd.Series) -> float | None:
    denom = float(actual.sum())
    if denom <= 0:
        return None
    return round(float(np.abs(pred - actual).sum()) / denom * 100.0, 2)


def _state(request: Request, session: dict, route: str | None) -> dict:
    store = request.app.state.store
    rt = request.app.state.runtime
    sid = session["session_id"]
    latest_revealed = _latest_revealed(session)
    current_day = min(session["clock_date"], session["end_date"])

    fc = pd.DataFrame(
        rt.query(
            "SELECT target_date, route, hour, pred_boardings, baseline_boardings, trips_running, trips_starting, "
            "service_hours, "
            "lags_available_count, status, issued_at, saved_at_wall, latest_ridership_date_used "
            "FROM replay_forecasts WHERE session_id = ?",
            (sid,),
        )
    )
    oc = store.october_hourly_forecast_vs_actual[["route", "date", "hour", "actual_ridership", "threshold_p75"]]
    if fc.empty:
        merged = fc
    else:
        merged = fc.merge(
            oc.rename(columns={"date": "target_date"}), on=["target_date", "route", "hour"], how="left"
        )
        hidden = merged["target_date"] > latest_revealed
        merged.loc[hidden, "actual_ridership"] = np.nan
        merged["revealed"] = ~hidden

    def daily(frame: pd.DataFrame) -> list[dict]:
        if frame.empty:
            return []
        g = (
            frame.groupby("target_date")
            .agg(
                forecast_boardings=("pred_boardings", "sum"),
                baseline_boardings=("baseline_boardings", "sum"),
                actual_boardings=("actual_ridership", lambda s: s.sum(min_count=1)),
                revealed=("revealed", "all"),
                hours=("hour", "count"),
                scheduled_departures=("trips_starting", lambda s: s.sum(min_count=1)),
            )
            .reset_index()
            .rename(columns={"target_date": "date"})
        )
        g["forecast_boardings"] = g["forecast_boardings"].round(1)
        g["baseline_boardings"] = g["baseline_boardings"].round(1)
        g.loc[~g["revealed"], "actual_boardings"] = np.nan
        return clean_records(g.sort_values("date"))

    def scores(frame: pd.DataFrame) -> dict:
        if frame.empty:
            return {"revealed_days": 0, "scored_hours": 0, "model_wape_pct": None, "baseline_wape_pct": None}
        rev = frame[frame["revealed"] & frame["actual_ridership"].notna()]
        both = rev[rev["baseline_boardings"].notna()]
        return {
            "revealed_days": int(rev["target_date"].nunique()),
            "scored_hours": int(len(both)),
            "model_wape_pct": _wape(both["pred_boardings"], both["actual_ridership"]) if len(both) else None,
            "baseline_wape_pct": _wape(both["baseline_boardings"], both["actual_ridership"]) if len(both) else None,
            "unscored_hours_missing_baseline": int(len(rev) - len(both)),
        }

    route_block = None
    if route:
        if route not in store.valid_routes:
            raise HTTPException(status_code=404, detail=f"Route '{route}' not found.")
        rf = merged[merged["route"] == route] if not merged.empty else merged
        today = rf[rf["target_date"] == current_day] if not rf.empty else rf
        last_rev = rf[rf["revealed"]] if not rf.empty else rf
        last_date = last_rev["target_date"].max() if not last_rev.empty else None
        last_rows = last_rev[last_rev["target_date"] == last_date] if last_date else last_rev.iloc[0:0]
        cols = ["hour", "pred_boardings", "baseline_boardings", "trips_running", "trips_starting", "service_hours",
                "lags_available_count", "status", "issued_at", "latest_ridership_date_used"]
        route_block = {
            "route": route,
            "daily": daily(rf),
            "scores": scores(rf),
            "current_day": current_day,
            "current_day_hourly": clean_records(today.sort_values("hour")[cols]) if not today.empty else [],
            "last_revealed_date": last_date,
            "last_revealed_hourly": clean_records(
                last_rows.sort_values("hour")[["hour", "pred_boardings", "baseline_boardings", "actual_ridership", "trips_running"]]
            ) if not last_rows.empty else [],
        }

    status_label = {
        "paused": "Paused",
        "playing": "Playing",
        "completed": f"Completed (reached {session['end_date']})",
    }.get(session["status"], session["status"])

    return {
        "mode": "Historical replay",
        "session": {**session, "status_label": status_label},
        "virtual_date": current_day,
        "completed": session["status"] == "completed",
        "supported_range": {"start": REPLAY_START, "end": REPLAY_END},
        "allowed_delays": list(ALLOWED_DELAYS),
        "information_policy": {
            "issue_time": "00:00 on the virtual date, before the first scheduled trip",
            "horizon": "The same service day, one forecast per scheduled route-hour",
            "delay_days": int(session["delay_days"]),
            "latest_ridership_date_used": (
                pd.Timestamp(current_day) - pd.Timedelta(days=int(session["delay_days"]))
            ).strftime("%Y-%m-%d"),
            "latest_revealed_date": latest_revealed,
            "schedule_snapshot": session["schedule_snapshot"],
            "model_version": session["model_version"],
            "note": (
                "This is a replay of past dates. It is not a live feed. The real MTA hourly file was about "
                "19 days behind when it was downloaded, so a 1-day delay is a demo assumption. Choose 14 or "
                "21 days to see what happens when recent lags are missing."
            ),
        },
        "network_daily": daily(merged),
        "network_scores": scores(merged),
        "forecast_record_count": int(len(fc)),
        "route_detail": route_block,
        "source": (
            "models/final_forecaster.joblib (read-only) · app_data/october_hourly_forecast_vs_actual.parquet "
            "(schedule, calendar, lag values and recorded boardings) · backend/runtime SQLite (saved forecasts)"
        ),
    }


@router.get("/replays")
def list_replays(request: Request, limit: int = Query(default=10, ge=1, le=50)) -> dict:
    rows = request.app.state.runtime.query(
        "SELECT * FROM replay_sessions ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
    )
    return {"rows": rows, "count": len(rows)}


@router.post("/replays")
def create_replay(request: Request, payload: ReplayCreate) -> dict:
    start = _validate_start(payload.start_date)
    delay = _validate_delay(payload.delay_days)
    session = _create_session(request, start, delay, payload.speed_seconds)
    return _state(request, session, None)


@router.get("/replays/{session_id}")
def get_replay(request: Request, session_id: str, route: str | None = Query(default=None)) -> dict:
    session = _tick(request, _get_session(request, session_id))
    return _state(request, session, route)


@router.get("/replays/{session_id}/forecasts")
def get_replay_forecasts(
    request: Request,
    session_id: str,
    route: str | None = Query(default=None),
    target_date: str | None = Query(default=None),
) -> dict:
    session = _tick(request, _get_session(request, session_id))
    sql = "SELECT * FROM replay_forecasts WHERE session_id = ?"
    params: list = [session_id]
    if route:
        sql += " AND route = ?"
        params.append(route)
    if target_date:
        sql += " AND target_date = ?"
        params.append(target_date)
    sql += " ORDER BY target_date, route, hour"
    rows = request.app.state.runtime.query(sql, tuple(params))
    return {
        "session_id": session_id,
        "virtual_date": min(session["clock_date"], session["end_date"]),
        "provenance": "Predicted boardings (experimental)",
        "count": len(rows),
        "rows": rows,
    }


@router.post("/replays/{session_id}/control")
def control_replay(
    request: Request, session_id: str, payload: ReplayControl, route: str | None = Query(default=None)
) -> dict:
    rt = request.app.state.runtime
    session = _tick(request, _get_session(request, session_id))
    action = payload.action.strip().lower()

    if action == "start":
        if session["status"] == "completed":
            raise HTTPException(status_code=409, detail="This replay has finished. Use reset to start again.")
        rt.execute(
            "UPDATE replay_sessions SET status = 'playing', last_tick_wall = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
    elif action == "pause":
        if session["status"] == "playing":
            rt.execute(
                "UPDATE replay_sessions SET status = 'paused', last_tick_wall = NULL WHERE session_id = ?",
                (session_id,),
            )
    elif action == "advance":
        if session["status"] == "completed":
            raise HTTPException(status_code=409, detail="This replay has finished. Use reset to start again.")
        session = _advance_one(request, session)
        if session["status"] == "playing":
            rt.execute("UPDATE replay_sessions SET last_tick_wall = ? WHERE session_id = ?", (time.time(), session_id))
    elif action == "speed":
        if payload.speed_seconds is None:
            raise HTTPException(status_code=422, detail="speed needs speed_seconds (1 to 60).")
        rt.execute(
            "UPDATE replay_sessions SET speed_seconds = ? WHERE session_id = ?", (payload.speed_seconds, session_id)
        )
        if session["status"] == "playing":
            rt.execute("UPDATE replay_sessions SET last_tick_wall = ? WHERE session_id = ?", (time.time(), session_id))
    elif action == "reset":
        start = _validate_start(payload.start_date or session["start_date"])
        delay = _validate_delay(payload.delay_days if payload.delay_days is not None else int(session["delay_days"]))
        new_session = _create_session(request, start, delay, float(session["speed_seconds"]))
        rt.execute(
            "UPDATE replay_sessions SET replaced_by = ?, status = CASE WHEN status = 'playing' THEN 'paused' "
            "ELSE status END WHERE session_id = ?",
            (new_session["session_id"], session_id),
        )
        return _state(request, new_session, route)
    else:
        raise HTTPException(status_code=422, detail="action must be start, pause, advance, reset or speed.")

    return _state(request, _get_session(request, session_id), route)
