"""Step 13: trip durations and daily scheduled service per route/date (spec 9.5.2, 9.6.3).

- GTFS times are ELAPSED seconds since the service day's noon-minus-12h; "25:10:00" = 90,600 s and stays
  on its original service date. They are never wrapped with a clock-time parser.
- Trip duration = arrival at the LAST stop (max stop_sequence) - departure at the FIRST stop (min stop_sequence).
  Valid only if both endpoint times exist, the trip has >= 2 stop events, every stop_sequence parses, and
  last arrival >= first departure.
- scheduled_trips counts every active trip (even with a missing duration);
  scheduled_service_hours = sum(durations)/3600 ONLY if every included duration is valid, else missing.
"""
from __future__ import annotations

import re

import duckdb
import pandas as pd

TIME_RE = r"^\d{1,3}:[0-5]\d:[0-5]\d$"  # values are already trimmed by gtfs_tables


class DuplicateActiveTripError(ValueError):
    pass


def parse_gtfs_time(t: str | None) -> int | None:
    """Python twin of the SQL macro below (used in tests and docs): 'H:MM:SS' -> elapsed seconds."""
    if t is None:
        return None
    t = t.strip()
    if not re.match(TIME_RE, t):
        return None
    h, m, s = (int(x) for x in t.split(":"))
    return h * 3600 + m * 60 + s


def build_trip_durations(con: duckdb.DuckDBPyConnection) -> None:
    """Create TEMP TABLE trip_dur(trip_id, n_events, first_dep_s, last_arr_s, duration_s, duration_valid, reason)."""
    con.execute(f"""
        CREATE OR REPLACE TEMP MACRO gtfs_secs(t) AS CASE WHEN regexp_matches(coalesce(t, ''), '{TIME_RE}') THEN
            cast(split_part(t, ':', 1) AS INTEGER) * 3600 + cast(split_part(t, ':', 2) AS INTEGER) * 60
            + cast(split_part(t, ':', 3) AS INTEGER) END""")
    con.execute("""
        CREATE OR REPLACE TEMP TABLE trip_dur AS
        WITH st AS (
            SELECT trip_id, try_cast(stop_sequence AS INTEGER) AS seq,
                   gtfs_secs(arrival_time) AS arr, gtfs_secs(departure_time) AS dep
            FROM stop_times),
        b AS (SELECT trip_id, count(*) AS n_events, count(seq) AS n_seq, min(seq) AS mn, max(seq) AS mx
              FROM st GROUP BY trip_id),
        ends AS (SELECT trip_id, seq, any_value(dep) AS dep, any_value(arr) AS arr, count(*) AS k
                 FROM st GROUP BY trip_id, seq),
        e AS (
            SELECT b.trip_id, b.n_events, b.n_seq, f.dep AS first_dep_s, l.arr AS last_arr_s,
                   f.k AS k_first, l.k AS k_last
            FROM b
            LEFT JOIN ends f ON f.trip_id = b.trip_id AND f.seq = b.mn   -- first stop row
            LEFT JOIN ends l ON l.trip_id = b.trip_id AND l.seq = b.mx)  -- last stop row
        SELECT trip_id, n_events, first_dep_s, last_arr_s,
               CASE WHEN reason IS NULL THEN last_arr_s - first_dep_s END AS duration_s,
               reason IS NULL AS duration_valid, reason
        FROM (SELECT *, CASE
                WHEN n_seq < n_events THEN 'unparseable_stop_sequence'
                WHEN n_events < 2 THEN 'fewer_than_two_stop_events'
                WHEN k_first > 1 OR k_last > 1 THEN 'duplicate_endpoint_sequence'
                WHEN first_dep_s IS NULL THEN 'missing_first_departure'
                WHEN last_arr_s IS NULL THEN 'missing_last_arrival'
                WHEN last_arr_s < first_dep_s THEN 'last_arrival_before_first_departure'
              END AS reason FROM e)""")


def daily_service(con: duckdb.DuckDBPyConnection, snapshot_id: str, active: pd.DataFrame) -> pd.DataFrame:
    """Route/date scheduled service for the given (date, service_id) pairs of ONE snapshot.

    Requires TEMP TABLEs bus_cw (gtfs_tables.bus_crosswalk) and trip_dur (build_trip_durations).
    Trips with no stop_times are counted with an invalid duration ('no_stop_times').
    """
    con.register("_active", active)
    try:
        con.execute("""
            CREATE OR REPLACE TEMP TABLE active_trips AS
            SELECT a.date, cw.route, cw.route_id, t.trip_id, t.service_id,
                   d.duration_s, coalesce(d.duration_valid, false) AS duration_valid,
                   coalesce(d.reason, 'no_stop_times') AS reason
            FROM _active a
            JOIN trips t ON t.service_id = a.service_id
            JOIN bus_cw cw ON cw.route_id = t.route_id
            LEFT JOIN trip_dur d ON d.trip_id = t.trip_id""")
    finally:
        con.unregister("_active")
    dup = con.execute("SELECT count(*) - count(DISTINCT (date, trip_id)) FROM active_trips").fetchone()[0]
    if dup:
        raise DuplicateActiveTripError(f"{snapshot_id}: {dup} duplicated (date, trip_id) active trips")
    out = con.execute("""
        SELECT route, date, any_value(route_id) AS route_id,
               count(*) AS scheduled_trips,
               CASE WHEN bool_and(duration_valid) THEN round(sum(duration_s) / 3600.0, 6) END AS scheduled_service_hours,
               bool_and(duration_valid) AS duration_complete,
               count(*) FILTER (WHERE NOT duration_valid) AS trips_missing_duration
        FROM active_trips GROUP BY route, date ORDER BY route, date""").df()
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out["scheduled_service_hours"] = out["scheduled_service_hours"].astype("Float64")
    out["trips_missing_duration"] = out["trips_missing_duration"].astype("Int64")
    out["scheduled_trips"] = out["scheduled_trips"].astype("Int64")
    out.insert(0, "snapshot_id", snapshot_id)
    return out


def bus_trips_per_date(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Active bus trips per date in the last daily_service() call (dates with 0 are absent -> gaps)."""
    df = con.execute("SELECT date, count(*) AS active_bus_trips FROM active_trips GROUP BY date").df()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def invalid_duration_summary(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    rows = con.execute("SELECT reason, count(*) FROM active_trips WHERE NOT duration_valid GROUP BY 1").fetchall()
    return {r: int(n) for r, n in rows}
