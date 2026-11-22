"""Stage 7: issue and store one day's forecasts, using only what was known at the start of that day.

For target day D (spec 9.14.2, 9.10.4):
  - issue time = the start of D; with the one-day reporting delay the newest usable ride date is D - 1;
  - target rows = the forecast-time schedule for D (forecast_targets: the archive captured strictly before D);
  - history = daily_ridership rows with service_date <= D - delay, filtered IN SQL, so later rides are never read;
  - features = Stage 3's single build_features (the code that built the training rows);
  - model = the frozen served pipeline (rf_demand), file sha256 checked against the model manifest, never retrained;
  - baseline = the 4-week average (seasonal_mean), stored on the same rows for comparison only (not a fallback).
A row missing a required input is stored as `unavailable` with the reason in words: never imputed, never 0.
Forecasts are written once (primary key) and never rewritten: a recomputation that differs from the stored row
is an error (ForecastConflict), not an update.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psycopg
from psycopg.rows import dict_row, tuple_row

from analytics.features.model_features import build_features
from analytics.models.baselines import BASELINE_RULES
from backend.importer.import_data import REPO_ROOT, sha256

BASELINE = "seasonal_mean"
ISSUE_RULE = "issued at the start of the target day; rides through the day before are available (assumed delay)"
UNITS = "rides/day"


class ForecastConflict(RuntimeError):
    """A stored forecast differs from a recomputation: stored forecasts are never rewritten."""


@dataclass(frozen=True)
class Run:
    run_id: str
    data_version: str
    model_version: str
    model_sha256: str
    model_method: str
    pipeline_location: str
    feature_columns: tuple[str, ...]
    prediction_floor: float
    reporting_delay_days: int
    first_target: date
    last_target: date


# ------------------------------------------------------------------ words for withheld reasons
_FIELD_WORDS = {
    "boardings_28d_filled": "rides 28 days earlier (and no 7/14/21-day values to stand in)",
    "scheduled_trips": "scheduled trips",
    "scheduled_hours": "scheduled trip-hours (incomplete trip durations)",
}


def reason_words(excluded_reason: str) -> str:
    """'boardings_1d_ago, boardings_7d_ago' -> 'missing: rides 1 day earlier, rides 7 days earlier'."""
    parts = []
    for f in (x.strip() for x in excluded_reason.split(",")):
        if f in _FIELD_WORDS:
            parts.append(_FIELD_WORDS[f])
        elif f.startswith("boardings_") and f.endswith("d_ago"):
            k = f.split("_")[1].rstrip("d")
            parts.append(f"rides {k} day{'' if k == '1' else 's'} earlier")
        else:
            parts.append(f.replace("_", " "))
    return "missing: " + ", ".join(parts)


# ------------------------------------------------------------------ run and model
def run_id_for(data_version: str, model_version: str, model_sha: str, delay: int) -> str:
    key = json.dumps([data_version, model_version, model_sha, delay, BASELINE], separators=(",", ":"))
    return "run_" + hashlib.sha256(key.encode()).hexdigest()[:16]


def ensure_run(conn: psycopg.Connection, data_version: str, delay: int = 1, code_commit: str = "unknown") -> Run:
    """The forecast run for this data version, frozen model and delay (created once; same id every time)."""
    if delay != 1:
        raise ValueError("the frozen model was built for a one-day reporting delay; another delay needs rebuilt "
                         "features and a newly evaluated model")
    cur = conn.cursor(row_factory=dict_row)
    mv = cur.execute("""SELECT model_version, selected_method, pipeline_location, pipeline_sha256, manifest
                        FROM model_versions ORDER BY frozen_at DESC LIMIT 1""").fetchone()
    if mv is None:
        raise ValueError("no model version is imported")
    model_version, method, location, model_sha = (mv["model_version"], mv["selected_method"],
                                                  mv["pipeline_location"], mv["pipeline_sha256"])
    manifest = mv["manifest"] if isinstance(mv["manifest"], dict) else json.loads(mv["manifest"])
    span = cur.execute("""SELECT min(target_date) AS first, max(target_date) AS last FROM forecast_targets
                          WHERE data_version = %s AND split = 'test'""", (data_version,)).fetchone()
    first, last = span["first"], span["last"]
    if first is None:
        raise ValueError(f"no forecast targets for {data_version}: run import_stage7.py first")
    run_id = run_id_for(data_version, model_version, model_sha, delay)
    conn.execute("""INSERT INTO forecast_runs (run_id, data_version, model_version, model_sha256, model_method,
                        baseline_method, reporting_delay_days, issue_time_rule, first_target, last_target, code_commit)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (run_id) DO NOTHING""",
                 (run_id, data_version, model_version, model_sha, method, BASELINE, delay, ISSUE_RULE, first, last,
                  code_commit))
    sb = manifest["serving_bundle"]
    return Run(run_id, data_version, model_version, model_sha, method, location, tuple(sb["feature_columns"]),
               float(manifest["settings"]["prediction_floor"]), delay, first, last)


@lru_cache(maxsize=4)
def _pipeline(location: str, expected_sha: str):
    path = REPO_ROOT / location
    actual = sha256(path)
    if actual != expected_sha:
        raise RuntimeError(f"{location}: sha256 {actual[:12]}... differs from the model manifest {expected_sha[:12]}...")
    return joblib.load(path)


def load_pipeline(run: Run):
    return _pipeline(run.pipeline_location, run.model_sha256)


# ------------------------------------------------------------------ one day
def day_inputs(conn: psycopg.Connection, run: Run, target: date) -> tuple[pd.DataFrame, pd.DataFrame, date]:
    """Target rows for `target` and the ride history the forecast may use (filtered in SQL)."""
    latest = target - timedelta(days=run.reporting_delay_days)
    cur = conn.cursor(row_factory=dict_row)
    targets = pd.DataFrame((cur.execute(
        """SELECT route, target_date AS date, scheduled_trips, scheduled_hours, sunday_like_day,
                  forecast_snapshot
           FROM forecast_targets WHERE data_version = %s AND target_date = %s ORDER BY route""",
        (run.data_version, target)).fetchall()),
        columns=["route", "date", "scheduled_trips", "scheduled_hours", "sunday_like_day", "forecast_snapshot"])
    history = pd.DataFrame((cur.execute(
        """SELECT route, service_date AS date, rides FROM daily_ridership
           WHERE data_version = %s AND service_date BETWEEN %s AND %s""",   # nothing after `latest` is ever read
        (run.data_version, target - timedelta(days=28), latest)).fetchall()), columns=["route", "date", "rides"])
    for c in ("scheduled_trips", "scheduled_hours"):
        targets[c] = targets[c].astype("float64")
    targets["sunday_like_day"] = targets["sunday_like_day"].astype("int64")
    history["rides"] = pd.to_numeric(history["rides"]).astype("float64")
    return targets, history, latest


def compute_day(conn: psycopg.Connection, run: Run, target: date) -> pd.DataFrame:
    """Both methods' forecasts for every scheduled route on `target` (not stored)."""
    targets, history, latest = day_inputs(conn, run, target)
    if targets.empty:
        return pd.DataFrame()
    feats = build_features(targets, history, reporting_delay_days=run.reporting_delay_days)
    ok = feats["eligible"].to_numpy(dtype=bool)
    model_pred = np.full(len(feats), np.nan)
    if ok.any():
        model_pred[ok] = np.maximum(load_pipeline(run).predict(feats.loc[ok, list(run.feature_columns)]),
                                    run.prediction_floor)
    base_pred = np.where(ok, feats[BASELINE_RULES[BASELINE]].to_numpy(dtype=float), np.nan)
    out = []
    for method, pred in ((run.model_method, model_pred), (BASELINE, base_pred)):
        f = pd.DataFrame({
            "run_id": run.run_id, "method": method, "issue_date": target, "route": feats["route"].astype(str),
            "target_date": target, "latest_ride_date": latest, "input_snapshot": targets["forecast_snapshot"],
            "scheduled_trips": feats["scheduled_trips"], "scheduled_hours": feats["scheduled_hours"],
            "prediction": pred,
        })
        f["status"] = np.where(ok, "forecast", "unavailable")
        f["withheld_reason"] = [None if e else reason_words(r) for e, r in zip(ok, feats["excluded_reason"])]
        out.append(f)
    return pd.concat(out, ignore_index=True)


