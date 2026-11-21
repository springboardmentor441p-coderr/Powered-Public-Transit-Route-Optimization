"""GET /api/network/trend: the whole network's recorded rides, one row for EVERY calendar date in the range
(spec 9.16.2 "Network overview: demand trend"). A date without any ridership record is a gap with its reason,
never 0 (spec 9.16.1).

Each date carries the reported day type, the sum of recorded rides over the routes that reported that day and how
many routes that was, and, inside the schedule window, the selected archive's scheduled trips summed over routes:
  recorded              rides recorded, inside the schedule window (schedule totals present)
  recorded_rides_only   rides recorded, before the schedule window: no dated schedule exists
  no_record             no route has a ridership record on this date (rides null, never 0)

The total depends on which routes reported, so `routes_reporting` travels with it. `summary` (days, mean and
median rides/day per day type) lets a screen write its insight sentence from the API instead of hard-coding it.
The cutoff is applied in SQL (db.permitted_through): no row or count after it is read.
"""
from __future__ import annotations

import statistics
from datetime import date

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.db import cutoff_block, get_conn, permitted_through, resolve_version
from backend.app.labels import LABELS, UNITS, envelope

router = APIRouter(tags=["network"])
REASONS = {
    "recorded_rides_only": "rides recorded; no dated schedule exists before the analysis window",
    "no_record": "no route has a ridership record on this date",
}
STARTS_AFTER_CUTOFF = "the requested range starts after the cutoff"
TOTAL_NOTE = ("network total of the routes that reported rides that day; compare it with the number of routes "
              "reporting that day (hover a day)")
DAYTYPES = {"W": "weekday", "A": "Saturday", "U": "Sunday/holiday"}

TREND_SQL = """
WITH d AS (SELECT generate_series(%(a)s::date, %(b)s::date, interval '1 day')::date AS service_date),
     r AS (SELECT service_date, min(daytype) AS daytype, sum(rides)::bigint AS rides, count(*) AS routes_reporting
           FROM daily_ridership
           WHERE data_version = %(dv)s AND service_date BETWEEN %(a)s AND least(%(b)s, %(t)s) GROUP BY 1),
     s AS (SELECT service_date, sum(scheduled_trips)::bigint AS scheduled_trips, count(*) AS routes_scheduled
           FROM daily_schedule
           WHERE data_version = %(dv)s AND service_date BETWEEN %(a)s AND least(%(b)s, %(t)s) GROUP BY 1)
SELECT d.service_date, r.daytype, r.rides, coalesce(r.routes_reporting, 0) AS routes_reporting,
       s.scheduled_trips, s.routes_scheduled,
       CASE WHEN r.service_date IS NULL THEN 'no_record'
            WHEN d.service_date < %(w0)s OR d.service_date > %(w1)s THEN 'recorded_rides_only'
            ELSE 'recorded' END AS status
FROM d LEFT JOIN r USING (service_date) LEFT JOIN s USING (service_date)
ORDER BY d.service_date
"""


def summarise(rows: list[dict]) -> list[dict]:
    """Per reported day type: days with a record, mean and median recorded rides/day. Gaps are not counted."""
    out = []
    for code, name in DAYTYPES.items():
        vals = [r["rides"] for r in rows if r["daytype"] == code and r["rides"] is not None]
        out.append({"daytype": code, "daytype_label": name, "days": len(vals),
                    "mean_rides": statistics.fmean(vals) if vals else None,
                    "median_rides": float(statistics.median(vals)) if vals else None,
                    "reason": None if vals else f"no {name} with a ridership record in this range"})
    return out


@router.get("/api/network/trend")
def network_trend(
    start: date | None = Query(None, description="default: the start of the analysis window (dated schedules); "
                                                 "may go back to the first recorded date"),
    end: date | None = Query(None, description="default: the last permitted date"),
    cutoff: date | None = Query(None, description="use only service dates on or before this date"),
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
    w0, w1 = v["analysis_start"], min(v["analysis_end"], through)
    rows = conn.execute(TREND_SQL, {"dv": v["data_version"], "a": a, "b": b, "t": through,
                                    "w0": w0, "w1": w1}).fetchall()
    for row in rows:
        row["reason"] = REASONS.get(row["status"])
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return envelope(
        v, cutoff_block(v, cutoff),
        range={"start": a, "end": b, "clipped_to_cutoff": end is not None and end > through,
               "schedule_window": {"start": w0, "end": w1}},
        labels={"rides": LABELS["recorded_rides"], "scheduled_trips": LABELS["scheduled_trips"]},
        units={"rides": UNITS["rides"], "scheduled_trips": UNITS["scheduled_trips"]},
        total_note=TOTAL_NOTE, status_counts=counts, summary=summarise(rows), count=len(rows), days=rows,
    )
