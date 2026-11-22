"""Replay sessions in the database (spec 9.14.4, 9.17.2): create, load, save, describe. The clock rules are in clock.py.

A session stores its run (model + data + delay versions), start, virtual date, delay, speed and status. Sessions are
never deleted: a reset creates a NEW session whose parent is the old one, so the audit trail stays intact.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

import psycopg
from psycopg.rows import dict_row

from backend.replay.clock import Clock, new_clock
from backend.replay.forecasting import commit_or_unknown, ensure_run, store_range

DEFAULT_SPEED = 5.0
DELAY_ASSUMPTION = "rides through the previous day are available at the start of each replay day"
DELAY_NOTE = "a retrospective demonstration assumption, not a verified public-feed capability"


class SessionNotFound(LookupError):
    pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _clock(row: dict) -> Clock:
    return Clock(row["start_date"], row["virtual_date"], row["final_date"], row["reporting_delay_days"],
                 float(row["speed_seconds"]), row["status"], row["playing_since"])


def load(conn: psycopg.Connection, session_id: str) -> tuple[dict, Clock]:
    row = conn.cursor(row_factory=dict_row).execute(
        "SELECT * FROM replay_sessions WHERE session_id = %s", (session_id,)).fetchone()
    if row is None:
        raise SessionNotFound(f"replay session {session_id!r} does not exist")
    return row, _clock(row)


def create(conn: psycopg.Connection, data_version: str, start: date | None, delay: int = 1,
           speed_seconds: float = DEFAULT_SPEED, parent: str | None = None) -> str:
    run = ensure_run(conn, data_version, delay=1, code_commit=commit_or_unknown()) if delay == 1 else None
    first, final = (run.first_target, run.last_target) if run else (date.min, date.max)
    clock = new_clock(first, final, start, delay, speed_seconds)  # validates start, delay and speed
    session_id = uuid.uuid4().hex
    conn.execute("""INSERT INTO replay_sessions (session_id, parent_session_id, run_id, data_version, model_version,
                        start_date, virtual_date, final_date, reporting_delay_days, speed_seconds, status, playing_since)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                 (session_id, parent, run.run_id, data_version, run.model_version, clock.start_date, clock.virtual_date,
                  clock.final_date, clock.delay, clock.speed_seconds, clock.status, clock.playing_since))
    ensure_forecasts(conn, session_id)
    return session_id


def save(conn: psycopg.Connection, session_id: str, c: Clock) -> None:
    conn.execute("""UPDATE replay_sessions SET virtual_date = %s, speed_seconds = %s, status = %s, playing_since = %s,
                        updated_at = now() WHERE session_id = %s""",
                 (c.virtual_date, c.speed_seconds, c.status, c.playing_since, session_id))


def ensure_forecasts(conn: psycopg.Connection, session_id: str) -> None:
    """Every day the session can show (up to its current day) has stored forecasts BEFORE it is revealed. The build job
    normally stored them already; this only fills a gap (idempotent, never rewrites)."""
    row, c = load(conn, session_id)
    last = min(c.virtual_date, c.final_date)
    have = conn.execute("""SELECT count(DISTINCT target_date) AS n FROM forecasts
                           WHERE run_id = %s AND target_date BETWEEN %s AND %s""",
                        (row["run_id"], c.start_date, last)).fetchone()
    n = have["n"] if isinstance(have, dict) else have[0]
    if n < (last - c.start_date).days + 1:
        run = ensure_run(conn, row["data_version"], delay=c.delay, code_commit=commit_or_unknown())
        store_range(conn, run, c.start_date, last)


def describe(conn: psycopg.Connection, row: dict, c: Clock) -> dict:
    """What a screen needs to show the session (spec 9.13.1, 9.14.1, 9.16.1)."""
    cur = conn.cursor(row_factory=dict_row)
    run = cur.execute("SELECT * FROM forecast_runs WHERE run_id = %s", (row["run_id"],)).fetchone()
    mv = cur.execute("SELECT manifest FROM model_versions WHERE model_version = %s", (row["model_version"],)).fetchone()
    manifest = mv["manifest"] if isinstance(mv["manifest"], dict) else json.loads(mv["manifest"])
    periods = manifest["periods"]
    return {
        "session_id": row["session_id"], "parent_session_id": row["parent_session_id"],
        "mode": "historical_replay", "mode_label": "Historical replay",
        "status": c.status, "complete": c.is_complete,
        "start_date": c.start_date, "final_date": c.final_date,
        "virtual_date": None if c.is_complete else c.virtual_date,
        "revealed_through": c.revealed_through,
        "days_revealed": max(0, (c.revealed_through - c.start_date).days + 1),
        "days_total": (c.final_date - c.start_date).days + 1,
        "speed_seconds": c.speed_seconds,
        "reporting_delay_days": c.delay,
        "delay_assumption": DELAY_ASSUMPTION, "delay_note": DELAY_NOTE,
        "run": {"run_id": run["run_id"], "data_version": run["data_version"], "model_version": run["model_version"],
                "model_sha256": run["model_sha256"], "issue_time_rule": run["issue_time_rule"],
                "first_target": run["first_target"], "last_target": run["last_target"]},
        "model": {"label": "Random forest, ride history", "trained_through": periods["train"][1],
                  "chosen_on": periods["validation"], "frozen_note": "frozen before June; never retrained in the replay",
                  "retrained_in_replay": False},
    }
