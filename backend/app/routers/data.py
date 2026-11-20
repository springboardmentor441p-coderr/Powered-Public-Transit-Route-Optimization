"""GET /api/data/coverage: dataset version, observation and schedule ranges, archive coverage, match counts,
missingness and quality (spec 9.17.3). Source hashes are grouped under `details` (spec 9.16.1 data-details panel).

With a cutoff, every date-derived field is computed in SQL from service dates on or before it: last dates, row
counts, matched days and missingness. Archives captured after the cutoff are not listed, and applied ranges are
clipped to it. Version-level figures that would reveal later data (rows excluded after the version's own ridership
cutoff, the importer's per-file row counts, the import timestamp) are left out.
"""
from __future__ import annotations

from datetime import date

import psycopg
from fastapi import APIRouter, Depends, Query

from backend.app.db import cutoff_block, get_conn, permitted_through, resolve_version
from backend.app.labels import LABELS, envelope

router = APIRouter(tags=["data"])


@router.get("/api/data/coverage")
def coverage(data_version: str | None = None,
             cutoff: date | None = Query(None, description="use only service dates on or before this date"),
             conn: psycopg.Connection = Depends(get_conn)) -> dict:
    v = resolve_version(conn, data_version)
    through = permitted_through(v, cutoff)
    p = {"dv": v["data_version"], "t": through, "a": v["analysis_start"], "b": min(v["analysis_end"], through)}
    obs = conn.execute("""SELECT min(service_date) AS first_date, max(service_date) AS last_date, count(*) AS rows,
                                 count(DISTINCT route) AS route_identifiers,
                                 count(*) FILTER (WHERE rides = 0) AS recorded_zero_rows
                          FROM daily_ridership WHERE data_version = %(dv)s AND service_date <= %(t)s""", p).fetchone()
    sched = conn.execute("""SELECT min(service_date) AS first_date, max(service_date) AS last_date, count(*) AS rows,
                                   count(DISTINCT service_date) AS dates, count(DISTINCT route) AS routes,
                                   count(*) FILTER (WHERE NOT duration_complete) AS incomplete_duration_rows
                            FROM daily_schedule WHERE data_version = %(dv)s AND service_date <= %(t)s""", p).fetchone()
    archives = conn.execute("""
        SELECT g.snapshot_id AS geometry_version, g.captured_date, g.applied_start,
               least(g.applied_end, %(t)s) AS applied_end,
               (least(g.applied_end, %(t)s) - g.applied_start + 1) AS applied_days,
               (SELECT count(*) FROM routes r WHERE r.data_version = g.data_version
                                               AND r.geometry_version = g.snapshot_id) AS bus_routes,
               (SELECT count(DISTINCT s.route) FROM daily_schedule s
                 WHERE s.data_version = g.data_version AND s.snapshot_id = g.snapshot_id
                   AND s.service_date <= %(t)s) AS scheduled_routes,
               (SELECT count(*) FROM route_shapes h WHERE h.data_version = g.data_version
                                               AND h.geometry_version = g.snapshot_id) AS map_lines,
               f.sha256
        FROM gtfs_snapshots g JOIN source_files f USING (data_version, snapshot_id)
        WHERE g.data_version = %(dv)s AND g.captured_date <= %(t)s AND g.applied_start <= %(t)s
        ORDER BY g.applied_start""", p).fetchall()
    matched = conn.execute("""SELECT count(*) AS rows, count(DISTINCT service_date) AS dates,
                                     count(DISTINCT route) AS routes
                              FROM matched_utilization WHERE data_version = %(dv)s AND service_date <= %(t)s""",
                           p).fetchone()
    missing_sql = """SELECT {reason} AS reason, count(*) AS rows, count(DISTINCT route) AS routes,
                            array_agg(DISTINCT route ORDER BY route) AS route_list,
                            min(service_date) AS first_date, max(service_date) AS last_date
                     FROM {table} WHERE data_version = %(dv)s AND service_date <= %(t)s
                     GROUP BY 1 ORDER BY 2 DESC, 1"""
    no_sched = conn.execute(missing_sql.format(reason="unmatched_reason", table="ridership_without_schedule"),
                            p).fetchall()
    no_rides = conn.execute(missing_sql.format(reason="missing_reason", table="schedule_without_ridership"),
                            p).fetchall()
    in_window = conn.execute("""SELECT count(*) AS n FROM daily_ridership WHERE data_version = %(dv)s
                                AND service_date BETWEEN %(a)s AND %(b)s""", p).fetchone()["n"]
    rep = conn.execute("SELECT import_report FROM dataset_versions WHERE data_version = %(dv)s", p).fetchone()
    report = rep["import_report"]

    observations = {"label": LABELS["recorded_rides"], **obs}
    details = {"import_git_commit": v["import_git_commit"], "built_git_commit": v["built_git_commit"],
               "schema_sha256": report["schema_sha256"],
               "archive_sha256": {a["geometry_version"]: a["sha256"] for a in archives}}
    if cutoff is None:  # version-level figures: only without a cutoff, because they describe the whole version
        observations |= {"ridership_cutoff": v["ridership_cutoff"],
                         "excluded_after_ridership_cutoff": report["ridership"]["excluded_after_cutoff"]}
        details |= {"imported_at": v["imported_at"], "inputs": report["inputs"]}
    return envelope(
        v, cutoff_block(v, cutoff),
        observations=observations,
        schedule={"label": LABELS["scheduled_trips"], **sched,
                  "note": "dated GTFS schedules exist only for the analysis window; earlier dates have recorded "
                          "rides only, no dated schedule"},
        analysis_window={"start": v["analysis_start"], "end": p["b"]},
        archives=[{k: a[k] for k in a if k != "sha256"} for a in archives],
        matching={"ridership_rows_in_window": in_window, "schedule_rows": sched["rows"],
                  "matched_rows": matched["rows"], "matched_dates": matched["dates"],
                  "matched_routes": matched["routes"],
                  "schedule_conditioned_coverage_pct":
                      round(100 * matched["rows"] / sched["rows"], 3) if sched["rows"] else None,
                  "ridership_without_schedule": no_sched, "schedule_without_ridership": no_rides},
        quality={"import_identities": report["identities"],
                 "import_identities_hold": all(x == 0 for x in report["identities"].values()),
                 "note": "identities were checked on the whole version at import; they are violation counts (0)"},
        details=details,
    )
