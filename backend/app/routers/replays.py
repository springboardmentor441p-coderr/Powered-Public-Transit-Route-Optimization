"""Replay sessions (spec 9.17.3): POST /api/replays, GET /api/replays/{id}, POST /api/replays/{id}/control.

The backend owns the clock. GET applies any elapsed playback steps and saves them, so a browser refresh retrieves the
same state. Control actions: start, pause, advance (n days), next_week, jump_to_end, select_date (forward only),
set_speed, and reset, which creates a NEW session (the old one is kept for audit, never deleted).
"""
from __future__ import annotations

from datetime import date

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.db import get_write_conn, resolve_version
from backend.replay import sessions
from backend.replay.clock import ClockError, at, control

router = APIRouter(tags=["replay"])


class CreateBody(BaseModel):
    start_date: date | None = Field(None, description="first replay day (default: the first supported day)")
    speed_seconds: float = Field(sessions.DEFAULT_SPEED, description="wall-clock seconds per virtual day while playing")
    reporting_delay_days: int = Field(1, description="only 1 is supported by the frozen model")
    data_version: str | None = None


class ControlBody(BaseModel):
    action: str = Field(..., description="start | pause | advance | next_week | jump_to_end | select_date | "
                                         "set_speed | reset")
    days: int | None = Field(None, description="advance: number of days (default 1)")
    to: date | None = Field(None, description="select_date: the day to move to")
    speed_seconds: float | None = None
    start_date: date | None = Field(None, description="reset: start of the new session (default: the old start)")


def _state(conn: psycopg.Connection, session_id: str) -> dict:
    """Load, apply elapsed playback, save if it moved, make sure today's forecasts are stored, describe."""
    try:
        row, clock = sessions.load(conn, session_id)
    except sessions.SessionNotFound as e:
        raise HTTPException(404, str(e))
    now = at(clock, sessions.now_utc())  # the clock as it stands now (pure)
    if now != clock:
        sessions.save(conn, session_id, now)
        sessions.ensure_forecasts(conn, session_id)
        row, now = sessions.load(conn, session_id)
    return sessions.describe(conn, row, now)


@router.post("/api/replays", status_code=201)
def create_replay(body: CreateBody, conn: psycopg.Connection = Depends(get_write_conn)) -> dict:
    v = resolve_version(conn, body.data_version)
    try:
        sid = sessions.create(conn, v["data_version"], body.start_date, body.reporting_delay_days, body.speed_seconds)
    except ClockError as e:
        raise HTTPException(422, str(e))
    return _state(conn, sid)


@router.get("/api/replays/{session_id}")
def get_replay(session_id: str, conn: psycopg.Connection = Depends(get_write_conn)) -> dict:
    return _state(conn, session_id)


@router.post("/api/replays/{session_id}/control")
def control_replay(session_id: str, body: ControlBody, conn: psycopg.Connection = Depends(get_write_conn)) -> dict:
    try:
        row, clock = sessions.load(conn, session_id)
    except sessions.SessionNotFound as e:
        raise HTTPException(404, str(e))
    if body.action == "reset":  # a clean new session; the old one stays as it was (audit), never deleted
        try:
            sid = sessions.create(conn, row["data_version"], body.start_date or row["start_date"],
                                  row["reporting_delay_days"], float(row["speed_seconds"]), parent=session_id)
        except ClockError as e:
            raise HTTPException(422, str(e))
        return _state(conn, sid)
    try:
        moved = control(clock, body.action, sessions.now_utc(), days=body.days, to=body.to,
                        speed_seconds=body.speed_seconds)
    except ClockError as e:
        raise HTTPException(422, str(e))
    sessions.save(conn, session_id, moved)
    sessions.ensure_forecasts(conn, session_id)
    return _state(conn, session_id)
