"""Database access for the API: one READ-ONLY connection per request (Stage 6 never writes).

The cutoff rule (one place, used by every endpoint): `permitted_through(version, cutoff)` is the last service date a
response may draw on. Every query filters `service_date <= permitted_through` IN SQL, so nothing after it is ever
read, counted or returned. Without a cutoff it is the version's own ridership cutoff (the same code path).
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date

import pandas as pd
import psycopg
from fastapi import Depends, HTTPException, Query
from psycopg.rows import dict_row

from backend.importer.import_data import REPO_ROOT, read_env

ENV_FILE = REPO_ROOT / "backend" / ".env"
URL_VAR = os.environ.get("ROUTERANKER_URL_VAR", "DATABASE_URL")  # tests override the dependency instead
GROUPS_AFTER_CUTOFF = "route groups were fitted on data after the cutoff, so they are not shown"


def database_url() -> str:
    url = read_env(ENV_FILE).get(URL_VAR) if ENV_FILE.exists() else None
    if not url:
        raise RuntimeError(f"{URL_VAR} is not set in backend/.env")
    return url


def open_conn(url: str) -> psycopg.Connection:
    conn = psycopg.connect(url, autocommit=True, row_factory=dict_row)
    conn.execute("SET default_transaction_read_only = on")  # any INSERT/UPDATE/DELETE fails, even by mistake
    return conn


def get_conn() -> Iterator[psycopg.Connection]:
    """FastAPI dependency."""
    with open_conn(database_url()) as conn:
        yield conn


def open_write_conn(url: str) -> psycopg.Connection:
    """Stage 7: the ONLY writable connection, used by the replay session and forecast endpoints (they write sessions
    and store forecasts). Every other endpoint keeps the read-only connection above."""
    return psycopg.connect(url, autocommit=True, row_factory=dict_row)


def get_write_conn() -> Iterator[psycopg.Connection]:
    """FastAPI dependency for the replay writers."""
    with open_write_conn(database_url()) as conn:
        yield conn


def resolve_version(conn: psycopg.Connection, requested: str | None) -> dict:
    """The requested data version, or the most recently imported one. Unknown -> 404 (never a silent fallback)."""
    row = conn.execute("""SELECT data_version, analysis_start, analysis_end, ridership_cutoff, imported_at,
                                 import_git_commit, built_git_commit
                          FROM dataset_versions WHERE %(v)s::text IS NULL OR data_version = %(v)s
                          ORDER BY imported_at DESC LIMIT 1""", {"v": requested}).fetchone()
    if row is None:
        raise HTTPException(404, f"data_version {requested!r} is not imported" if requested else
                            "no data version is imported yet")
    return row


def permitted_through(version: dict, cutoff: date | None) -> date:
    """Last service date a response may use: the cutoff, never later than the version's own ridership cutoff."""
    return version["ridership_cutoff"] if cutoff is None else min(cutoff, version["ridership_cutoff"])


class SessionCutoff(date):
    """A cutoff that came from a stored replay session (never from the client). It behaves as a plain date in every
    query and comparison; `replay` describes the session for the response's cutoff block."""
    replay: dict

    def __new__(cls, d: date, replay: dict):
        obj = super().__new__(cls, d.year, d.month, d.day)
        obj.replay = replay
        return obj


REPLAY_CUTOFF_REFUSED = ("in replay the cutoff comes from the replay session, not from the request; "
                         "send either session or cutoff, not both")


def request_cutoff(cutoff: date | None = Query(None, description="historical analysis: use only service dates on or "
                                                                 "before this date"),
                   session: str | None = Query(None, description="replay: the session id; the backend takes the "
                                                                 "cutoff from the stored session"),
                   conn: psycopg.Connection = Depends(get_conn)) -> date | None:
    """THE cutoff of every analysis endpoint. Historical analysis: the client's optional cutoff (Stage 6). Replay:
    the stored session's 'revealed through' date, computed on the server from the session row and the current
    time; a client-supplied cutoff alongside a session is refused, so editing the URL cannot reveal later data."""
    if session is None:
        return cutoff
    if cutoff is not None:
        raise HTTPException(422, REPLAY_CUTOFF_REFUSED)
    from backend.replay.clock import at  # local import: the clock module has no database dependency
    from backend.replay.sessions import _clock, now_utc
    if conn.execute("SELECT to_regclass('public.replay_sessions') IS NULL").fetchone()["?column?"]:
        raise HTTPException(404, "replay is not installed in this database")
    row = conn.execute("SELECT * FROM replay_sessions WHERE session_id = %s", (session,)).fetchone()
    if row is None:
        raise HTTPException(404, f"replay session {session!r} does not exist")
    c = at(_clock(row), now_utc())
    return SessionCutoff(c.revealed_through, {
        "session_id": session, "mode_label": "Historical replay", "complete": c.is_complete,
        "virtual_date": None if c.is_complete else c.virtual_date, "revealed_through": c.revealed_through,
        "reporting_delay_days": c.delay})


def cutoff_block(version: dict, cutoff: date | None) -> dict:
    replay = getattr(cutoff, "replay", None)
    block = {"requested": None if replay else cutoff, "applied": cutoff is not None,
             "permitted_through": permitted_through(version, cutoff)}
    if replay:
        block["source"] = "replay session"
        block["replay"] = replay
    return block


def group_version_for(conn: psycopg.Connection, data_version: str, through: date | None = None) -> dict | None:
    """The data version's route groups, or None when they were fitted on data after `through` (a cutoff)."""
    gv = conn.execute("""SELECT group_version, profile_start, profile_end, artifact_version, default_overlap_version
                         FROM group_versions WHERE data_version = %s ORDER BY group_version DESC LIMIT 1""",
                      (data_version,)).fetchone()
    if gv is not None and through is not None and gv["profile_end"] > through:
        return None
    return gv


def permitted_matched(conn: psycopg.Connection, data_version: str, start: date, end: date,
                      through: date) -> pd.DataFrame:
    """Matched route/dates in [start, min(end, through)], in the exact frame Stage 5's profiles.py expects.
    The cutoff is in the WHERE clause: rows after it are never read."""
    rows = conn.execute("""SELECT route, service_date AS date, daytype, rides, scheduled_trips,
                                  scheduled_service_hours, duration_complete
                           FROM matched_utilization
                           WHERE data_version = %(dv)s AND service_date BETWEEN %(a)s AND least(%(b)s, %(t)s)""",
                        {"dv": data_version, "a": start, "b": end, "t": through}).fetchall()
    df = pd.DataFrame(rows, columns=["route", "date", "daytype", "rides", "scheduled_trips",
                                     "scheduled_service_hours", "duration_complete"])
    df["date"] = pd.to_datetime(df["date"])
    df["duration_complete"] = df["duration_complete"].astype("boolean")
    df["scheduled_service_hours"] = df["scheduled_service_hours"].astype(float)
    return df


def permitted_schedule(conn: psycopg.Connection, data_version: str, start: date, end: date,
                       through: date) -> pd.DataFrame:
    """Scheduled route/dates in [start, min(end, through)] (route, date, scheduled_trips); cutoff in SQL."""
    rows = conn.execute("""SELECT route, service_date AS date, scheduled_trips FROM daily_schedule
                           WHERE data_version = %(dv)s AND service_date BETWEEN %(a)s AND least(%(b)s, %(t)s)""",
                        {"dv": data_version, "a": start, "b": end, "t": through}).fetchall()
    df = pd.DataFrame(rows, columns=["route", "date", "scheduled_trips"])
    df["date"] = pd.to_datetime(df["date"])
    return df