COLS = ["run_id", "method", "issue_date", "route", "target_date", "latest_ride_date", "input_snapshot",
        "scheduled_trips", "scheduled_hours", "prediction", "status", "withheld_reason"]


def _none(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else x


def store_day(conn: psycopg.Connection, run: Run, target: date) -> dict:
    """Issue and store `target`'s forecasts once. A retry inserts nothing; a stored row that differs from the
    recomputation raises ForecastConflict (stored forecasts are never rewritten). Returns counts."""
    df = compute_day(conn, run, target)
    if df.empty:
        return {"target": target, "inserted": 0, "existing": 0, "rows": 0}
    rows = [tuple(_none(v) for v in r) for r in df[COLS].itertuples(index=False, name=None)]
    existing = {(r[0], r[1]): r[2:] for r in conn.cursor(row_factory=tuple_row).execute(
        """SELECT method, route, prediction, status, withheld_reason, input_snapshot FROM forecasts
           WHERE run_id = %s AND issue_date = %s AND target_date = %s""", (run.run_id, target, target)).fetchall()}
    for r in rows:
        prev = existing.get((r[1], r[3]))
        if prev is not None and (prev[0], prev[1], prev[2], prev[3]) != (r[9], r[10], r[11], r[6]):
            raise ForecastConflict(f"{r[1]} route {r[3]} on {target}: stored {prev[:2]} differs from recomputed "
                                   f"{(r[9], r[10])}; a stored forecast is never rewritten")
    new = [r for r in rows if (r[1], r[3]) not in existing]
    if new:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.executemany(f"""INSERT INTO forecasts ({", ".join(COLS)})
                                    VALUES ({", ".join(["%s"] * len(COLS))})
                                    ON CONFLICT (run_id, method, issue_date, route, target_date) DO NOTHING""", new)
    return {"target": target, "inserted": len(new), "existing": len(rows) - len(new), "rows": len(rows)}


def store_range(conn: psycopg.Connection, run: Run, first: date, last: date) -> list[dict]:
    out, d = [], first
    while d <= last:
        out.append(store_day(conn, run, d))
        d += timedelta(days=1)
    return out


def run_hash(conn: psycopg.Connection, run_id: str, through: date | None = None) -> str:
    """sha256 over every stored forecast of the run (sorted; predictions as exact float hex), optionally up to a
    target date. Two builds of the same run must give the same hash."""
    rows = conn.cursor(row_factory=tuple_row).execute("""SELECT method, route, target_date, issue_date, latest_ride_date, input_snapshot, status,
                                  withheld_reason, prediction
                           FROM forecasts WHERE run_id = %s AND (%s::date IS NULL OR target_date <= %s)
                           ORDER BY method, target_date, route""", (run_id, through, through)).fetchall()
    h = hashlib.sha256()
    for r in rows:
        vals = list(r)
        p = vals[-1]
        vals[-1] = "None" if p is None else float(p).hex()
        h.update(("|".join(map(str, vals)) + "\n").encode())
    return h.hexdigest()


def commit_or_unknown() -> str:
    try:
        from analytics.reconstruction.build_stage2 import git_commit
        return git_commit()
    except Exception:  # noqa: BLE001 - provenance only
        return "unknown"


def repo_path(p: str) -> Path:
    return REPO_ROOT / p
