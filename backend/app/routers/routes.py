"""GET /api/routes: every route identifier with recorded rides, with names, history range, group and weekend service
status; optional filters (spec 9.17.3 "route discovery and filters").

Group status has three cases, kept apart: grouped (group_id set); ungrouped (in the Stage 5 population, group_id
NULL, with a reason); outside the population (in_group_population = false: recorded rides only before the
ridership window, so Stage 5 never considered it).

With a cutoff: only rides, matched days and archives on or before it are used. Routes with no recorded ride by then
are not listed. Names come only from archives captured by then. Route groups (fitted on the Stage 5 development
period) are shown only if that period ends on or before the cutoff; otherwise group fields are null, the reason is
given, and group/weekend filters return 422.
"""
from __future__ import annotations

from datetime import date

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.db import GROUPS_AFTER_CUTOFF, cutoff_block, get_conn, group_version_for, permitted_through, \
    resolve_version
from backend.app.db import request_cutoff
from backend.app.labels import envelope

router = APIRouter(tags=["routes"])
HAS_SERVICE = ["available", "insufficient_observations"]  # service scheduled (observations may be few)


@router.get("/api/routes")
def list_routes(
    data_version: str | None = None,
    cutoff: date | None = Depends(request_cutoff),
    group_id: int | None = Query(None, ge=0, description="only routes in this group"),
    ungrouped: bool | None = Query(None, description="true: routes in the group population left ungrouped (with a "
                                                     "reason); false: grouped routes. Routes outside the population "
                                                     "(no rides in the ridership window) match neither"),
    saturday_service: bool | None = Query(None, description="scheduled Saturday service in the profile period; "
                                                            "routes without a profile match neither value"),
    sunday_holiday_service: bool | None = Query(None, description="scheduled Sunday/holiday service in the profile "
                                                                  "period; routes without a profile match neither"),
    active_start: date | None = Query(None, description="with active_end: a recorded ride within the dates"),
    active_end: date | None = None,
    conn: psycopg.Connection = Depends(get_conn),
) -> dict:
    if (active_start is None) != (active_end is None):
        raise HTTPException(422, "active_start and active_end must be given together")
    if active_start and active_start > active_end:
        raise HTTPException(422, "active_start must not be after active_end")
    v = resolve_version(conn, data_version)
    through = permitted_through(v, cutoff)
    gv = group_version_for(conn, v["data_version"], through)
    if gv is None and any(f is not None for f in [group_id, ungrouped, saturday_service, sunday_holiday_service]):
        raise HTTPException(422, f"group and weekend-service filters are unavailable: {GROUPS_AFTER_CUTOFF}")
    where, p = [], {"dv": v["data_version"], "t": through, "gv": gv["group_version"] if gv else None,
                    "a": active_start, "b": active_end, "g": group_id, "has": HAS_SERVICE}
    if group_id is not None:
        where.append("g.group_id = %(g)s")
    if ungrouped is not None:  # only routes in the Stage 5 population (a membership row) are grouped or ungrouped
        where.append("g.route IS NOT NULL AND g.group_id IS NULL" if ungrouped else "g.group_id IS NOT NULL")
    for flag, col in [(saturday_service, "saturday_service_status"),
                      (sunday_holiday_service, "sunday_holiday_service_status")]:
        if flag is not None:
            where.append(f"p.{col} = ANY(%(has)s)" if flag else f"p.{col} = 'no_scheduled_service'")
    if active_start:
        where.append("""EXISTS (SELECT 1 FROM daily_ridership x WHERE x.data_version = %(dv)s AND x.route = r.route
                        AND x.service_date BETWEEN %(a)s AND least(%(b)s, %(t)s))""")
    rows = conn.execute(f"""
        WITH r AS (SELECT route, min(service_date) AS first_ride_date, max(service_date) AS last_ride_date,
                          count(*) AS recorded_days
                   FROM daily_ridership WHERE data_version = %(dv)s AND service_date <= %(t)s GROUP BY route),
             n AS (SELECT DISTINCT ON (x.route) x.route, x.route_long_name, x.geometry_version AS name_geometry_version
                   FROM routes x JOIN gtfs_snapshots s ON s.data_version = x.data_version
                                                       AND s.snapshot_id = x.geometry_version
                   WHERE x.data_version = %(dv)s AND s.captured_date <= %(t)s
                   ORDER BY x.route, s.captured_date DESC),
             m AS (SELECT route, count(*) AS matched_days FROM matched_utilization
                   WHERE data_version = %(dv)s AND service_date <= %(t)s GROUP BY route)
        SELECT r.route, n.route_long_name, n.name_geometry_version, r.first_ride_date, r.last_ride_date,
               r.recorded_days, coalesce(m.matched_days, 0) AS matched_days, n.route IS NOT NULL AS in_any_archive,
               g.route IS NOT NULL AS in_group_population,
               g.group_id, g.group_name, CASE WHEN g.group_id IS NULL THEN g.reason END AS ungrouped_reason,
               p.saturday_service_status, p.sunday_holiday_service_status
        FROM r LEFT JOIN n USING (route) LEFT JOIN m USING (route)
        LEFT JOIN group_memberships g ON g.group_version = %(gv)s AND g.route = r.route
        LEFT JOIN route_profiles p ON p.group_version = %(gv)s AND p.route = r.route
        {"WHERE " + " AND ".join(where) if where else ""}
        ORDER BY (r.route ~ '^[0-9]+$') DESC, NULLIF(regexp_replace(r.route, '[^0-9]', '', 'g'), '')::int, r.route
        """, p).fetchall()
    return envelope(v, cutoff_block(v, cutoff),
                    group_version=gv, groups_note=None if gv else GROUPS_AFTER_CUTOFF,
                    filters={"group_id": group_id, "ungrouped": ungrouped, "saturday_service": saturday_service,
                             "sunday_holiday_service": sunday_holiday_service,
                             "active_start": active_start, "active_end": active_end},
                    count=len(rows), routes=rows)
