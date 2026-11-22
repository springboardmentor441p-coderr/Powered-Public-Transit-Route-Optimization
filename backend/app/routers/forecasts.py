"""GET /api/forecasts and POST /api/forecasts (spec 9.17.3, 9.17.4): stored predictions and permitted outcomes.

Each forecast carries route, target date, issue time, prediction and units, status (forecast | unavailable, with the
reason), model version and sha256, data version, the latest ride date its inputs could use, the input schedule
snapshot, the reporting-delay policy and the fallback (none). In replay (`?session=`), only forecasts whose day has
been reached are returned, and the target's actual appears only once that day is revealed; the actual is a separate
field, never mixed into the prediction. Without a session (historical analysis) every stored forecast and its
recorded actual may be shown, as the explicit mode switch allows (spec 9.16.3).
"""
from __future__ import annotations

from datetime import date

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.db import REPLAY_CUTOFF_REFUSED, get_conn, get_write_conn, request_cutoff, resolve_version
from backend.app.labels import envelope
from backend.replay.forecasting import BASELINE, UNITS, ensure_run, store_day

router = APIRouter(tags=["forecasts"])
METHOD_LABELS = {"rf_demand": "Predicted rides (random forest, ride history)",
                 "seasonal_mean": "4-week average (for comparison only)"}
NO_RECORD = "no ridership record for this day"
NOT_REVEALED = "not revealed yet: this day's rides become available at the start of the next replay day"
MAX_DAYS_ALL_ROUTES = 7


def _run_row(conn, session_cutoff, data_version: str) -> dict:
    replay = getattr(session_cutoff, "replay", None)
    if replay:
        r = conn.execute("""SELECT r.* FROM replay_sessions s JOIN forecast_runs r ON r.run_id = s.run_id
                            WHERE s.session_id = %s""", (replay["session_id"],)).fetchone()
    else:
        r = conn.execute("""SELECT * FROM forecast_runs WHERE data_version = %s AND reporting_delay_days = 1
                            ORDER BY created_at LIMIT 1""", (data_version,)).fetchone()
    if r is None:
        raise HTTPException(404, "no forecasts are stored for this data version yet (run build_forecasts.py)")
    return r


def _shape(rows: list[dict], run: dict, revealed_through: date | None, replay: dict | None) -> list[dict]:
    out = []
    for r in rows:
        revealed = revealed_through is None or r["target_date"] <= revealed_through
        trips, pred = r["scheduled_trips"], r["prediction"]
        out.append({
            "route": r["route"], "target_date": r["target_date"], "method": r["method"],
            "label": METHOD_LABELS.get(r["method"], r["method"]),
            "issued_at": f"{r['issue_date'].isoformat()}T00:00 (start of the target day)",
            "prediction": pred, "units": UNITS, "status": r["status"], "unavailable_reason": r["withheld_reason"],
            "fallback_reason": None,
            "latest_available_ride_date": r["latest_ride_date"], "input_schedule_snapshot": r["input_snapshot"],
            "scheduled_trips": trips, "scheduled_hours": r["scheduled_hours"],
            "forecast_rides_per_scheduled_trip": None if pred is None or not trips else pred / trips,
            "forecast_rides_per_scheduled_hour": None if pred is None or not r["scheduled_hours"] else
            pred / r["scheduled_hours"],
            "model_version": run["model_version"], "model_sha256": run["model_sha256"],
            "data_version": run["data_version"], "reporting_delay_days": run["reporting_delay_days"],
            "actual": {"rides": r["rides"] if revealed else None, "revealed": revealed,
                       "reason": None if revealed and r["rides"] is not None else (NO_RECORD if revealed else NOT_REVEALED)},
            "session": None if replay is None else {"session_id": replay["session_id"],
                                                    "virtual_date": replay["virtual_date"]},
        })
    return out


