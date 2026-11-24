"""Stage 8: save, read and recompute scenarios. Saved rows are immutable (the database refuses UPDATE/DELETE); an
edit is a new row in the same lineage with version + 1.

Replay visibility: a scenario saved in a replay session records that session's cutoff and replay day. In replay mode
only replay scenarios whose cutoff and replay day are not later than the current session's are listed or returned,
and the computer's save time is left out (it is not a replay date). Historical analysis lists every scenario.
"""
from __future__ import annotations

import json
from datetime import date, datetime

import psycopg
from psycopg.types.json import Jsonb

from backend.app.db import SessionCutoff
from backend.scenarios.engine import ScenarioRefused, _canon, canonical_sha256, result_hash
from backend.scenarios.service import calculate

LIST_COLUMNS = """scenario_id, lineage_id, version, parent_scenario_id, name, origin, mode, session_id, virtual_date,
                  cutoff, data_version, group_version, forecast_run_id, model_version, baseline, inputs, assumptions,
                  result_sha256, created_at"""


class ScenarioConflict(RuntimeError):
    """A save whose id exists with a different result (should be impossible; never overwritten)."""


def _json(o):
    """JSON-safe copy for jsonb: dates as ISO strings, floats exactly as Python writes them (round-trip exact)."""
    return json.loads(json.dumps(o, default=_plain, allow_nan=False))


def _plain(x):
    if isinstance(x, (date, datetime)):
        return x.isoformat()
    if hasattr(x, "item"):  # numpy scalars -> Python numbers
        return x.item()
    raise TypeError(f"not JSON-safe: {type(x).__name__}")


def installed(conn: psycopg.Connection) -> bool:
    row = conn.execute("SELECT to_regclass('public.scenarios') IS NOT NULL AS ok").fetchone()
    return bool(row["ok"] if isinstance(row, dict) else row[0])


def _replay_day(replay: dict) -> date:
    """The current replay day; after completion, the day after the last revealed one."""
    if replay.get("virtual_date"):
        v = replay["virtual_date"]
        return v if isinstance(v, date) else date.fromisoformat(v)
    r = replay["revealed_through"]
    r = r if isinstance(r, date) else date.fromisoformat(r)
    return date.fromordinal(r.toordinal() + 1)


def visible_where(cutoff) -> tuple[str, dict]:
    replay = getattr(cutoff, "replay", None)
    if replay is None:
        return "TRUE", {}
    return ("mode = 'historical_replay' AND cutoff <= %(t)s AND (virtual_date IS NULL OR virtual_date <= %(day)s)",
            {"t": date(cutoff.year, cutoff.month, cutoff.day), "day": _replay_day(replay)})


def shape(row: dict, replay: bool, result: dict | None = None) -> dict:
    out = {k: row[k] for k in ("scenario_id", "lineage_id", "version", "parent_scenario_id", "name", "origin", "mode",
                               "session_id", "virtual_date", "cutoff", "baseline", "inputs", "assumptions",
                               "result_sha256")}
    out["versions"] = {k: row[k] for k in ("data_version", "group_version", "forecast_run_id", "model_version")}
    out["saved"] = True
    out["saved_at"] = None if replay else row["created_at"]  # computer time, never shown as a replay date
    if result is not None:
        out["result"] = result
    return out


