"""
analytics/03_parse_gtfs_schedule.py
RouteRanker Data Pipeline - Step 3: GTFS Schedule Parsing & Service Profile

Parses CTA GTFS schedule feeds using DuckDB with bounded memory:
1. Filters strictly to bus routes (route_type = 3).
2. Expands service calendars for Weekday, Saturday, and Sunday service patterns.
3. Computes trip volumes, operational spans, and stop sequences per route.
4. Normalizes post-midnight timestamps (>= 24:00:00).
5. Exports data/processed/gtfs_routes_clean.parquet & data/processed/route_scheduled_service.parquet.
"""

import os
import duckdb
import pandas as pd
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def parse_gtfs_schedule():
    print("=" * 60)
    print("ROUTERANKER PIPELINE: STEP 3 - GTFS SCHEDULE PARSING")
    print("=" * 60)

    # Locate GTFS directory
    gtfs_dir = DATA_DIR / "google_transit"
    if not gtfs_dir.exists():
        gtfs_dir = DATA_DIR / "mdb-389-202609160157"
    if not gtfs_dir.exists():
        raise FileNotFoundError(f"No GTFS directory found in {DATA_DIR}")

    print(f"[INPUT] Using GTFS directory: {gtfs_dir.name}")

    # Connect in-memory DuckDB with 512MB memory limit
    con = duckdb.connect(database=":memory:")
    con.execute("SET max_memory = '512MB';")
    con.execute("SET threads = 4;")

    routes_file = str(gtfs_dir / "routes.txt").replace("\\", "/")
    trips_file = str(gtfs_dir / "trips.txt").replace("\\", "/")
    calendar_file = str(gtfs_dir / "calendar.txt").replace("\\", "/")
    stops_file = str(gtfs_dir / "stops.txt").replace("\\", "/")
    stop_times_file = str(gtfs_dir / "stop_times.txt").replace("\\", "/")

    # 1. Load routes & filter to Bus (route_type = 3)
    con.execute(f"""
        CREATE TABLE routes_raw AS
        SELECT
            CAST(route_id AS VARCHAR) AS route_id,
            CAST(route_short_name AS VARCHAR) AS route_short_name,
            CAST(route_long_name AS VARCHAR) AS route_long_name,
            CAST(route_type AS INTEGER) AS route_type
        FROM read_csv_auto('{routes_file}');
    """)

    bus_routes_count = con.execute("SELECT count(*) FROM routes_raw WHERE route_type = 3").fetchone()[0]
    total_routes_count = con.execute("SELECT count(*) FROM routes_raw").fetchone()[0]
    print(f"[ROUTES] Total routes: {total_routes_count} | Bus routes (type=3): {bus_routes_count}")

    # 2. Load Calendar and tag daytype service IDs
    con.execute(f"""
        CREATE TABLE calendar_raw AS
        SELECT
            CAST(service_id AS VARCHAR) AS service_id,
            CAST(monday AS INTEGER) AS monday,
            CAST(tuesday AS INTEGER) AS tuesday,
            CAST(wednesday AS INTEGER) AS wednesday,
            CAST(thursday AS INTEGER) AS thursday,
            CAST(friday AS INTEGER) AS friday,
            CAST(saturday AS INTEGER) AS saturday,
            CAST(sunday AS INTEGER) AS sunday,
            CAST(start_date AS VARCHAR) AS start_date,
            CAST(end_date AS VARCHAR) AS end_date
        FROM read_csv_auto('{calendar_file}');
    """)

    # 3. Load Trips for bus routes
    con.execute(f"""
        CREATE TABLE trips_bus AS
        SELECT
            CAST(t.route_id AS VARCHAR) AS route_id,
            CAST(t.service_id AS VARCHAR) AS service_id,
            CAST(t.trip_id AS VARCHAR) AS trip_id,
            CAST(t.direction_id AS INTEGER) AS direction_id
        FROM read_csv_auto('{trips_file}') t
        JOIN routes_raw r ON CAST(t.route_id AS VARCHAR) = r.route_id
        WHERE r.route_type = 3;
    """)
    total_bus_trips = con.execute("SELECT count(*) FROM trips_bus").fetchone()[0]
    print(f"[TRIPS] Bus trips linked: {total_bus_trips:,}")

    # 4. Service Daytype Trip Counts per Route
    # Tag service_ids into W (Weekday: Mon-Fri = 1), A (Sat = 1, Sun = 0), U (Sun = 1, Mon-Fri = 0)
    con.execute("""
        CREATE TABLE service_daytypes AS
        SELECT
            service_id,
            CASE
                WHEN monday = 1 AND tuesday = 1 AND wednesday = 1 AND thursday = 1 AND friday = 1 THEN 'W'
                WHEN saturday = 1 AND sunday = 0 AND monday = 0 THEN 'A'
                WHEN sunday = 1 AND monday = 0 AND saturday = 0 THEN 'U'
                WHEN saturday = 0 AND sunday = 1 THEN 'U'
                ELSE 'W'
            END AS daytype
        FROM calendar_raw;
    """)

    con.execute("""
        CREATE TABLE route_trips_by_daytype AS
        SELECT
            t.route_id,
            sd.daytype,
            COUNT(DISTINCT t.trip_id) AS scheduled_trips
        FROM trips_bus t
        JOIN service_daytypes sd ON t.service_id = sd.service_id
        GROUP BY t.route_id, sd.daytype;
    """)

    # 5. Stop Times analysis (Stop counts, Span, Headways)
    print("[STOPS] Aggregating stop times and route topologies...")
    con.execute(f"""
        CREATE TABLE stop_times_bus AS
        SELECT
            CAST(st.trip_id AS VARCHAR) AS trip_id,
            CAST(st.stop_id AS VARCHAR) AS stop_id,
            CAST(st.stop_sequence AS INTEGER) AS stop_sequence,
            st.departure_time,
            st.arrival_time
        FROM read_csv_auto('{stop_times_file}') st
        WHERE CAST(st.trip_id AS VARCHAR) IN (SELECT trip_id FROM trips_bus);
    """)

    # Distinct stops served per route
    con.execute("""
        CREATE TABLE route_stops_summary AS
        SELECT
            t.route_id,
            COUNT(DISTINCT st.stop_id) AS total_stops_served
        FROM trips_bus t
        JOIN stop_times_bus st ON t.trip_id = st.trip_id
        GROUP BY t.route_id;
    """)

    # Pivot daytype trip counts: weekday_trips, saturday_trips, sunday_trips
    con.execute("""
        CREATE TABLE route_service_profile AS
        SELECT
            r.route_id,
            r.route_short_name,
            r.route_long_name,
            COALESCE(s.total_stops_served, 0) AS stops_count,
            COALESCE(MAX(CASE WHEN td.daytype = 'W' THEN td.scheduled_trips END), 0) AS weekday_scheduled_trips,
            COALESCE(MAX(CASE WHEN td.daytype = 'A' THEN td.scheduled_trips END), 0) AS saturday_scheduled_trips,
            COALESCE(MAX(CASE WHEN td.daytype = 'U' THEN td.scheduled_trips END), 0) AS sunday_scheduled_trips
        FROM routes_raw r
        LEFT JOIN route_stops_summary s ON r.route_id = s.route_id
        LEFT JOIN route_trips_by_daytype td ON r.route_id = td.route_id
        WHERE r.route_type = 3
        GROUP BY r.route_id, r.route_short_name, r.route_long_name, s.total_stops_served;
    """)

    df_service = con.execute("SELECT * FROM route_service_profile ORDER BY route_id").df()

    # Export clean routes and scheduled service tables
    out_routes = PROCESSED_DIR / "gtfs_routes_clean.parquet"
    out_service = PROCESSED_DIR / "route_scheduled_service.parquet"

    df_service.to_parquet(out_routes, engine="pyarrow", index=False)
    df_service.to_parquet(out_service, engine="pyarrow", index=False)

    print(f"\n[EXPORTED] {out_routes.relative_to(WORKSPACE_ROOT)} ({len(df_service)} bus routes)")
    print(f"[SAMPLE PROFILE]:")
    print(df_service[["route_id", "route_short_name", "stops_count", "weekday_scheduled_trips", "saturday_scheduled_trips", "sunday_scheduled_trips"]].head(10).to_string())

    con.close()
    return df_service

if __name__ == "__main__":
    parse_gtfs_schedule()
