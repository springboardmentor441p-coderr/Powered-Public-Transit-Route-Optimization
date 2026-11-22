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

import pandas as pd
import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.db import REPLAY_CUTOFF_REFUSED, get_conn, get_write_conn, request_cutoff, resolve_version
from backend.app.labels import envelope
from backend.app.routers.rankings import REFERENCE_GATE
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


REVIEW_MEANING = ("Predicted rides alongside planned trips and trip-hours for the replay day: a candidate for planner "
                  "inspection, not a measure of route quality")
MISSES_MEANING = "routes whose stored forecasts missed the revealed rides most, on average, so far in this replay"


def _rank_desc(values: pd.Series) -> pd.Series:
    """Descending rank with ties sharing the lowest rank (the same rule as the other rankings)."""
    return values.rank(method="min", ascending=False).astype("Int64")


@router.get("/api/forecasts/review")
def forecast_review(cutoff: date | None = Depends(request_cutoff), data_version: str | None = None,
                    conn: psycopg.Connection = Depends(get_conn)) -> dict:
    """Replay only: everything is computed from stored forecasts and REVEALED rides (service_date <= the session's
    'revealed through' date, in SQL)."""
    replay = getattr(cutoff, "replay", None)
    if replay is None:
        raise HTTPException(422, "the forecast review needs a replay session (?session=...)")
    v = resolve_version(conn, data_version)
    run = _run_row(conn, cutoff, v["data_version"])
    rt, today = replay["revealed_through"], replay["virtual_date"]
    start = conn.execute("SELECT start_date FROM replay_sessions WHERE session_id = %s",
                         (replay["session_id"],)).fetchone()["start_date"]
    gate = REFERENCE_GATE
    # ---- revealed forecast/actual pairs (both methods side by side), from the session's start to revealed-through
    pairs = pd.DataFrame(conn.execute("""
        SELECT m.route, m.target_date, m.status, m.prediction AS model, b.prediction AS base, d.rides
        FROM forecasts m
        JOIN forecasts b ON b.run_id = m.run_id AND b.route = m.route AND b.target_date = m.target_date
                        AND b.issue_date = m.issue_date AND b.method = %(base)s
        LEFT JOIN daily_ridership d ON d.data_version = %(dv)s AND d.route = m.route AND d.service_date = m.target_date
                                   AND d.service_date <= %(rt)s
        WHERE m.run_id = %(run)s AND m.method = %(model)s AND m.target_date BETWEEN %(a)s AND %(rt)s""",
        {"base": BASELINE, "dv": run["data_version"], "rt": rt, "run": run["run_id"], "model": run["model_method"],
         "a": start}).fetchall(), columns=["route", "target_date", "status", "model", "base", "rides"])
    for c in ("model", "base", "rides"):
        pairs[c] = pd.to_numeric(pairs[c]).astype("float64")
    scored = pairs[pairs["status"].eq("forecast") & pairs["rides"].notna()].copy()
    scored["model_err"] = (scored["rides"] - scored["model"]).abs()
    scored["base_err"] = (scored["rides"] - scored["base"]).abs()

    # ---- running error, day by day (cumulative, same route-days for both methods)
    daily = scored.groupby("target_date").agg(rows=("rides", "size"), actual=("rides", "sum"),
                                              m=("model_err", "sum"), b=("base_err", "sum")).sort_index()
    cum = daily.cumsum()
    running = [{"date": d, "rows_scored": int(r.rows), "day_rows_scored": int(dr.rows), "day_model_mae": float(dr.m / dr.rows),
                "day_baseline_mae": float(dr.b / dr.rows),
                "model_mae": float(r.m / r.rows), "baseline_mae": float(r.b / r.rows),
                "model_wape_percent": float(100 * r.m / r.actual), "baseline_wape_percent": float(100 * r.b / r.actual)}
               for (d, r), (_, dr) in zip(cum.iterrows(), daily.iterrows())]
    days_revealed = (rt - start).days + 1 if rt >= start else 0
    coverage = {"route_days_forecast": int(pairs["status"].eq("forecast").sum()),
                "route_days_unavailable": int(pairs["status"].eq("unavailable").sum()),
                "route_days_without_actual": int((pairs["status"].eq("forecast") & pairs["rides"].isna()).sum()),
                "route_days_scored": int(len(scored)), "days_revealed": max(days_revealed, 0)}

    # ---- yesterday: forecast vs actual per route (the most recently revealed day)
    yday = pairs[pairs["target_date"].eq(rt)].sort_values("route") if days_revealed > 0 else pairs.iloc[0:0]
    yesterday = [{"route": r.route, "status": r.status, "prediction": None if pd.isna(r.model) else float(r.model),
                  "baseline": None if pd.isna(r.base) else float(r.base),
                  "rides": None if pd.isna(r.rides) else float(r.rides),
                  "error": None if pd.isna(r.model) or pd.isna(r.rides) else float(r.rides - r.model)}
                 for r in yday.itertuples(index=False)]

    # ---- the spec's forecast demand/service review, for the replay day (predicted rides vs planned service)
    review_rows = []
    if today is not None:
        tf = pd.DataFrame(conn.execute("""
            SELECT route, status, prediction, withheld_reason, scheduled_trips, scheduled_hours, input_snapshot
            FROM forecasts WHERE run_id = %s AND method = %s AND target_date = %s ORDER BY route""",
            (run["run_id"], run["model_method"], today)).fetchall(),
            columns=["route", "status", "prediction", "withheld_reason", "scheduled_trips", "scheduled_hours",
                     "input_snapshot"])
        for c in ("prediction", "scheduled_trips", "scheduled_hours"):
            tf[c] = pd.to_numeric(tf[c]).astype("float64")
        tf["per_trip"] = tf["prediction"] / tf["scheduled_trips"]
        tf["per_hour"] = tf["prediction"] / tf["scheduled_hours"]
        tf["rank_per_hour"] = _rank_desc(tf["per_hour"].where(tf["per_hour"].notna()))
        tf["rank_per_trip"] = _rank_desc(tf["per_trip"].where(tf["per_trip"].notna()))
        for r in tf.sort_values(["rank_per_hour", "route"], na_position="last").itertuples(index=False):
            review_rows.append({
                "route": r.route, "status": r.status, "predicted_rides": None if pd.isna(r.prediction) else float(r.prediction),
                "scheduled_trips": float(r.scheduled_trips),
                "scheduled_hours": None if pd.isna(r.scheduled_hours) else float(r.scheduled_hours),
                "predicted_rides_per_scheduled_trip": None if pd.isna(r.per_trip) else float(r.per_trip),
                "predicted_rides_per_scheduled_hour": None if pd.isna(r.per_hour) else float(r.per_hour),
                "rank_per_hour": None if pd.isna(r.rank_per_hour) else int(r.rank_per_hour),
                "rank_per_trip": None if pd.isna(r.rank_per_trip) else int(r.rank_per_trip),
                "reason": r.withheld_reason if r.status != "forecast" else (
                    None if not pd.isna(r.per_hour) else "scheduled trip-hours unavailable (incomplete trip durations)"),
                "input_schedule_snapshot": r.input_snapshot})

    # ---- largest misses so far (per route, revealed days only), gated like the other rankings
    per = scored.groupby("route").agg(days=("rides", "size"), model_mae=("model_err", "mean"),
                                      baseline_mae=("base_err", "mean"), actual=("rides", "sum"),
                                      m=("model_err", "sum"))
    routes_seen = sorted(set(pairs["route"]), key=str)
    misses = []
    eligible = per[per["days"] >= gate]
    ranks = _rank_desc(eligible["model_mae"])
    for route in routes_seen:
        p = per.loc[route] if route in per.index else None
        n = 0 if p is None else int(p["days"])
        misses.append({
            "route": route, "scored_days": n,
            "model_mae": None if p is None else float(p["model_mae"]),
            "baseline_mae": None if p is None else float(p["baseline_mae"]),
            "model_wape_percent": None if p is None or p["actual"] <= 0 else float(100 * p["m"] / p["actual"]),
            "rank": int(ranks[route]) if route in ranks.index else None,
            "reason": None if route in ranks.index else f"fewer than {gate} scored days ({n})"})
    misses.sort(key=lambda x: (x["rank"] is None, x["rank"] or 0, -x["scored_days"], x["route"]))

    return envelope(v, {"requested": None, "applied": True, "permitted_through": rt, "source": "replay session",
                        "replay": replay},
                    mode_label="Historical replay", units=UNITS,
                    model={"method": run["model_method"], "label": METHOD_LABELS[run["model_method"]],
                           "model_version": run["model_version"], "model_sha256": run["model_sha256"]},
                    baseline={"method": BASELINE, "label": METHOD_LABELS[BASELINE]},
                    coverage=coverage, running=running, yesterday=yesterday,
                    review={"meaning": REVIEW_MEANING, "date": today, "rows": review_rows,
                            "counts": {"routes": len(review_rows),
                                       "ranked": sum(r["rank_per_hour"] is not None for r in review_rows)}},
                    misses={"meaning": MISSES_MEANING, "gate": gate, "gate_label": f"at least {gate} scored days",
                            "rows": misses, "counts": {"routes": len(misses),
                                                      "ranked": sum(m["rank"] is not None for m in misses)}})


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
