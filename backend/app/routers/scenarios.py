"""Stage 8: service scenarios (spec 9.15, 9.17.2, 9.17.3).

POST /api/scenarios/calculate        validate and calculate; nothing is saved (read-only connection)
POST /api/scenarios                  validate, calculate and SAVE (201; an identical save returns the stored one, 200)
GET  /api/scenarios                  saved scenarios (in replay: only those saved at or before this session's day)
GET  /api/scenarios/{id}             one saved scenario with its stored result and its other versions
GET  /api/scenarios/{id}/recompute   re-run it with its stored cutoff and versions; are the hashes identical?

Replay: `?session=` gives the cutoff (request_cutoff), so the baseline uses revealed rides only, in SQL; a client
cutoff with a session is refused. A saved scenario keeps its own cutoff for ever, so recomputing it later, on a
later replay day, gives the same result.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.app.db import cutoff_block, get_conn, get_write_conn, request_cutoff, resolve_version
from backend.app.labels import LABELS, envelope
from backend.scenarios.engine import LIMITS, ScenarioRefused
from backend.scenarios.service import calculate
from backend.scenarios.store import (LIST_COLUMNS, ScenarioConflict, installed, recompute, save, shape,
                                     visible_where)

router = APIRouter(tags=["scenarios"])
SPEC_REFERENCE = "spec 9.15"
MODE_NOTE = ("Service scenario: a hypothetical calculation from a saved baseline and the changes and assumptions "
             "listed with it. It is kept apart from recorded rides and from forecast evaluation.")


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")
    how: Literal["percent", "per_day"]
    value: Any = Field(description="a % change, or the new value per day (trips or trip-hours)")


class ServiceLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    routes: list[str] | None = Field(None, description="routes this change applies to (default: every baseline route)")
    trips: Change | None = None
    trip_hours: Change | None = None


class Stress(BaseModel):
    model_config = ConfigDict(extra="forbid")
    percent: Any
    scope: Literal["baseline_routes", "network", "routes"] = "baseline_routes"
    routes: list[str] | None = None


class Baseline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    routes: list[str] | None = None
    group_id: int | None = Field(None, ge=0)
    period: Literal["full_matched_window", "development"] | None = None
    start: date | None = None
    end: date | None = None
    daytype: Literal["W", "A", "U"] | None = None
    demand: Literal["recorded", "predicted"] = "recorded"


class ScenarioBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseline: Baseline
    service: list[ServiceLine] = []
    demand_stress: Stress | None = None


class SaveBody(ScenarioBody):
    name: str
    revises: str | None = Field(None, description="the scenario this is a new version of")


def _req(body: ScenarioBody) -> dict:
    return {"baseline": body.baseline.model_dump(),
            "service": [s.model_dump() for s in body.service],
            "demand_stress": body.demand_stress.model_dump() if body.demand_stress else None}


def _need(conn) -> None:
    if not installed(conn):
        raise HTTPException(404, "scenarios are not installed in this database")


def _is_replay(cutoff) -> bool:
    return getattr(cutoff, "replay", None) is not None


def _info(v, cutoff, **body):
    return envelope(v, cutoff_block(v, cutoff), label=LABELS["scenario"], note=MODE_NOTE,
                    limits=LIMITS, spec_reference=SPEC_REFERENCE, **body)


@router.post("/api/scenarios/calculate")
def calculate_scenario(body: ScenarioBody, cutoff: date | None = Depends(request_cutoff),
                       data_version: str | None = None, conn: psycopg.Connection = Depends(get_conn)) -> dict:
    v = resolve_version(conn, data_version)
    try:
        calc = calculate(conn, v, cutoff, _req(body))
    except ScenarioRefused as e:
        raise HTTPException(422, str(e))
    keep = ("baseline", "inputs", "assumptions", "result", "result_sha256", "versions", "cutoff", "virtual_date")
    return _info(v, cutoff, scenario={**{k: calc[k] for k in keep}, "saved": False})


@router.post("/api/scenarios", status_code=201)
def save_scenario(body: SaveBody, response: Response, cutoff: date | None = Depends(request_cutoff),
                  data_version: str | None = None, conn: psycopg.Connection = Depends(get_write_conn)) -> dict:
    _need(conn)
    v = resolve_version(conn, data_version)
    try:
        row, created = save(conn, v, cutoff, _req(body), body.name, "planner", body.revises)
    except ScenarioRefused as e:
        raise HTTPException(422, str(e))
    except ScenarioConflict as e:
        raise HTTPException(409, str(e))
    if not created:
        response.status_code = 200
    return _info(v, cutoff, created=created, scenario=shape(row, _is_replay(cutoff), row["result"]))


def _visible_row(conn, v, cutoff, scenario_id: str) -> dict:
    where, p = visible_where(cutoff)
    row = conn.execute(f"SELECT * FROM scenarios WHERE scenario_id = %(id)s AND data_version = %(dv)s AND {where}",
                       {"id": scenario_id, "dv": v["data_version"], **p}).fetchone()
    if row is None:
        raise HTTPException(404, f"scenario {scenario_id} is not available here (it does not exist, or it was saved "
                                 f"later in the replay or outside this replay)")
    return row


@router.get("/api/scenarios")
def list_scenarios(cutoff: date | None = Depends(request_cutoff), data_version: str | None = None,
                   conn: psycopg.Connection = Depends(get_conn)) -> dict:
    _need(conn)
    v = resolve_version(conn, data_version)
    where, p = visible_where(cutoff)
    rows = conn.execute(f"SELECT {LIST_COLUMNS} FROM scenarios WHERE data_version = %(dv)s AND {where} "
                        f"ORDER BY created_at DESC, scenario_id", {"dv": v["data_version"], **p}).fetchall()
    return _info(v, cutoff, count=len(rows), scenarios=[shape(r, _is_replay(cutoff)) for r in rows])


@router.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str, cutoff: date | None = Depends(request_cutoff), data_version: str | None = None,
                 conn: psycopg.Connection = Depends(get_conn)) -> dict:
    _need(conn)
    v = resolve_version(conn, data_version)
    row = _visible_row(conn, v, cutoff, scenario_id)
    where, p = visible_where(cutoff)
    versions = conn.execute(f"SELECT scenario_id, version, name FROM scenarios WHERE lineage_id = %(l)s AND {where} "
                            f"ORDER BY version", {"l": row["lineage_id"], **p}).fetchall()
    return _info(v, cutoff, scenario=shape(row, _is_replay(cutoff), row["result"]), lineage=versions)


@router.get("/api/scenarios/{scenario_id}/recompute")
def recompute_scenario(scenario_id: str, cutoff: date | None = Depends(request_cutoff),
                       data_version: str | None = None, conn: psycopg.Connection = Depends(get_conn)) -> dict:
    _need(conn)
    v = resolve_version(conn, data_version)
    row = _visible_row(conn, v, cutoff, scenario_id)
    try:
        check = recompute(conn, v, row)
    except ScenarioRefused as e:
        raise HTTPException(422, f"the saved scenario can no longer be recalculated: {e}")
    return _info(v, cutoff, scenario_id=scenario_id, check=check)
