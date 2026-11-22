"""GET /api/routes/{route}/history: one row for EVERY calendar date in the range, so a gap is shown as a gap with
its reason, never as 0 (spec 9.16.1, 9.17.3 "mode/cutoff-aware observation history").

Each date carries its reported day type, recorded rides (or none), the scheduled service of the selected archive
(or none), the two ratios when both sides exist, and a status with its reason:
  matched                       recorded rides and scheduled service on the same date
  ridership_without_schedule    rides recorded, no selected scheduled service (Stage 2 reason)
  schedule_without_ridership    service scheduled, no ridership record (Stage 2 reason); rides stay null
  no_service_no_record          in the schedule window: neither service nor a record (e.g. a weekday-only route on
                                a Saturday)
  recorded_rides_only           before the schedule window: rides recorded, no dated schedule exists
  no_record                     before the schedule window: no ridership record

Only mode=historical exists in Stage 6 (replay arrives with Stage 7). The cutoff is applied in SQL (db.permitted_
through): the range is clipped to it, and no row, count or snapshot after it is read. A range that starts after the
cutoff is refused (422), not answered with an empty list.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.db import cutoff_block, get_conn, permitted_through, resolve_version
from backend.app.db import request_cutoff
from backend.app.labels import LABELS, UNITS, envelope, reason_words

router = APIRouter(tags=["routes"])
REASONS = {
    "no_service_no_record": "no scheduled service and no ridership record on this date",
    "recorded_rides_only": "rides recorded; no dated schedule exists before the analysis window",
    "no_record": "no ridership record; no dated schedule exists before the analysis window",
}
STARTS_AFTER_CUTOFF = "the requested range starts after the cutoff"

HISTORY_SQL = """
WITH d AS (SELECT generate_series(%(a)s::date, %(b)s::date, interval '1 day')::date AS service_date),
     dt AS (SELECT service_date, min(daytype) AS daytype FROM daily_ridership          -- one reported day type
            WHERE data_version = %(dv)s AND service_date BETWEEN %(a)s AND %(b)s GROUP BY 1),  -- per date (all routes)
     r AS (SELECT service_date, daytype, rides FROM daily_ridership
           WHERE data_version = %(dv)s AND route = %(route)s AND service_date BETWEEN %(a)s AND %(b)s),
     s AS (SELECT service_date, snapshot_id, scheduled_trips, scheduled_service_hours, duration_complete,
                  trips_missing_duration FROM daily_schedule
           WHERE data_version = %(dv)s AND route = %(route)s AND service_date BETWEEN %(a)s AND %(b)s),
     m AS (SELECT service_date, rides_per_scheduled_trip, rides_per_scheduled_hour FROM matched_utilization
           WHERE data_version = %(dv)s AND route = %(route)s AND service_date BETWEEN %(a)s AND %(b)s),
     w AS (SELECT service_date, unmatched_reason FROM ridership_without_schedule
           WHERE data_version = %(dv)s AND route = %(route)s AND service_date BETWEEN %(a)s AND %(b)s),
     x AS (SELECT service_date, missing_reason FROM schedule_without_ridership
           WHERE data_version = %(dv)s AND route = %(route)s AND service_date BETWEEN %(a)s AND %(b)s)
SELECT d.service_date, coalesce(r.daytype, dt.daytype) AS daytype, r.rides,
       g.snapshot_id AS selected_snapshot_id, s.scheduled_trips, s.scheduled_service_hours, s.duration_complete,
       s.trips_missing_duration, m.rides_per_scheduled_trip, m.rides_per_scheduled_hour,
       CASE WHEN m.service_date IS NOT NULL THEN 'matched'
            WHEN w.service_date IS NOT NULL THEN 'ridership_without_schedule'
            WHEN x.service_date IS NOT NULL THEN 'schedule_without_ridership'
            WHEN g.snapshot_id IS NOT NULL THEN 'no_service_no_record'
            WHEN r.service_date IS NOT NULL THEN 'recorded_rides_only'
            ELSE 'no_record' END AS status,
       coalesce(w.unmatched_reason, x.missing_reason) AS stage2_reason,
       (r.service_date IS NOT NULL) AS has_record, (s.service_date IS NOT NULL) AS has_schedule
