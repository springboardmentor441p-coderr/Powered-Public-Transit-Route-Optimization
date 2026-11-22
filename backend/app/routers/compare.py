"""GET /api/routes/compare: two or more routes over ONE period and day type (spec 9.16.2 "Compare routes":
comparable period/day type, demand/service and coverage differences; 9.17.3 "comparable route evidence and
geometry version").

For each route: the three named indicators with their network rank (ranked among ALL routes at the reference gate,
so a rank means the same as on Review priorities), numerator/denominator, eligibility and reason; coverage (observed
days, scheduled service days, unmatched days on each side, incomplete-duration days); its group. Across the routes:
the dates on which ALL of them are matched, so the reader can see whether they were observed on the same days.

Map: each route's "most common path per direction" in one named geometry version, with tie labels. A route that is
not in that version is still returned, with no lines and a reason (never an error, never a silently empty map).
Plus the Stage 5 overlap rows among the selected routes.

Cutoff: every row is read through db.permitted_through in SQL (via compute_profiles and the queries below); the
period is clipped to it; only archives captured on or before it can be the geometry version.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from analytics.geometry.route_shapes import PATH_LABEL, tie_label
from backend.app.db import GROUPS_AFTER_CUTOFF, cutoff_block, get_conn, group_version_for, permitted_through, \
    resolve_version
from backend.app.db import request_cutoff
from backend.app.labels import UNITS, envelope
from backend.app.routers.rankings import (CAVEAT, METRICS, PART_LABELS, PERIOD_LABELS, REFERENCE_GATE, _none, compute_profiles,
                                          gate_label, resolve_period)

router = APIRouter(tags=["routes"])
NO_COMMON_DAYS = "no date on which all selected routes were observed"
SAME_DAYS_RANK_NOTE = "network ranks are shown only for each route's own observed days, not for a chosen set of dates"
MAX_ROUTES = 8
NOT_IN_VERSION = "not in this timetable version"
NO_ACTIVE_TRIPS = "in this timetable version, but no active trips on its applied dates"


def _per_day(total, days: int):
    total = _none(total)
    return None if total is None or not days else total / days


@router.get("/api/routes/compare")
def compare_routes(
    routes: str = Query(..., description=f"comma-separated, 2 to {MAX_ROUTES} distinct routes, e.g. 49,X49"),
    period: Literal["full_matched_window", "development"] | None = None,
    start: date | None = None,
    end: date | None = None,
    daytype: Literal["W", "A", "U"] = "W",
    geometry_version: str | None = Query(None, description="default: the archive in force on the period's last day"),
    same_days: bool = Query(False, description="compute every value on the dates ALL selected routes were observed"),
    cutoff: date | None = Depends(request_cutoff),
    data_version: str | None = None,
    conn: psycopg.Connection = Depends(get_conn),
) -> dict:
    wanted = [r.strip() for r in routes.split(",") if r.strip()]
    if len(set(wanted)) != len(wanted):
        raise HTTPException(422, "each route may appear only once")
    if not 2 <= len(wanted) <= MAX_ROUTES:
        raise HTTPException(422, f"compare needs 2 to {MAX_ROUTES} routes, got {len(wanted)}")
    v = resolve_version(conn, data_version)
    dv, through = v["data_version"], permitted_through(v, cutoff)
    name, a, b, b_eff = resolve_period(period, start, end, through)
    p = {"dv": dv, "a": a, "b": b_eff, "t": through, "routes": wanted, "dt": daytype, "n": len(wanted)}

    known = {r["route"] for r in conn.execute(
        """SELECT route FROM daily_ridership WHERE data_version = %(dv)s AND route = ANY(%(routes)s)
                                               AND service_date <= %(t)s
           UNION SELECT route FROM daily_schedule WHERE data_version = %(dv)s AND route = ANY(%(routes)s)
                                                    AND service_date <= %(t)s""", p).fetchall()}
    if set(wanted) - known:
        raise HTTPException(404, f"no recorded rides or scheduled service on or before {through} for "
                                 f"{sorted(set(wanted) - known)}")

    # ---- indicators: network ranks (all routes ranked at the reference gate, then the selected ones picked)
    prof = compute_profiles(conn, dv, name, a, b_eff, through, REFERENCE_GATE)
    rows = {} if prof is None else {r["route"]: r for r in prof[(prof["daytype"] == daytype)
                                                                & prof["route"].isin(wanted)].to_dict("records")}

    # ---- coverage on each side (dates of this day type), and the dates all selected routes share
    cov = {r["route"]: r for r in conn.execute("""
        SELECT x.route,
               (SELECT count(*) FROM ridership_without_schedule w WHERE w.data_version = %(dv)s
                       AND w.route = x.route AND w.daytype = %(dt)s
                       AND w.service_date BETWEEN %(a)s AND %(b)s) AS recorded_days_without_schedule,
               (SELECT count(*) FROM schedule_without_ridership w WHERE w.data_version = %(dv)s
                       AND w.route = x.route AND w.service_date BETWEEN %(a)s AND %(b)s
                       AND EXISTS (SELECT 1 FROM daily_ridership o WHERE o.data_version = %(dv)s
                                   AND o.service_date = w.service_date AND o.daytype = %(dt)s))
                       AS scheduled_days_without_record
        FROM unnest(%(routes)s::text[]) AS x(route)""", p).fetchall()}
    common_dates = {r["service_date"] for r in conn.execute("""
        SELECT service_date FROM matched_utilization
         WHERE data_version = %(dv)s AND route = ANY(%(routes)s) AND daytype = %(dt)s
           AND service_date BETWEEN %(a)s AND %(b)s
         GROUP BY service_date HAVING count(DISTINCT route) = %(n)s""", p).fetchall()}
    common = len(common_dates)
    if same_days:  # every value on the shared dates only; network ranks are not defined on hand-picked dates
        prof = compute_profiles(conn, dv, name, a, b_eff, through, REFERENCE_GATE, set(wanted), common_dates)             if common_dates else None
        rows = {} if prof is None else {r["route"]: r for r in prof[prof["daytype"] == daytype].to_dict("records")}

    # ---- groups (only if fitted on data up to the cutoff)
    gv = group_version_for(conn, dv, through)
    groups = {} if gv is None else {r["route"]: r for r in conn.execute(
        """SELECT route, group_id, group_name, CASE WHEN group_id IS NULL THEN reason END AS ungrouped_reason
           FROM group_memberships WHERE group_version = %s AND route = ANY(%s)""",
        (gv["group_version"], wanted)).fetchall()}

    # ---- geometry: one named version, captured on or before the cutoff
    allowed = conn.execute("""SELECT snapshot_id, applied_start, applied_end FROM gtfs_snapshots
                              WHERE data_version = %(dv)s AND captured_date <= %(t)s ORDER BY applied_start""",
                           p).fetchall()
    if geometry_version is None:
        in_force = [g["snapshot_id"] for g in allowed if g["applied_start"] <= b_eff <= g["applied_end"]]
        geometry_version = in_force[0] if in_force else (allowed[-1]["snapshot_id"] if allowed else None)
    elif geometry_version not in {g["snapshot_id"] for g in allowed}:
        raise HTTPException(422, f"geometry version {geometry_version!r} is unknown or captured after the cutoff")
    lines = conn.execute("""SELECT route, direction_id, direction_label, shape_id, tied_top_shapes, line_geojson
                            FROM route_shapes WHERE data_version = %s AND geometry_version = %s AND route = ANY(%s)
                            ORDER BY route, direction_id""", (dv, geometry_version, wanted)).fetchall()
    for ln in lines:
        ln["tie_label"] = tie_label(ln["tied_top_shapes"])
    in_version = {r["route"] for r in conn.execute(
        "SELECT route FROM routes WHERE data_version = %s AND geometry_version = %s AND route = ANY(%s)",
        (dv, geometry_version, wanted)).fetchall()}
    with_lines = {ln["route"] for ln in lines}
    no_lines = [{"route": r, "reason": NO_ACTIVE_TRIPS if r in in_version else NOT_IN_VERSION}
                for r in wanted if r not in with_lines]
    ogv = group_version_for(conn, dv)  # the overlap product comes from GTFS stop sets only (no ridership)
    overlap = [] if ogv is None or geometry_version is None else conn.execute("""
        SELECT route_a, route_b, shared_stop_count, jaccard_stop_overlap, smaller_route_stop_overlap,
               overlap_review_rank, interpretation
        FROM route_stop_overlap WHERE group_version = %s AND geometry_version = %s
          AND route_a = ANY(%s) AND route_b = ANY(%s)
        ORDER BY overlap_review_rank, route_a, route_b""",
                                                                              (ogv["group_version"], geometry_version,
                                                                               wanted, wanted)).fetchall()

    out = []
    for route in wanted:
        r = rows.get(route)
        obs = 0 if r is None else int(r["observed_days"])
        indicators = None if r is None else {
            metric: {"label": label, "unit": unit, "value": _none(r[value_col]),
                     "network_rank": None if same_days else _none(r[rank_col]),
                     "eligible": bool(r[f"{rank_col}_eligible"]), "reason": _none(r[f"{rank_col}_reason"]),
                     "numerator": _none(r[num_col]), "denominator": _none(r[den_col]),
                     "numerator_label": PART_LABELS[num_col], "denominator_label": PART_LABELS[den_col]}
            for metric, (rank_col, value_col, num_col, den_col, label, unit) in METRICS.items()}
        out.append({
            "route": route,
            "indicators": indicators,
            "no_matched_days_reason": None if r is not None else (
                NO_COMMON_DAYS if same_days else "no matched days of this day type in the period"),
            "service": None if r is None else {
                "mean_scheduled_trips": _per_day(r["scheduled_trips_sum"], obs),
                "mean_scheduled_service_hours": _per_day(r["scheduled_hours_sum"], obs)},
            "coverage": {"observed_days": obs,
                         "scheduled_service_days": None if r is None else _none(r["scheduled_service_days"]),
                         "incomplete_duration_days": 0 if r is None else int(r["incomplete_duration_days"]),
                         "recorded_days_without_schedule": cov[route]["recorded_days_without_schedule"],
                         "scheduled_days_without_record": cov[route]["scheduled_days_without_record"]},
            "group": groups.get(route),
            "map_lines": sum(ln["route"] == route for ln in lines),
        })
    return envelope(
        v, cutoff_block(v, cutoff),
        period={"name": name, "label": PERIOD_LABELS[name], "start": a, "end": b_eff, "clipped_to_cutoff": b > through},
        daytype=daytype, units=UNITS, caveat=CAVEAT,
        configuration={"min_observed_days": REFERENCE_GATE, "gate_label": gate_label(REFERENCE_GATE),
                       "ranks": "network ranks among all routes in the period and day type"},
        same_days=same_days,
        basis_label=(f"values on the {common} dates all selected routes were observed" if same_days
                     else "values on each route's own observed days"),
        rank_note=SAME_DAYS_RANK_NOTE if same_days else None,
        common_matched_days=common,
        comparable_note=None if all(x["coverage"]["observed_days"] == common for x in out) else
        "the routes were not all observed on the same dates; compare observed days before comparing values",
        groups_note=None if gv else GROUPS_AFTER_CUTOFF,
        routes=out,
        map={"geometry_version": geometry_version, "label": PATH_LABEL, "lines": lines,
             "routes_without_lines": no_lines},
        overlap=overlap,
    )
