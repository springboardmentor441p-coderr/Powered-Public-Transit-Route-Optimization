"""GET /api/rankings: the spec 9.12 named rankings for a period and day type, computed by Stage 5's OWN function
(analytics.groups.profiles.utilization_profiles), so the API and the Stage 5 report can never disagree; plus the
route overlap review (Stage 5 pairs ranked by Jaccard).

Every route in the period is returned: eligible rows with their rank, ineligible rows unranked with their observed
days and reason (spec 9.7.2). Numerator and denominator are returned with each value (9.12 "store ... numerator/
denominator and eligibility reason").

min_days: not given -> the reference gate (20); any explicit value is used as given, and `non_reference_gate` is
true only when the resolved gate differs from the reference.

Cutoff: matched and schedule rows are loaded only up to db.permitted_through, in SQL, then ranked; a period ending
after the cutoff is clipped to it. Only the configuration that applies to this ranking is returned (no period
list), so no configured date after the cutoff appears.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Literal

import pandas as pd
import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from analytics.groups.profiles import schedule_with_daytype, utilization_profiles
from backend.app.db import (GROUPS_AFTER_CUTOFF, cutoff_block, get_conn, group_version_for, permitted_matched,
                            permitted_schedule, permitted_through, resolve_version)
from backend.app.labels import UNITS, envelope
from backend.app.routers.history import STARTS_AFTER_CUTOFF
from backend.importer.import_data import REPO_ROOT

router = APIRouter(tags=["rankings"])
CFG = json.loads((REPO_ROOT / "analytics/config/groups.json").read_text(encoding="utf-8"))
REFERENCE_GATE = int(CFG["gates"]["ranking_min_observed_days"])
CAVEAT = ("A high value may reflect route length, speed and turnover; a low value may reflect coverage obligations "
          "or limited observations. A ranking is a review indicator, not a measure of route quality.")
SPEC_REFERENCE = "spec 9.12"  # shown in "How was this number made?", never in visible text
PART_LABELS = {"rides_sum": "recorded rides", "observed_days": "observed days",
               "scheduled_trips_sum": "scheduled trips", "scheduled_hours_sum": "scheduled trip-hours"}
PERIOD_LABELS = {"full_matched_window": "Full matched window", "development": "Development period", "custom": "Chosen dates"}
METRICS = {  # API name -> Stage 5 ranking column, value, numerator, denominator, label, unit
    "observed_daily_demand": ("observed_daily_demand_rank", "mean_daily_rides", "rides_sum", "observed_days",
                              "Observed daily demand", UNITS["rides"]),
    "rides_per_scheduled_trip": ("rides_per_trip_rank", "rides_per_scheduled_trip", "rides_sum",
                                 "scheduled_trips_sum", "Rides per scheduled trip", UNITS["rides_per_scheduled_trip"]),
    "rides_per_scheduled_hour": ("service_productivity_metric_rank", "rides_per_scheduled_hour", "rides_sum",
                                 "scheduled_hours_sum", "Rides per scheduled hour", UNITS["rides_per_scheduled_hour"]),
}
OVERLAP = "route_overlap_review"
PERIODS = {k: tuple(date.fromisoformat(x) for x in v) for k, v in CFG["periods"]["ranking_periods"].items()}


def _none(x):
    """pandas NA/NaN -> None, numpy scalars -> Python numbers (JSON-safe; missing stays missing, never 0)."""
    if x is None or x is pd.NA or (isinstance(x, float) and x != x):
        return None
    return x.item() if hasattr(x, "item") else x


def gate_label(gate: int) -> str:
    return f"reference gate: {gate}" if gate == REFERENCE_GATE else \
        f"non-reference gate: {gate} (reference: {REFERENCE_GATE})"


def resolve_period(period: str | None, start: date | None, end: date | None,
                   through: date) -> tuple[str, date, date, date]:
    """(name, start, configured/requested end, effective end); a range starting after the cutoff is refused."""
    if period and (start or end):
        raise HTTPException(422, "give either period or start/end, not both")
    if (start is None) != (end is None):
        raise HTTPException(422, "start and end must be given together")
    name = period or ("custom" if start else CFG["periods"]["reference_ranking_period"])
    a, b = (start, end) if start else PERIODS[name]
    if a > b:
        raise HTTPException(422, "start must not be after end")
    if a > through:
        raise HTTPException(422, f"{STARTS_AFTER_CUTOFF} ({a} > {through})")
    return name, a, b, min(b, through)


def compute_profiles(conn: psycopg.Connection, data_version: str, name: str, a: date, b_eff: date, through: date,
                     gate: int, members: set[str] | None = None) -> pd.DataFrame | None:
    """Stage 5's utilization_profiles on the permitted rows (cutoff in SQL). Day types for scheduled-service days
    come from all routes (as in Stage 5); `members` then restricts which routes are ranked."""
    matched = permitted_matched(conn, data_version, a, b_eff, through)
    schedule = schedule_with_daytype(permitted_schedule(conn, data_version, a, b_eff, through), matched)
    if members is not None:
        matched, schedule = matched[matched["route"].isin(members)], schedule[schedule["route"].isin(members)]
    cfg = {**CFG, "gates": {**CFG["gates"], "ranking_min_observed_days": gate}}
    return utilization_profiles(matched, name, str(a), str(b_eff), cfg, schedule) if len(matched) else None


@router.get("/api/rankings")
def rankings(
    metric: Literal["observed_daily_demand", "rides_per_scheduled_trip", "rides_per_scheduled_hour",
                    "route_overlap_review"] = "rides_per_scheduled_hour",
    period: Literal["full_matched_window", "development"] | None = Query(
        None, description="a configured period (default: the reference period); or give start and end"),
    start: date | None = None,
    end: date | None = None,
    daytype: Literal["W", "A", "U"] = "W",
    min_days: int | None = Query(None, ge=1, description=f"ranking gate; not given = the reference gate "
                                                         f"({REFERENCE_GATE})"),
    group_id: int | None = Query(None, ge=0, description="rank only within this route group"),
    geometry_version: str | None = Query(None, description="route_overlap_review only (default: Stage 5's)"),
    cutoff: date | None = Query(None, description="use only service dates on or before this date"),
    data_version: str | None = None,
    conn: psycopg.Connection = Depends(get_conn),
) -> dict:
    v = resolve_version(conn, data_version)
    through = permitted_through(v, cutoff)
    if metric == OVERLAP:
        return _overlap(conn, v, cutoff, through, geometry_version,
                        unused={"period": period, "start": start, "end": end, "group_id": group_id,
                                "min_days": min_days})
    if geometry_version is not None:
        raise HTTPException(422, "geometry_version applies only to route_overlap_review")
    gate = REFERENCE_GATE if min_days is None else min_days
    name, a, b, b_eff = resolve_period(period, start, end, through)  # clipped to the cutoff; never after it

    # ---- optional group: only routes in it are ranked (spec 9.12 "optionally within a similar-route group")
    gv = group_version_for(conn, v["data_version"], through)
    members = None
    if group_id is not None:
        if gv is None:
            raise HTTPException(422, f"group_id is unavailable: {GROUPS_AFTER_CUTOFF}")
        members = {r["route"] for r in conn.execute(
            "SELECT route FROM group_memberships WHERE group_version = %s AND group_id = %s",
            (gv["group_version"], group_id)).fetchall()}
        if not members:
            raise HTTPException(404, f"group {group_id} does not exist in {gv['group_version']}")

    prof = compute_profiles(conn, v["data_version"], name, a, b_eff, through, gate, members)  # Stage 5's own

    rank_col, value_col, num_col, den_col, label, unit = METRICS[metric]
    rows = []
    if prof is not None:
        for rec in prof[prof["daytype"] == daytype].to_dict("records"):
            rows.append({"rank": _none(rec[rank_col]), "route": rec["route"],
                         "eligible": bool(rec[f"{rank_col}_eligible"]), "reason": _none(rec[f"{rank_col}_reason"]),
                         "observed_days": int(rec["observed_days"]),
                         "scheduled_service_days": _none(rec["scheduled_service_days"]),
                         "incomplete_duration_days": int(rec["incomplete_duration_days"]),
                         "numerator": _none(rec[num_col]), "denominator": _none(rec[den_col]),
                         "value": _none(rec[value_col])})
    rows.sort(key=lambda x: (x["rank"] is None, x["rank"] or 0, -x["observed_days"] if x["rank"] is None else 0,
                             x["route"]))
    return envelope(
        v, cutoff_block(v, cutoff),
        metric={"key": metric, "label": label, "unit": unit,
                "meaning": CFG["rankings"]["views"][rank_col]["meaning"], "caveat": CAVEAT,
                "numerator": num_col, "denominator": den_col,
                "numerator_label": PART_LABELS[num_col], "denominator_label": PART_LABELS[den_col],
                "spec_reference": SPEC_REFERENCE},
        period={"name": name, "label": PERIOD_LABELS[name], "start": a, "end": b_eff, "clipped_to_cutoff": b > through},
        daytype=daytype,
        configuration={"min_observed_days": gate, "reference_min_observed_days": REFERENCE_GATE,
                       "non_reference_gate": gate != REFERENCE_GATE, "gate_label": gate_label(gate),
                       "direction": CFG["rankings"]["direction"], "ties": CFG["rankings"]["ties"],
                       "ratio_rule": CFG["rankings"]["ratio_rule"]},
        group={"group_id": group_id, "group_version": gv["group_version"]} if group_id is not None else None,
        counts={"routes": len(rows), "ranked": sum(r["rank"] is not None for r in rows),
                "unranked": sum(r["rank"] is None for r in rows)},
        rows=rows,
    )


def _overlap(conn, v, cutoff, through, geometry_version, unused) -> dict:
    """Stage 5 route_stop_overlap for one geometry version: pairs ranked by Jaccard, ties preserved, each row with
    its 'corridor review only' interpretation. Stop sets come from GTFS alone (no ridership), so the Stage 5
    profile period does not hide them; under a cutoff only archives captured on or before it may be chosen."""
    given = [k for k, x in unused.items() if x is not None]
    if given:
        raise HTTPException(422, f"{', '.join(given)}: not applicable to route_overlap_review")
    gv = group_version_for(conn, v["data_version"])
    if gv is None:
        raise HTTPException(404, "no route overlap product is imported for this data version")
    allowed = [r["snapshot_id"] for r in conn.execute(
        """SELECT snapshot_id FROM gtfs_snapshots WHERE data_version = %s AND captured_date <= %s
           ORDER BY captured_date""", (v["data_version"], through)).fetchall()]
    if not allowed:
        raise HTTPException(422, "no geometry version was captured on or before the cutoff")
    if geometry_version is None:
        geometry_version = gv["default_overlap_version"] if gv["default_overlap_version"] in allowed else allowed[-1]
    elif geometry_version not in allowed:
        raise HTTPException(422, f"geometry version {geometry_version!r} is unknown or captured after the cutoff")
    rows = conn.execute("""
        SELECT o.overlap_review_rank AS rank, o.route_a, o.route_b, o.shared_stop_count, o.route_a_stop_count,
               o.route_b_stop_count, o.jaccard_stop_overlap, o.smaller_route_stop_overlap,
               ca.exclusive_stop_fraction AS route_a_exclusive_fraction,
               cb.exclusive_stop_fraction AS route_b_exclusive_fraction, o.interpretation
        FROM route_stop_overlap o
        JOIN route_stop_coverage ca ON ca.group_version = o.group_version AND ca.geometry_version = o.geometry_version
                                   AND ca.route = o.route_a
        JOIN route_stop_coverage cb ON cb.group_version = o.group_version AND cb.geometry_version = o.geometry_version
                                   AND cb.route = o.route_b
        WHERE o.group_version = %s AND o.geometry_version = %s
        ORDER BY o.overlap_review_rank, o.route_a, o.route_b""", (gv["group_version"], geometry_version)).fetchall()
    return envelope(
        v, cutoff_block(v, cutoff),
        metric={"key": OVERLAP, "label": "Route overlap review",
                "meaning": "shared stops, Jaccard and exclusive coverage: a corridor worth examining",
                "spec_reference": SPEC_REFERENCE,
                "caveat": rows[0]["interpretation"] if rows else None},
        geometry_version=geometry_version, default_geometry_version=gv["default_overlap_version"],
        available_geometry_versions=allowed, counts={"pairs": len(rows)}, rows=rows,
    )