FROM d
LEFT JOIN dt USING (service_date) LEFT JOIN r USING (service_date) LEFT JOIN s USING (service_date)
LEFT JOIN m USING (service_date) LEFT JOIN w USING (service_date) LEFT JOIN x USING (service_date)
LEFT JOIN gtfs_snapshots g ON g.data_version = %(dv)s AND d.service_date BETWEEN g.applied_start AND g.applied_end
ORDER BY d.service_date
"""


@router.get("/api/routes/{route}/history")
def route_history(
    route: str,
    mode: Literal["historical"] = Query("historical", description="Stage 6: historical analysis only "
                                                                  "(replay mode arrives with Stage 7)"),
    start: date | None = Query(None, description="default: the start of the analysis window (dated schedules)"),
    end: date | None = Query(None, description="default: the last permitted date"),
    cutoff: date | None = Depends(request_cutoff),
    data_version: str | None = None,
    conn: psycopg.Connection = Depends(get_conn),
) -> dict:
    if start and end and start > end:
        raise HTTPException(422, "start must not be after end")
    v = resolve_version(conn, data_version)
    through = permitted_through(v, cutoff)
    if start and start > through:
        raise HTTPException(422, f"{STARTS_AFTER_CUTOFF} ({start} > {through})")
    a = start or v["analysis_start"]
    b = min(end or through, through)
    p = {"dv": v["data_version"], "route": route, "a": a, "b": b, "t": through}
    known = conn.execute("""SELECT EXISTS (SELECT 1 FROM daily_ridership WHERE data_version = %(dv)s
                                           AND route = %(route)s AND service_date <= %(t)s)
                                OR EXISTS (SELECT 1 FROM daily_schedule WHERE data_version = %(dv)s
                                           AND route = %(route)s AND service_date <= %(t)s) AS known""",
                         p).fetchone()["known"]
    if not known:
        raise HTTPException(404, f"route {route!r} has no recorded rides or scheduled service "
                                 f"on or before {through}")
    rows = conn.execute(HISTORY_SQL, p).fetchall() if a <= b else []
    for row in rows:
        code = row.pop("stage2_reason")
        row["reason_code"] = code                       # Stage 2's code, for machines; `reason` is for people
        row["reason"] = reason_words(code) or REASONS.get(row["status"])
    summary: dict[str, int] = {}
    for row in rows:
        summary[row["status"]] = summary.get(row["status"], 0) + 1
    name = conn.execute("""SELECT x.route_long_name, x.geometry_version FROM routes x
                           JOIN gtfs_snapshots s ON s.data_version = x.data_version AND s.snapshot_id = x.geometry_version
                           WHERE x.data_version = %(dv)s AND x.route = %(route)s AND s.captured_date <= %(t)s
                           ORDER BY s.captured_date DESC LIMIT 1""", p).fetchone()
    return envelope(
        v, cutoff_block(v, cutoff),
        route=route, route_long_name=name["route_long_name"] if name else None,
        name_geometry_version=name["geometry_version"] if name else None,
        # the request is not echoed back: a requested end after the cutoff would put a later date in the response
        range={"start": a, "end": b, "clipped_to_cutoff": end is not None and end > through,
               "schedule_window": {"start": v["analysis_start"], "end": min(v["analysis_end"], through)}},
        labels={"rides": LABELS["recorded_rides"], "scheduled_trips": LABELS["scheduled_trips"],
                "scheduled_service_hours": LABELS["scheduled_hours"]},
        units=UNITS, summary=summary, count=len(rows), days=rows,
    )