def save(conn: psycopg.Connection, v: dict, cutoff, req: dict, name: str, origin: str = "planner",
         revises: str | None = None) -> tuple[dict, bool]:
    """Validate, calculate and store. Returns (row, created). The same save twice returns the stored row."""
    name = (name or "").strip()
    if not 1 <= len(name) <= 80:
        raise ScenarioRefused("give the scenario a name of 1 to 80 characters")
    replay = getattr(cutoff, "replay", None)
    parent = None
    if revises is not None:
        where, p = visible_where(cutoff)
        parent = conn.execute(f"SELECT scenario_id, lineage_id, data_version FROM scenarios WHERE scenario_id = %(id)s "
                              f"AND {where}", {"id": revises, **p}).fetchone()
        if parent is None:
            raise ScenarioRefused(f"scenario {revises} does not exist here, so it cannot be revised")
        if parent["data_version"] != v["data_version"]:
            raise ScenarioRefused("a new version must use the same data version as the scenario it revises")
    calc = calculate(conn, v, cutoff, req)
    mode = "historical_replay" if replay else "historical_analysis"
    session_id = replay["session_id"] if replay else None
    identity = {"name": name, "origin": origin, "mode": mode, "session_id": session_id,
                "virtual_date": calc["virtual_date"], "cutoff": calc["cutoff"], "versions": calc["versions"],
                "baseline": calc["baseline"], "inputs": calc["inputs"],
                "parent": parent["scenario_id"] if parent else None}
    sid = "scn_" + canonical_sha256(identity)[:16]
    existing = conn.execute("SELECT * FROM scenarios WHERE scenario_id = %s", (sid,)).fetchone()
    if existing is not None:
        if existing["result_sha256"].strip() != calc["result_sha256"]:
            raise ScenarioConflict(f"{sid} is stored with a different result; it is never overwritten")
        return existing, False
    if parent:
        lineage = parent["lineage_id"]
        version = conn.execute("SELECT max(version) AS v FROM scenarios WHERE lineage_id = %s",
                               (lineage,)).fetchone()["v"] + 1
    else:
        lineage, version = sid, 1
    vs = calc["versions"]
    row = conn.execute(
        """INSERT INTO scenarios (scenario_id, lineage_id, version, parent_scenario_id, name, origin, mode, session_id,
                                  virtual_date, cutoff, data_version, group_version, forecast_run_id, model_version,
                                  baseline, inputs, assumptions, result, result_sha256)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
        (sid, lineage, version, parent["scenario_id"] if parent else None, name, origin, mode, session_id,
         calc["virtual_date"], calc["cutoff"], vs["data_version"], vs["group_version"], vs["forecast_run_id"],
         vs["model_version"], Jsonb(_json(calc["baseline"])), Jsonb(_json(calc["inputs"])),
         Jsonb(_json(calc["assumptions"])), Jsonb(_json(calc["result"])), calc["result_sha256"])).fetchone()
    return row, True


def stored_request(row: dict) -> dict:
    """The original request, rebuilt from the saved baseline and inputs."""
    b = row["baseline"]
    req = dict(b["request"])
    for k in ("start", "end"):
        if isinstance(req.get(k), str):
            req[k] = date.fromisoformat(req[k])
    return {"baseline": req, "service": row["inputs"]["service"], "demand_stress": row["inputs"]["demand_stress"]}


def recompute(conn: psycopg.Connection, v: dict, row: dict) -> dict:
    """Re-run a saved scenario with its STORED cutoff, replay day and versions; compare the result hashes."""
    cutoff = row["cutoff"]
    if row["mode"] == "historical_replay":
        cutoff = SessionCutoff(row["cutoff"], {"session_id": row["session_id"], "virtual_date": row["virtual_date"],
                                               "revealed_through": row["cutoff"], "mode_label": "Historical replay",
                                               "complete": row["virtual_date"] is None})
    calc = calculate(conn, v, cutoff, stored_request(row), virtual_date=row["virtual_date"])
    stored_from_json = result_hash(row["result"])
    same_versions = calc["versions"] == {k: row[k] for k in ("data_version", "group_version", "forecast_run_id",
                                                             "model_version")}
    return {"stored_sha256": row["result_sha256"].strip(), "stored_json_sha256": stored_from_json,
            "recomputed_sha256": calc["result_sha256"], "same_versions": same_versions,
            "identical": calc["result_sha256"] == row["result_sha256"].strip() == stored_from_json and same_versions,
            "canonical_equal": _canon(_json(calc["result"])) == _canon(row["result"])}
