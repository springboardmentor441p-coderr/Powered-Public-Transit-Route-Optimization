"""Stage 8: load a scenario's baseline from the database (cutoff in SQL) and calculate the whole scenario.

`calculate(conn, version, cutoff, request)` is the one function behind both "calculate" and "save", and behind
"recompute" (which passes the STORED cutoff and replay day), so a saved scenario is reproduced by the same code.

Demand bases:
- recorded  (both modes): Stage 5's period profiles through the cutoff; the 20-day ranking gate.
- predicted (replay only): the stored model forecast for the replay day and that day's forecast-time timetable;
  one day, so the minimum-days gate does not apply (gate 1), ties still share a rank.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import psycopg

from backend.app.db import GROUPS_AFTER_CUTOFF, group_version_for, permitted_through
from backend.app.labels import UNITS
from backend.app.routers.rankings import (CFG, PERIOD_LABELS, REFERENCE_GATE, compute_profiles, resolve_period)
from backend.scenarios.engine import (BASIS_LABELS, DAYTYPE_WORDS, LIMITS, ScenarioRefused, _routes_words,
                                      assumption_sentences, compare, day_words, result_hash, validate_inputs)

DAYTYPES = ("W", "A", "U")
PERIOD_WORDS = {"full_matched_window": "the full matched window", "development": "the development period",
                "custom": "the chosen dates"}
NO_TIMETABLE = ("recorded rides have no matching timetable (no verified route match), so schedule-based "
                "scenarios are unavailable")
NO_RIDES_PERIOD = "no recorded rides in this period"
SCHEDULE_NO_RIDES = "scheduled service but no recorded rides in this period"


def route_key(r: str):
    digits = "".join(ch for ch in r if ch.isdigit())
    return (not r.isdigit(), int(digits) if digits else 10 ** 9, r)


def _refuse_late(d: date | None, through: date, what: str) -> None:
    if d is not None and d > through:
        raise ScenarioRefused(f"the {what} {day_words(d)} is after the last available date, {day_words(through)}")


def _selected(conn, dv: str, gv: dict | None, routes: list[str] | None, group_id: int | None) -> tuple[list[str], dict]:
    if (routes is None) == (group_id is None):
        raise ScenarioRefused("choose either routes or one route group for the baseline")
    group = None
    if group_id is not None:
        if gv is None:
            raise ScenarioRefused(f"route groups are unavailable: {GROUPS_AFTER_CUTOFF}")
        rows = conn.execute("SELECT route, group_name FROM group_memberships WHERE group_version = %s AND group_id = %s",
                            (gv["group_version"], group_id)).fetchall()
        if not rows:
            raise ScenarioRefused(f"group {group_id} does not exist in the frozen route groups")
        routes = [r["route"] for r in rows]
        group = {"group_id": group_id, "group_name": rows[0]["group_name"], "group_version": gv["group_version"]}
    routes = [str(r) for r in routes]
    if not routes:
        raise ScenarioRefused("the baseline needs at least one route")
    if len(set(routes)) != len(routes):
        raise ScenarioRefused("the baseline names a route twice")
    if len(routes) > LIMITS["routes"]:
        raise ScenarioRefused(f"at most {LIMITS['routes']} routes per scenario")
    return sorted(routes, key=route_key), group


def _known(conn, dv: str, through: date, routes: list[str]) -> None:
    known = {r["route"] for r in conn.execute(
        """SELECT DISTINCT route FROM daily_ridership WHERE data_version = %(dv)s AND service_date <= %(t)s
                                                       AND route = ANY(%(r)s)
           UNION SELECT DISTINCT route FROM daily_schedule WHERE data_version = %(dv)s AND service_date <= %(t)s
                                                             AND route = ANY(%(r)s)""",
        {"dv": dv, "t": through, "r": routes}).fetchall()}
    unknown = [r for r in routes if r not in known]
    if unknown:
        raise ScenarioRefused(f"{_routes_words(unknown)}: no recorded rides or scheduled service up to "
                              f"{day_words(through)}")


def _recorded(conn, v: dict, through: date, b: dict, selected: list[str]):
    daytype = b.get("daytype")
    if daytype not in DAYTYPES:
        raise ScenarioRefused("choose weekdays, Saturdays or Sundays and holidays")
    _refuse_late(b.get("start"), through, "start date")
    _refuse_late(b.get("end"), through, "end date")
    try:
        name, a, end, b_eff = resolve_period(b.get("period"), b.get("start"), b.get("end"), through)
    except Exception as e:  # HTTPException from the shared period rule -> the same words, as a refusal
        raise ScenarioRefused(getattr(e, "detail", str(e)))
    dv = v["data_version"]
    prof = compute_profiles(conn, dv, name, a, b_eff, through, REFERENCE_GATE)
    cols = ["route", "observed_days", "scheduled_service_days", "incomplete_duration_days", "rides_sum",
            "scheduled_trips_sum", "scheduled_hours_sum"]
    base = (prof[prof["daytype"] == daytype][cols].copy() if prof is not None else pd.DataFrame(columns=cols))
    for c in ("rides_sum", "scheduled_trips_sum", "scheduled_hours_sum"):
        base[c] = pd.to_numeric(base[c], errors="coerce").astype(float)
    base["scheduled_service_days"] = base["scheduled_service_days"].fillna(0).astype(int)
    base["structural_zero"] = (base["observed_days"] == 0) & (base["scheduled_service_days"] == 0)
    base["unavailable_reason"] = None
    missing = [r for r in selected if r not in set(base["route"])]
    if missing:
        rides = {r["route"] for r in conn.execute(
            """SELECT DISTINCT route FROM daily_ridership WHERE data_version = %s AND route = ANY(%s)
               AND service_date BETWEEN %s AND %s""", (dv, missing, a, b_eff)).fetchall()}
        sched = {r["route"] for r in conn.execute(
            """SELECT DISTINCT route FROM daily_schedule WHERE data_version = %s AND route = ANY(%s)
               AND service_date BETWEEN %s AND %s AND scheduled_trips > 0""", (dv, missing, a, b_eff)).fetchall()}
        extra = [{"route": r, "observed_days": 0, "scheduled_service_days": 0, "incomplete_duration_days": 0,
                  "rides_sum": float("nan"), "scheduled_trips_sum": float("nan"), "scheduled_hours_sum": float("nan"),
                  "structural_zero": False,
                  "unavailable_reason": NO_TIMETABLE if r in rides and r not in sched else
                  SCHEDULE_NO_RIDES if r in sched else NO_RIDES_PERIOD} for r in missing]
        base = pd.concat([base, pd.DataFrame(extra)], ignore_index=True)
    day_count = conn.execute("""SELECT count(DISTINCT service_date) AS n FROM daily_ridership WHERE data_version = %s
                                AND daytype = %s AND service_date BETWEEN %s AND %s""",
                             (dv, daytype, a, b_eff)).fetchone()["n"]
    period = {"name": name, "label": PERIOD_LABELS[name], "start": a, "end": b_eff, "clipped_to_cutoff": end > through}
    meta = {"demand": "recorded", "daytype": daytype, "period": period, "days_of_daytype": int(day_count),
            "gate": REFERENCE_GATE, "forecast": None}
    return base.reset_index(drop=True), meta


def _predicted(conn, v: dict, replay: dict | None, selected: list[str], virtual_date: date | None):
    if replay is None:
        raise ScenarioRefused("predicted rides are available only in a replay session")
    vd = virtual_date or replay.get("virtual_date")
    if vd is None:
        raise ScenarioRefused("the replay is complete: there is no replay day left with a stored forecast")
    run = conn.execute("""SELECT r.run_id, r.model_version, r.model_method FROM replay_sessions s
                          JOIN forecast_runs r USING (run_id) WHERE s.session_id = %s""",
                       (replay["session_id"],)).fetchone()
    rows = conn.execute("""SELECT route, prediction, status, withheld_reason, scheduled_trips, scheduled_hours,
                                  latest_ride_date, input_snapshot
                           FROM forecasts WHERE run_id = %s AND method = %s AND issue_date = %s AND target_date = %s""",
                        (run["run_id"], run["model_method"], vd, vd)).fetchall()
    recs = [{"route": r["route"], "observed_days": 1, "scheduled_service_days": 1,
             "incomplete_duration_days": 1 if r["scheduled_hours"] is None else 0,
             "rides_sum": float("nan") if r["prediction"] is None else float(r["prediction"]),
             "scheduled_trips_sum": float(r["scheduled_trips"]),
             "scheduled_hours_sum": float("nan") if r["scheduled_hours"] is None else float(r["scheduled_hours"]),
             "structural_zero": False,
             "unavailable_reason": None if r["prediction"] is not None else
             f"forecast unavailable ({r['withheld_reason']})"} for r in rows]
    have = {r["route"] for r in rows}
    for r in selected:
        if r not in have:  # known route with no scheduled service on the replay day: a structural zero
            recs.append({"route": r, "observed_days": 0, "scheduled_service_days": 0, "incomplete_duration_days": 0,
                         "rides_sum": float("nan"), "scheduled_trips_sum": float("nan"),
                         "scheduled_hours_sum": float("nan"), "structural_zero": True, "unavailable_reason": None})
    latest = max((r["latest_ride_date"] for r in rows), default=None)
    meta = {"demand": "predicted", "daytype": "D", "period": {"name": "replay_day", "label": "The replay day",
                                                             "start": vd, "end": vd, "clipped_to_cutoff": False},
            "days_of_daytype": 1, "gate": 1, "virtual_date": vd,
            "forecast": {"run_id": run["run_id"], "model_version": run["model_version"],
                         "method": run["model_method"], "latest_ride_date": latest}}
    return pd.DataFrame(recs), meta


def calculate(conn: psycopg.Connection, v: dict, cutoff: date | None, req: dict, virtual_date: date | None = None) -> dict:
    """Validate, load the baseline through the cutoff (in SQL) and calculate. `req`: {baseline, service,
    demand_stress}. Returns {baseline, inputs, assumptions, result, versions} with the result's sha256."""
    replay = getattr(cutoff, "replay", None)
    through = permitted_through(v, cutoff)
    inputs = validate_inputs(req.get("service"), req.get("demand_stress"))
    b = dict(req.get("baseline") or {})
    demand = b.get("demand", "recorded")
    if demand not in BASIS_LABELS:
        raise ScenarioRefused("demand is either recorded rides or predicted rides")
    gv = group_version_for(conn, v["data_version"], through)
    selected, group = _selected(conn, v["data_version"], gv, b.get("routes"), b.get("group_id"))
    _known(conn, v["data_version"], through, selected)
    if demand == "recorded":
        base, meta = _recorded(conn, v, through, b, selected)
    else:
        if b.get("period") or b.get("start") or b.get("end") or b.get("daytype"):
            raise ScenarioRefused("predicted rides use the replay day; no period or day type is chosen")
        base, meta = _predicted(conn, v, replay, selected, virtual_date)

    cmp = compare(base, selected, inputs, meta["days_of_daytype"], meta["daytype"], meta["gate"])
    groups = {}
    if gv is not None:
        groups = {r["route"]: r["group_id"] for r in conn.execute(
            "SELECT route, group_id FROM group_memberships WHERE group_version = %s AND route = ANY(%s)",
            (gv["group_version"], selected)).fetchall()}
    for row in cmp["rows"]:
        row["group_id"] = groups.get(row["route"])

    who = (f"the route group “{group['group_name']}” ({len(selected)} routes)" if group
           else _routes_words(selected))
    p = meta["period"]
    if demand == "recorded":
        sentence = (f"Baseline: {who} on {DAYTYPE_WORDS[meta['daytype']]} in {PERIOD_WORDS[p['name']]} "
                    f"({day_words(p['start'])} – {day_words(p['end'])}"
                    f"{', cut off at the last available date' if p['clipped_to_cutoff'] else ''}), "
                    f"from recorded rides and the timetables that applied on the same days.")
        ranking = (f"Re-ranked with the usual rules: a route needs at least {meta['gate']} observed days of this day "
                   f"type, ties share a rank, and routes below that stay unranked with their reason.")
    else:
        latest = meta["forecast"]["latest_ride_date"]
        sentence = (f"Baseline: {who} on the replay day, {day_words(p['start'])}: the model's stored forecast, "
                    f"issued at the start of the day" + (f" from rides through {day_words(latest)}" if latest else "")
                    + ", with that day's timetable.")
        ranking = ("One day only: routes are ranked on that day's predicted rides per scheduled trip and hour, ties "
                   "sharing a rank; the minimum-days rule for period rankings does not apply to a single day.")
    if gv is not None:
        ranking += " Route groups are the frozen version fitted on the development period."
    baseline = {"routes": selected, "group": group, "demand": demand, "demand_label": BASIS_LABELS[demand],
                "daytype": None if demand == "predicted" else meta["daytype"],
                "daytype_label": "the replay day" if demand == "predicted" else DAYTYPE_WORDS[meta["daytype"]],
                "period": p, "days_of_daytype": meta["days_of_daytype"],
                "sentence": sentence, "ranking_sentence": ranking}
    assumptions = assumption_sentences(baseline, inputs, cmp)
    result = {"rows": cmp["rows"], "totals": cmp["totals"], "other_rank_changes": cmp["other_rank_changes"],
              "ranked_routes": cmp["ranked_routes"], "units": UNITS,
              "ranking": {"min_observed_days": meta["gate"], "reference_min_observed_days": REFERENCE_GATE,
                          "ties": CFG["rankings"]["ties"], "direction": CFG["rankings"]["direction"]}}
    versions = {"data_version": v["data_version"], "group_version": gv["group_version"] if gv else None,
                "forecast_run_id": meta["forecast"]["run_id"] if meta["forecast"] else None,
                "model_version": meta["forecast"]["model_version"] if meta["forecast"] else None}
    return {"baseline": baseline, "inputs": inputs, "assumptions": assumptions, "result": result,
            "result_sha256": result_hash(result), "versions": versions, "cutoff": through,
            "virtual_date": meta.get("virtual_date")}
