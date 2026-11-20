"""GET /api/map/lines: the "most common path per direction" lines of ONE geometry version, for the network map
(spec 9.16.2 "dated map") and route detail. Every response names its geometry version (spec 9.19.2).

Version choice: `geometry_version`, or `date` (the archive applied on that date), or neither (the archive in force on
the last permitted date). Under a cutoff, only archives captured on or before it, and only dates on or before it.
Lines are simplified FOR DISPLAY (default 10 m; 0 = the stored line exactly); the response states the tolerance and
the point counts. Requested routes that are not in the version are returned with no lines and a reason.
"""
from __future__ import annotations

from datetime import date

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from analytics.geometry.route_shapes import PATH_LABEL, tie_label
from analytics.geometry.simplify import simplify
from backend.app.db import GROUPS_AFTER_CUTOFF, cutoff_block, get_conn, group_version_for, permitted_through, \
    resolve_version
from backend.app.labels import envelope
from backend.app.routers.compare import NO_ACTIVE_TRIPS, NOT_IN_VERSION

router = APIRouter(tags=["map"])
DEFAULT_SIMPLIFY_M = 10.0


@router.get("/api/map/lines")
def map_lines(
    geometry_version: str | None = None,
    date_: date | None = Query(None, alias="date", description="the archive applied on this service date"),
    routes: str | None = Query(None, description="comma-separated; default: every route in the version"),
    simplify_m: float = Query(DEFAULT_SIMPLIFY_M, ge=0, le=100, description="display tolerance in metres; 0 = exact"),
    cutoff: date | None = Query(None, description="use only service dates on or before this date"),
    data_version: str | None = None,
    conn: psycopg.Connection = Depends(get_conn),
) -> dict:
    if geometry_version and date_:
        raise HTTPException(422, "give either geometry_version or date, not both")
    v = resolve_version(conn, data_version)
    dv, through = v["data_version"], permitted_through(v, cutoff)
    if date_ and date_ > through:
        raise HTTPException(422, f"the requested date is after the cutoff ({date_} > {through})")
    allowed = conn.execute("""SELECT snapshot_id, applied_start, least(applied_end, %s) AS applied_end
                              FROM gtfs_snapshots WHERE data_version = %s AND captured_date <= %s
                              ORDER BY applied_start""", (through, dv, through)).fetchall()
    if geometry_version:
        chosen = next((g for g in allowed if g["snapshot_id"] == geometry_version), None)
        if chosen is None:
            raise HTTPException(422, f"geometry version {geometry_version!r} is unknown or captured after the cutoff")
    else:
        on = date_ or through
        chosen = next((g for g in allowed if g["applied_start"] <= on <= g["applied_end"]), None)
        if chosen is None:
            raise HTTPException(422, f"no timetable version applies on {on} (dated schedules cover "
                                     f"{v['analysis_start']} onwards)")
    gvid = chosen["snapshot_id"]
    wanted = None if routes is None else [r.strip() for r in routes.split(",") if r.strip()]
    gv = group_version_for(conn, dv, through)
    rows = conn.execute("""
        SELECT s.route, r.route_long_name, s.direction_id, s.direction_label, s.shape_id, s.tied_top_shapes,
               s.point_count, s.line_geojson, m.group_id
        FROM route_shapes s JOIN routes r USING (data_version, geometry_version, route)
        LEFT JOIN group_memberships m ON m.group_version = %(gv)s AND m.route = s.route
        WHERE s.data_version = %(dv)s AND s.geometry_version = %(g)s
          AND (%(routes)s::text[] IS NULL OR s.route = ANY(%(routes)s))
        ORDER BY s.route, s.direction_id""",
                        {"dv": dv, "g": gvid, "routes": wanted,
                         "gv": gv["group_version"] if gv else None}).fetchall()
    sent = 0
    for ln in rows:
        coords = simplify(ln["line_geojson"]["coordinates"], simplify_m)
        ln["line_geojson"] = {"type": "LineString", "coordinates": coords}
        ln["points_sent"] = len(coords)
        ln["tie_label"] = tie_label(ln["tied_top_shapes"])
        sent += len(coords)
    no_lines = []
    if wanted is not None:
        have = {ln["route"] for ln in rows}
        listed = {r["route"] for r in conn.execute(
            "SELECT route FROM routes WHERE data_version = %s AND geometry_version = %s AND route = ANY(%s)",
            (dv, gvid, wanted)).fetchall()}
        no_lines = [{"route": r, "reason": NO_ACTIVE_TRIPS if r in listed else NOT_IN_VERSION}
                    for r in wanted if r not in have]
    return envelope(
        v, cutoff_block(v, cutoff),
        geometry_version=gvid,
        applied={"start": chosen["applied_start"], "end": chosen["applied_end"]},
        label=PATH_LABEL,
        display={"simplify_m": simplify_m,
                 "note": "stored lines exactly" if simplify_m == 0 else
                 f"simplified for display: every stored point within {simplify_m:g} m of the drawn line",
                 "points_stored": sum(ln["point_count"] for ln in rows), "points_sent": sent},
        groups_note=None if gv else GROUPS_AFTER_CUTOFF,
        count=len(rows), lines=rows, routes_without_lines=no_lines,
    )
