"""Stage 8 scenario engine (spec 9.15): service arithmetic and explicit demand stress on a saved baseline.

A scenario = a BASELINE (routes or a frozen route group, a period, a day type, a demand basis) + explicit CHANGES
(scheduled trips and/or trip-hours, as a % or a new value per day) + an optional DEMAND STRESS (rides +/- x %).

Rules (spec 9.15.1-9.15.3, sec. 6):
- Demand is held fixed unless the stress line says otherwise. Adding service never adds riders. No elasticity.
- Trip-hours change with trips at the baseline's mean duration per trip (hours x new trips / old trips); a change to
  trip-hours alone keeps the trips and implies a new mean duration, which is stated.
- Ratios are ratios of sums over the same days; a zero or missing denominator gives "unavailable" (never 0).
- A route with no scheduled service on that day type (a structural zero) cannot be scaled by a %: adding service
  needs an explicit number of trips per day, and its ratios stay unknown (no recorded rides on days without service).
- Re-ranking uses Stage 5's own `rank_views` (the same gate, reasons and ties rule as every other ranking).

Pure arithmetic lives in `apply_changes` (no database); `calculate` loads the baseline through the cutoff in SQL.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime

import numpy as np
import pandas as pd

from analytics.groups.profiles import rank_views

DAYTYPE_WORDS = {"W": "weekdays", "A": "Saturdays", "U": "Sundays and holidays"}
BASIS_LABELS = {"recorded": "Recorded rides (held fixed)",
                "predicted": "Predicted rides for the replay day (held fixed)"}
LIMITS = {
    "service_percent": (-100.0, 200.0),   # -100 % = no service (ratios unavailable), +200 % = three times the service
    "trips_per_day": (0.0, 2000.0),
    "hours_per_day": (0.0, 2000.0),
    "stress_percent": (-90.0, 100.0),
    "service_lines": 5,
    "routes": 150,                       # the largest frozen group has 67 routes
}
INTERPRETATION = ("This is conditional planning arithmetic, not a forecast. It does not show reduced crowding, a "
                  "ridership gain or a timetable that could actually be run.")
DURATION_LIMIT = ("Running-time effects (congestion, departure times, direction mix) are not modelled: each changed "
                  "trip is assumed to take the baseline's mean time.")
NO_RIDES_ADDED = "no recorded rides on days without service, so demand there is unknown"
ZERO_SERVICE = "no scheduled service in the scenario, so per-trip and per-hour values are undefined"
HOURS_INCOMPLETE = "scheduled trip-hours unavailable (incomplete trip durations)"
RANK_COLS = {"rides_per_scheduled_trip": "rides_per_trip_rank",
             "rides_per_scheduled_hour": "service_productivity_metric_rank"}


class ScenarioRefused(ValueError):
    """An input the engine will not calculate, with the reason in plain words (the API answers 422)."""


# ---------------------------------------------------------------------------------------------- small helpers
def day_words(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def _n(x: float | None, digits: int = 1) -> str:
    return "unavailable" if x is None else f"{x:,.{digits}f}"


def _pct(p: float) -> str:
    return f"{p:+g} %".replace("-", "−")


def _routes_words(routes: list[str]) -> str:
    if len(routes) == 1:
        return f"route {routes[0]}"
    if len(routes) <= 6:
        return "routes " + ", ".join(routes[:-1]) + " and " + routes[-1]
    return f"{len(routes)} routes"


def _f(x) -> float | None:
    """NaN/NA/None -> None; numpy -> float. Missing stays missing, never 0."""
    if x is None or x is pd.NA:
        return None
    x = float(x)
    return None if math.isnan(x) else x


def factor(percent: float) -> float:
    """(100 + p) / 100: +20 -> 1.2 and -15 -> 0.85 exactly as written (no 1 + p/100 rounding)."""
    return (100.0 + percent) / 100.0


def _canon(o):
    if isinstance(o, float):
        return {"f": o.hex()}  # exact, platform-independent
    if isinstance(o, dict):
        return {str(k): _canon(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_canon(v) for v in o]
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return _canon(float(o))
    return o


def canonical_sha256(obj) -> str:
    return hashlib.sha256(json.dumps(_canon(obj), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# ---------------------------------------------------------------------------------------------- validation
def _check_number(x, lo: float, hi: float, what: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)):
        raise ScenarioRefused(f"{what} must be a number")
    x = float(x)
    if not lo <= x <= hi:
        raise ScenarioRefused(f"{what} must be between {lo:g} and {hi:g} (got {x:g})")
    return x


def _check_change(c: dict | None, measure: str) -> dict | None:
    if c is None:
        return None
    how = c.get("how")
    what = "scheduled trips" if measure == "trips" else "scheduled trip-hours"
    if how == "percent":
        lo, hi = LIMITS["service_percent"]
        return {"how": "percent", "value": _check_number(c.get("value"), lo, hi, f"the change in {what} (%)")}
    if how == "per_day":
        lo, hi = LIMITS["trips_per_day" if measure == "trips" else "hours_per_day"]
        v = c.get("value")
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)) and v < 0:
            raise ScenarioRefused(f"{what} per day cannot be negative (got {float(v):g})")
        return {"how": "per_day", "value": _check_number(v, lo, hi, f"{what} per day")}
    raise ScenarioRefused(f"a change in {what} must be a percentage or a new value per day")


def validate_inputs(service: list[dict] | None, stress: dict | None) -> dict:
    """Shape and range checks that need no data. Returns the normalized inputs (the saved `inputs`)."""
    service = service or []
    if len(service) > LIMITS["service_lines"]:
        raise ScenarioRefused(f"at most {LIMITS['service_lines']} service changes per scenario")
    lines, seen = [], set()
    for i, line in enumerate(service, 1):
        trips, hours = _check_change(line.get("trips"), "trips"), _check_change(line.get("trip_hours"), "hours")
        if trips is None and hours is None:
            raise ScenarioRefused(f"service change {i} changes neither trips nor trip-hours")
        routes = line.get("routes")
        if routes is not None:
            routes = [str(r) for r in routes]
            if not routes:
                raise ScenarioRefused(f"service change {i} names no route")
            if len(set(routes)) != len(routes):
                raise ScenarioRefused(f"service change {i} names a route twice")
        key = tuple(routes) if routes is not None else ("*",)
        overlap = (seen & set(key)) or ("*" in seen) or (key == ("*",) and seen)
        if overlap:
            raise ScenarioRefused("each route can be changed by only one service change")
        seen |= set(key)
        lines.append({"routes": routes, "trips": trips, "trip_hours": hours})
    out_stress = None
    if stress is not None:
        lo, hi = LIMITS["stress_percent"]
        p = _check_number(stress.get("percent"), lo, hi, "the demand assumption (%)")
        scope = stress.get("scope", "baseline_routes")
        if scope not in ("baseline_routes", "network", "routes"):
            raise ScenarioRefused("the demand assumption applies to the baseline routes, chosen routes or the network")
        routes = stress.get("routes")
        if scope == "routes":
            if not routes:
                raise ScenarioRefused("name the routes the demand assumption applies to")
            routes = [str(r) for r in routes]
            if len(set(routes)) != len(routes):
                raise ScenarioRefused("the demand assumption names a route twice")
        elif routes:
            raise ScenarioRefused("routes are given only when the demand assumption applies to chosen routes")
        out_stress = {"percent": p, "scope": scope, "routes": routes if scope == "routes" else None}
    if not lines and out_stress is None:
        raise ScenarioRefused("a scenario needs a service change or a demand assumption")
    return {"service": lines, "demand_stress": out_stress}


# ---------------------------------------------------------------------------------------------- arithmetic
def apply_changes(base: pd.DataFrame, selected: list[str], inputs: dict, day_count: int, daytype_words: str) -> dict:
    """The scenario arithmetic, with no database. `base`: one row per network route for the day type, columns
    route, observed_days, scheduled_service_days, incomplete_duration_days, rides_sum, scheduled_trips_sum,
    scheduled_hours_sum (NaN when incomplete), structural_zero, unavailable_reason. Returns per-route values for the
    baseline and the scenario, plus notes. Raises ScenarioRefused for a change that cannot apply at all."""
    b = base.set_index("route")
    changes: dict[str, dict] = {}
    for i, line in enumerate(inputs["service"], 1):
        routes = line["routes"] if line["routes"] is not None else selected
        outside = [r for r in routes if r not in selected]
        if outside:
            raise ScenarioRefused(f"service change {i}: {_routes_words(outside)} is not in the baseline")
        applicable = []
        for r in routes:
            reason = _why_not(b, r, line, daytype_words)
            if reason is None:
                applicable.append(r)
            changes[r] = {**line, "applies": reason is None, "reason": reason}
        if not applicable:
            reasons = "; ".join(f"route {r}: {changes[r]['reason']}" for r in routes)
            raise ScenarioRefused(f"service change {i} cannot be applied to any of its routes ({reasons})")
        if line["trip_hours"] is not None:
            bad = [r for r in applicable if not b.loc[r, "structural_zero"] and math.isnan(b.loc[r, "scheduled_hours_sum"])]
            if bad:
                raise ScenarioRefused(f"{_routes_words(bad)}: {HOURS_INCOMPLETE}, so trip-hours cannot be changed; "
                                      f"change the trips instead")
    stress = inputs["demand_stress"]
    if stress is None:
        stressed: set[str] = set()
    elif stress["scope"] == "network":
        stressed = set(b.index)
    elif stress["scope"] == "baseline_routes":
        stressed = set(selected)
    else:
        outside = [r for r in stress["routes"] if r not in selected]
        if outside:
            raise ScenarioRefused(f"the demand assumption names {_routes_words(outside)}, not in the baseline")
        stressed = set(stress["routes"])
    s_factor = factor(stress["percent"]) if stress else 1.0

    out = {}
    for r, row in b.iterrows():
        n = int(row["observed_days"])
        R, T, H = _f(row["rides_sum"]), _f(row["scheduled_trips_sum"]), _f(row["scheduled_hours_sum"])
        c = changes.get(r)
        R2, T2, H2, days2, status, note = R, T, H, n, "unchanged", None
        if c is not None and not c["applies"]:
            note = c["reason"]
        elif c is not None and bool(row["structural_zero"]):
            days2 = day_count
            T2 = c["trips"]["value"] * day_count
            H2 = c["trip_hours"]["value"] * day_count if c["trip_hours"] else None
            R2, status = None, "service_added"
            note = NO_RIDES_ADDED if H2 is not None else f"{NO_RIDES_ADDED}; trip-hours need a stated value per day"
        elif c is not None:
            status = "changed"
            if c["trips"] is not None:
                T2 = T * factor(c["trips"]["value"]) if c["trips"]["how"] == "percent" else c["trips"]["value"] * n
            if c["trip_hours"] is not None:
                h = c["trip_hours"]
                H2 = H * factor(h["value"]) if h["how"] == "percent" else h["value"] * n
            elif H is not None:  # trips only: each trip keeps the baseline mean duration
                H2 = H if T2 == T else (H * (T2 / T) if T else None)
        if r in stressed and R is not None and status != "service_added":
            R2 = R * s_factor
            if status == "unchanged":
                status = "demand_only"
        out[r] = {"n": n, "days2": days2, "R": R, "T": T, "H": H, "R2": R2, "T2": T2, "H2": H2,
                  "status": status, "note": note, "stressed": r in stressed and R is not None,
                  "structural_zero": bool(row["structural_zero"]), "daytype_words": daytype_words,
                  "unavailable_reason": row["unavailable_reason"] if isinstance(row["unavailable_reason"], str) else None}
    return {"routes": out, "changes": changes, "stressed": stressed, "stress_factor": s_factor}


def _why_not(b: pd.DataFrame, r: str, line: dict, daytype_words: str) -> str | None:
    """Why a service change cannot apply to route r (None = it applies)."""
    if r not in b.index:
        return "not in the baseline"
    row = b.loc[r]
    if isinstance(row["unavailable_reason"], str):
        return row["unavailable_reason"]
    if bool(row["structural_zero"]):
        if line["trips"] is None or line["trips"]["how"] != "per_day":
            return (f"no scheduled service on {daytype_words}, so a percentage has nothing to scale; "
                    f"give a number of trips per day instead")
        if line["trip_hours"] is not None and line["trip_hours"]["how"] != "per_day":
            return f"no scheduled trip-hours on {daytype_words} to scale; give trip-hours per day instead"
        return None
    if int(row["observed_days"]) == 0:
        return "scheduled service but no recorded rides on these days, so there is no baseline to change"
    return None


def _ratio(num: float | None, den: float | None, zero_reason: str) -> tuple[float | None, str | None]:
    if num is None or den is None:
        return None, None
    if den <= 0:
        return None, zero_reason
    return num / den, None


def rank_frame(values: dict, base: pd.DataFrame, scenario: bool, gate: int, daytype: str) -> pd.DataFrame:
    """Profile-shaped table of one side (baseline or scenario) for Stage 5's rank_views: the baseline's own day
    counts, so ineligible routes keep exactly the reasons /api/rankings gives them."""
    recs = []
    for row in base.to_dict("records"):
        r, v = row["route"], values[row["route"]]
        R, T, H = (v["R2"], v["T2"], v["H2"]) if scenario else (v["R"], v["T"], v["H"])
        added = scenario and v["status"] == "service_added"
        recs.append({"route": r, "daytype": daytype, "observed_days": v["n"],
                     "scheduled_service_days": v["days2"] if added else row["scheduled_service_days"],
                     "incomplete_duration_days": (0 if H is not None else 1) if added
                     else int(row["incomplete_duration_days"]),
                     "rides_sum": np.nan if R is None else R,
                     "scheduled_trips_sum": np.nan if T is None else T,
                     "scheduled_hours_sum": np.nan if H is None else H})
    p = pd.DataFrame(recs)
    p["mean_daily_rides"] = p["rides_sum"] / p["observed_days"].where(p["observed_days"] > 0)
    p["rides_per_scheduled_trip"] = p["rides_sum"] / p["scheduled_trips_sum"].where(p["scheduled_trips_sum"] > 0)
    p["rides_per_scheduled_hour"] = p["rides_sum"] / p["scheduled_hours_sum"].where(p["scheduled_hours_sum"] > 0)
    return rank_views(p, gate).set_index("route")


def _side(v: dict, scenario: bool, ranks: pd.DataFrame, r: str, extra_reason: str | None) -> dict:
    R, T, H = (v["R2"], v["T2"], v["H2"]) if scenario else (v["R"], v["T"], v["H"])
    n = v["days2"] if scenario else v["n"]
    per_day = (lambda x: None if x is None or n == 0 else x / n)
    rpt, rpt_why = _ratio(R, T, ZERO_SERVICE)
    rph, rph_why = _ratio(R, H, ZERO_SERVICE)
    reasons = {}
    base_reason = extra_reason or v["unavailable_reason"]
    if base_reason is None and v["structural_zero"] and not (scenario and v["status"] == "service_added"):
        base_reason = f"no scheduled service on {v['daytype_words']}, so nothing to compare"
    if R is None:
        reasons["rides_per_day"] = base_reason or (NO_RIDES_ADDED if v["status"] == "service_added" else
                                                   "no recorded rides on these days")
    if T is None:
        reasons["trips_per_day"] = base_reason or "no scheduled trips on these days"
    if H is None:
        if scenario and v["status"] == "service_added":
            reasons["hours_per_day"] = "trip-hours need a stated value per day where there was no service"
        elif base_reason:
            reasons["hours_per_day"] = base_reason
        elif T is not None and T > 0:
            reasons["hours_per_day"] = HOURS_INCOMPLETE
        else:
            reasons["hours_per_day"] = "no scheduled trips on these days"
    if rpt is None:
        reasons["rides_per_trip"] = rpt_why or reasons.get("rides_per_day") or reasons.get("trips_per_day")
    if rph is None:
        reasons["rides_per_hour"] = rph_why or reasons.get("rides_per_day") or reasons.get("hours_per_day")
    duration = None if H is None or not T else H / T * 60.0
    out = {"days": n, "rides_per_day": per_day(R), "trips_per_day": per_day(T), "hours_per_day": per_day(H),
           "mean_trip_minutes": duration, "rides_per_scheduled_trip": rpt, "rides_per_scheduled_hour": rph,
           "rides_sum": R, "scheduled_trips_sum": T, "scheduled_hours_sum": H, "reasons": reasons}
    for key, col in RANK_COLS.items():
        rr = ranks.loc[r] if r in ranks.index else None
        out[f"rank_{key}"] = None if rr is None or pd.isna(rr[col]) else int(rr[col])
        out[f"rank_{key}_reason"] = None if rr is None or pd.isna(rr[f"{col}_reason"]) else str(rr[f"{col}_reason"])
    if scenario and v["status"] == "service_added":
        for key in RANK_COLS:
            out[f"rank_{key}_reason"] = NO_RIDES_ADDED
    return out


def _change(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None or a == 0 else (b - a) / a * 100.0


def _totals(values: dict, routes: list[str]) -> dict:
    """Sums over routes where the measure is available on BOTH sides (the same routes in both columns)."""
    out, left_out = {}, {}
    for key, num, den in (("rides_per_scheduled_trip", "R", "T"), ("rides_per_scheduled_hour", "R", "H")):
        use = [r for r in routes if all(values[r][x] is not None for x in (num, den, num + "2", den + "2"))]
        nb, db = sum(values[r][num] for r in use), sum(values[r][den] for r in use)
        ns, ds = sum(values[r][num + "2"] for r in use), sum(values[r][den + "2"] for r in use)
        out[key] = {"baseline": nb / db if use and db > 0 else None, "scenario": ns / ds if use and ds > 0 else None,
                    "routes_included": len(use)}
        out[key]["change_percent"] = _change(out[key]["baseline"], out[key]["scenario"])
        for r in routes:
            if r not in use:
                left_out.setdefault(r, "a value is unavailable on one side")
    for key, x in (("rides_per_day", "R"), ("trips_per_day", "T"), ("hours_per_day", "H")):
        use = [r for r in routes if values[r][x] is not None and values[r][x + "2"] is not None
               and values[r]["n"] > 0 and values[r]["days2"] > 0]
        bsum = sum(values[r][x] / values[r]["n"] for r in use)
        ssum = sum(values[r][x + "2"] / values[r]["days2"] for r in use)
        out[key] = {"baseline": bsum if use else None, "scenario": ssum if use else None, "routes_included": len(use),
                    "change_percent": _change(bsum if use else None, ssum if use else None)}
    out["routes"] = len(routes)
    out["left_out"] = [{"route": r, "reason": why} for r, why in left_out.items()]
    return out


def compare(base: pd.DataFrame, selected: list[str], inputs: dict, day_count: int, daytype: str, gate: int) -> dict:
    """Baseline vs scenario per route and in totals, both sides re-ranked by the same rules."""
    words = DAYTYPE_WORDS.get(daytype, "the replay day")
    applied = apply_changes(base, selected, inputs, day_count, words)
    values = applied["routes"]
    rb = rank_frame(values, base, False, gate, daytype)
    rs = rank_frame(values, base, True, gate, daytype)
    rows = []
    for r in selected:
        v = values[r]
        b = _side(v, False, rb, r, None)
        s = _side(v, True, rs, r, None)
        rows.append({"route": r, "status": v["status"], "note": v["note"], "demand_assumed": v["stressed"],
                     "structural_zero": v["structural_zero"],
                     "baseline": b, "scenario": s,
                     "change_percent": {k: _change(b[k], s[k]) for k in
                                        ("rides_per_day", "trips_per_day", "hours_per_day",
                                         "rides_per_scheduled_trip", "rides_per_scheduled_hour")},
                     "rank_change": {k: None if b[f"rank_{k}"] is None or s[f"rank_{k}"] is None else
                                     b[f"rank_{k}"] - s[f"rank_{k}"] for k in RANK_COLS}})
    others = []
    for r in sorted(set(values) - set(selected)):
        col = RANK_COLS["rides_per_scheduled_hour"]
        a, z = rb.loc[r, col], rs.loc[r, col]
        if not pd.isna(a) and not pd.isna(z) and int(a) != int(z):
            others.append({"route": r, "rank_before": int(a), "rank_after": int(z)})
    ranked = {k: {"baseline": int(rb[c].notna().sum()), "scenario": int(rs[c].notna().sum())}
              for k, c in RANK_COLS.items()}
    return {"rows": rows, "totals": {"selected": _totals(values, selected), "network": _totals(values, list(values))},
            "other_rank_changes": others, "ranked_routes": ranked, "applied": applied}


# ---------------------------------------------------------------------------------------------- sentences
def assumption_sentences(baseline: dict, inputs: dict, cmp: dict) -> list[dict]:
    """Every input and assumption in plain words (saved with the scenario and shown on screen)."""
    out = [{"kind": "baseline", "text": baseline["sentence"]}]
    stress = inputs["demand_stress"]
    noun = "Recorded rides" if baseline["demand"] == "recorded" else "Predicted rides"
    if stress is None:
        out.append({"kind": "demand", "text": f"Demand is held fixed: {noun.lower()} stay as they were, so adding "
                                              f"service does not add riders."})
    else:
        who = {"network": "every route in the network", "baseline_routes": "the baseline routes"}.get(
            stress["scope"]) or _routes_words(stress["routes"])
        verb = "fall" if stress["percent"] < 0 else "rise"
        out.append({"kind": "demand_stress",
                    "text": f"Scenario assumption: rides {verb} by {abs(stress['percent']):g} % on {who}. This is "
                            f"assumed demand, not a prediction; the {noun.lower()} are kept alongside."})
        if stress["scope"] != "network":
            out.append({"kind": "demand", "text": "Every other route keeps its demand."})
    rows = {x["route"]: x for x in cmp["rows"]}
    for i, line in enumerate(inputs["service"], 1):
        routes = line["routes"] if line["routes"] is not None else list(rows)
        parts = []
        for measure, unit in (("trips", "scheduled trips"), ("trip_hours", "scheduled trip-hours")):
            c = line[measure]
            if c is None:
                continue
            parts.append(f"{unit} change by {_pct(c['value'])}" if c["how"] == "percent" else
                         f"{unit} are set to {c['value']:g} per day")
        out.append({"kind": "service", "text": f"Change {i}: on {_routes_words(routes)}, " + " and ".join(parts) + "."})
        if line["trips"] is not None and line["trip_hours"] is None:
            mins = [(r, rows[r]["baseline"]["mean_trip_minutes"]) for r in routes if r in rows
                    and rows[r]["status"] == "changed" and rows[r]["baseline"]["mean_trip_minutes"] is not None]
            if mins:
                shown = ", ".join(f"route {r}: {m:.1f} minutes" for r, m in mins[:4]) + (" …" if len(mins) > 4 else "")
                out.append({"kind": "duration",
                            "text": f"Each trip keeps the baseline's mean duration ({shown}), so trip-hours change "
                                    f"in proportion to trips."})
        elif line["trip_hours"] is not None:
            mins = [(r, rows[r]["scenario"]["mean_trip_minutes"]) for r in routes if r in rows
                    and rows[r]["scenario"]["mean_trip_minutes"] is not None and rows[r]["status"] != "unchanged"]
            if mins:
                shown = ", ".join(f"route {r}: {m:.1f} minutes" for r, m in mins[:4]) + (" …" if len(mins) > 4 else "")
                out.append({"kind": "duration", "text": f"Trip-hours are stated directly, so the implied mean "
                                                        f"duration per trip becomes {shown}."})
        for r in routes:
            row = rows.get(r)
            if row and row["note"]:
                out.append({"kind": "not_applied" if row["status"] == "unchanged" else "note",
                            "text": f"Route {r}: {row['note']}."})
    out.append({"kind": "ranking", "text": baseline["ranking_sentence"]})
    out.append({"kind": "interpretation", "text": INTERPRETATION})
    out.append({"kind": "duration_limit", "text": DURATION_LIMIT})
    return out


def result_hash(result: dict) -> str:
    return canonical_sha256(result)