@router.get("/api/forecasts")
def get_forecasts(
    route: str | None = Query(None, description="one route (default: all routes)"),
    start: date | None = Query(None), end: date | None = Query(None),
    method: str | None = Query(None, description=f"rf_demand or {BASELINE} (default: both)"),
    cutoff: date | None = Depends(request_cutoff),
    data_version: str | None = None,
    conn: psycopg.Connection = Depends(get_conn),
) -> dict:
    replay = getattr(cutoff, "replay", None)
    if cutoff is not None and replay is None:
        raise HTTPException(422, "forecasts take a replay session, not a cutoff date")
    v = resolve_version(conn, data_version)
    run = _run_row(conn, cutoff, v["data_version"])
    # the newest target day that may be shown: in replay, the current replay day (its forecast is issued at its
    # start); after completion, the final day. Historical analysis: the run's last day.
    if replay:
        newest = replay["virtual_date"] or replay["revealed_through"]
    else:
        newest = run["last_target"]
    a = start or (newest if route is None else run["first_target"])
    b = min(end or newest, newest)
    if a > b:
        raise HTTPException(422, f"no forecast days in {a} .. {b} are visible (the newest visible day is {newest})")
    if route is None and (b - a).days + 1 > MAX_DAYS_ALL_ROUTES:
        raise HTTPException(422, f"all routes: at most {MAX_DAYS_ALL_ROUTES} days per request; choose a route or a "
                                 "shorter range")
    revealed_through = replay["revealed_through"] if replay else None
    rows = conn.execute("""
        SELECT f.*, d.rides FROM forecasts f
        LEFT JOIN daily_ridership d ON d.data_version = %(dv)s AND d.route = f.route AND d.service_date = f.target_date
             AND (%(rt)s::date IS NULL OR d.service_date <= %(rt)s)          -- the actual is read only once revealed
        WHERE f.run_id = %(run)s AND f.target_date BETWEEN %(a)s AND %(b)s
          AND (%(route)s::text IS NULL OR f.route = %(route)s) AND (%(m)s::text IS NULL OR f.method = %(m)s)
        ORDER BY f.target_date, f.route, f.method""",
        {"dv": run["data_version"], "rt": revealed_through, "run": run["run_id"], "a": a, "b": b,
         "route": route, "m": method}).fetchall()
    return envelope(v, {"requested": None, "applied": replay is not None, "permitted_through": revealed_through,
                        **({"source": "replay session", "replay": replay} if replay else {})},
                    mode_label="Historical replay" if replay else "Historical analysis",
                    range={"start": a, "end": b}, run={k: run[k] for k in ("run_id", "model_version", "model_sha256",
                                                                         "issue_time_rule", "reporting_delay_days")},
                    count=len(rows), forecasts=_shape(rows, run, revealed_through, replay))


class ForecastRequest(BaseModel):
    route: str
    target_date: date
    session: str | None = Field(None, description="replay session: the target must not be after its current day")
    cutoff: date | None = Field(None, description="refused: forecasts take their issue context from the session")


@router.post("/api/forecasts")
def post_forecast(body: ForecastRequest, conn: psycopg.Connection = Depends(get_write_conn)) -> dict:
    """Validated request for a route/target/issue context. Issues (stores) the target day's forecasts if they are not
    stored yet, and returns this route's stored forecasts. A retry returns the same stored rows; nothing is rewritten."""
    if body.cutoff is not None:
        raise HTTPException(422, REPLAY_CUTOFF_REFUSED)
    v = resolve_version(conn, None)
    run = ensure_run(conn, v["data_version"])
    if not run.first_target <= body.target_date <= run.last_target:
        raise HTTPException(422, f"forecasts exist for {run.first_target} .. {run.last_target}")
    replay = None
    if body.session:
        from backend.replay.clock import at
        from backend.replay.sessions import SessionNotFound, load, now_utc
        try:
            _, clock = load(conn, body.session)
        except SessionNotFound as e:
            raise HTTPException(404, str(e))
        c = at(clock, now_utc())
        today = c.final_date if c.is_complete else c.virtual_date
        if body.target_date > today:
            raise HTTPException(422, f"{body.target_date} has not been reached in this replay (current day {today}); "
                                     "a forecast is issued at the start of its own day")
        replay = {"session_id": body.session, "virtual_date": None if c.is_complete else c.virtual_date,
                  "revealed_through": c.revealed_through}
    exists = conn.execute("SELECT 1 FROM forecast_targets WHERE data_version = %s AND route = %s AND target_date = %s",
                          (v["data_version"], body.route, body.target_date)).fetchone()
    if not exists:
        raise HTTPException(404, f"route {body.route} has no scheduled service on {body.target_date} in the timetable "
                                 "available before that day")
    stored = store_day(conn, run, body.target_date)
    rt = replay["revealed_through"] if replay else None
    rows = conn.execute("""SELECT f.*, d.rides FROM forecasts f
                           LEFT JOIN daily_ridership d ON d.data_version = %s AND d.route = f.route
                                AND d.service_date = f.target_date AND (%s::date IS NULL OR d.service_date <= %s)
                           WHERE f.run_id = %s AND f.route = %s AND f.target_date = %s ORDER BY f.method""",
                        (v["data_version"], rt, rt, run.run_id, body.route, body.target_date)).fetchall()
    run_row = conn.execute("SELECT * FROM forecast_runs WHERE run_id = %s", (run.run_id,)).fetchone()
    return envelope(v, {"requested": None, "applied": replay is not None, "permitted_through": rt},
                    stored={"newly_stored": stored["inserted"], "already_stored": stored["existing"]},
                    forecasts=_shape(rows, run_row, rt, replay))
