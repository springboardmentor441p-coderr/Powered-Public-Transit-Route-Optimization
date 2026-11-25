"""
AI_RouteRanker - GTFS Relational Ingestion Pipeline
Ingests, validates, and partitions 8 historical GTFS snapshots using DuckDB.
Handles GTFS times >= 24:00:00, preserves leading zeros in identifiers,
performs primary key and foreign key audits, and persists Parquet and DuckDB tables.
Complies with Milestone 3.1 specifications.
"""

import datetime
import os
import time
from typing import Dict, List, Optional, Set, Tuple
import duckdb

SNAPSHOT_EFFECTIVE_WINDOWS: List[Dict[str, str]] = [
    {
        "snapshot_id": "mdb-389-202511230128",
        "effective_start": "2025-11-23",
        "effective_end": "2025-12-18",
        "archive_label": "November 23, 2025",
    },
    {
        "snapshot_id": "mdb-389-202512190112",
        "effective_start": "2025-12-19",
        "effective_end": "2026-01-07",
        "archive_label": "December 19, 2025",
    },
    {
        "snapshot_id": "mdb-389-202601080131",
        "effective_start": "2026-01-08",
        "effective_end": "2026-02-09",
        "archive_label": "January 8, 2026",
    },
    {
        "snapshot_id": "mdb-389-202602100132",
        "effective_start": "2026-02-10",
        "effective_end": "2026-03-25",
        "archive_label": "February 10, 2026",
    },
    {
        "snapshot_id": "mdb-389-202603260020",
        "effective_start": "2026-03-26",
        "effective_end": "2026-04-23",
        "archive_label": "March 26, 2026",
    },
    {
        "snapshot_id": "mdb-389-202604240144",
        "effective_start": "2026-04-24",
        "effective_end": "2026-05-29",
        "archive_label": "April 24, 2026",
    },
    {
        "snapshot_id": "mdb-389-202605300003",
        "effective_start": "2026-05-30",
        "effective_end": "2026-07-10",
        "archive_label": "May 30, 2026",
    },
    {
        "snapshot_id": "mdb-389-202607110020",
        "effective_start": "2026-07-11",
        "effective_end": "2026-07-31",
        "archive_label": "July 11, 2026",
    },
]


def get_csv_columns(filepath: str) -> Set[str]:
    """Read the header line of a CSV/TXT file and return normalized column names."""
    if not os.path.exists(filepath):
        return set()
    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
        header = f.readline().strip()
        return {c.strip().strip('"').strip("'") for c in header.split(",") if c.strip()}


class GTFSIngestionPipeline:
    """
    Manages end-to-end ingestion of multi-snapshot GTFS archives into DuckDB.
    Maintains strict memory limits suited for 8 GB RAM developer laptops.
    """

    def __init__(
        self,
        gtfs_raw_dir: str = os.path.join("data", "raw", "gtfs"),
        output_dir: str = os.path.join("data", "processed", "gtfs"),
        db_path: str = os.path.join("data", "processed", "ai_routeranker.duckdb"),
        memory_limit: str = "4GB",
    ):
        self.gtfs_raw_dir = gtfs_raw_dir
        self.output_dir = output_dir
        self.db_path = db_path
        self.memory_limit = memory_limit
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.con = duckdb.connect(db_path)
        self.con.execute(f"SET max_memory = '{memory_limit}';")
        self.con.execute("SET preserve_insertion_order = false;")
        self.con.execute("CREATE SCHEMA IF NOT EXISTS analytical;")

    def initialize_tables(self):
        """Create empty consolidated analytical GTFS tables if not already existing."""
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS analytical.gtfs_snapshots (
                snapshot_id VARCHAR PRIMARY KEY,
                effective_start_date DATE,
                effective_end_date DATE,
                archive_label VARCHAR,
                ingestion_timestamp TIMESTAMP,
                agency_count BIGINT,
                routes_count BIGINT,
                trips_count BIGINT,
                stops_count BIGINT,
                stop_times_count BIGINT,
                calendar_count BIGINT,
                calendar_dates_count BIGINT,
                shapes_count BIGINT,
                pk_integrity_passed BOOLEAN,
                fk_integrity_passed BOOLEAN,
                status VARCHAR
            );
        """)

        # Clean/recreate tables if restarting ingestion
        tables = [
            "gtfs_agency",
            "gtfs_routes",
            "gtfs_trips",
            "gtfs_stops",
            "gtfs_stop_times",
            "gtfs_calendar",
            "gtfs_calendar_dates",
            "gtfs_frequencies",
            "gtfs_shapes",
        ]
        for tbl in tables:
            self.con.execute(f"DROP TABLE IF EXISTS analytical.{tbl};")

        self.con.execute("""
            CREATE TABLE analytical.gtfs_agency (
                snapshot_id VARCHAR,
                agency_id VARCHAR,
                agency_name VARCHAR,
                agency_url VARCHAR,
                agency_timezone VARCHAR,
                agency_lang VARCHAR,
                agency_phone VARCHAR,
                agency_fare_url VARCHAR
            );

            CREATE TABLE analytical.gtfs_routes (
                snapshot_id VARCHAR,
                route_id VARCHAR,
                agency_id VARCHAR,
                route_short_name VARCHAR,
                route_long_name VARCHAR,
                route_desc VARCHAR,
                route_type INTEGER,
                route_url VARCHAR,
                route_color VARCHAR,
                route_text_color VARCHAR
            );

            CREATE TABLE analytical.gtfs_trips (
                snapshot_id VARCHAR,
                route_id VARCHAR,
                service_id VARCHAR,
                trip_id VARCHAR,
                trip_headsign VARCHAR,
                direction_id INTEGER,
                block_id VARCHAR,
                shape_id VARCHAR,
                wheelchair_accessible INTEGER
            );

            CREATE TABLE analytical.gtfs_stops (
                snapshot_id VARCHAR,
                stop_id VARCHAR,
                stop_code VARCHAR,
                stop_name VARCHAR,
                stop_desc VARCHAR,
                stop_lat DOUBLE,
                stop_lon DOUBLE,
                location_type INTEGER,
                parent_station VARCHAR,
                wheelchair_boarding INTEGER
            );

            CREATE TABLE analytical.gtfs_stop_times (
                snapshot_id VARCHAR,
                trip_id VARCHAR,
                arrival_time VARCHAR,
                departure_time VARCHAR,
                arrival_seconds INTEGER,
                departure_seconds INTEGER,
                stop_id VARCHAR,
                stop_sequence INTEGER,
                stop_headsign VARCHAR,
                pickup_type INTEGER,
                drop_off_type INTEGER,
                shape_dist_traveled DOUBLE,
                timepoint INTEGER
            );

            CREATE TABLE analytical.gtfs_calendar (
                snapshot_id VARCHAR,
                service_id VARCHAR,
                monday INTEGER,
                tuesday INTEGER,
                wednesday INTEGER,
                thursday INTEGER,
                friday INTEGER,
                saturday INTEGER,
                sunday INTEGER,
                start_date DATE,
                end_date DATE
            );

            CREATE TABLE analytical.gtfs_calendar_dates (
                snapshot_id VARCHAR,
                service_id VARCHAR,
                date DATE,
                exception_type INTEGER
            );

            CREATE TABLE analytical.gtfs_frequencies (
                snapshot_id VARCHAR,
                trip_id VARCHAR,
                start_time VARCHAR,
                end_time VARCHAR,
                headway_secs INTEGER,
                exact_times INTEGER
            );

            CREATE TABLE analytical.gtfs_shapes (
                snapshot_id VARCHAR,
                shape_id VARCHAR,
                shape_pt_lat DOUBLE,
                shape_pt_lon DOUBLE,
                shape_pt_sequence INTEGER,
                shape_dist_traveled DOUBLE
            );
        """)

    def ingest_single_snapshot(self, snapshot_meta: Dict[str, str]) -> Dict[str, object]:
        """Ingest one extracted GTFS archive into DuckDB and export to Parquet."""
        snapshot_id = snapshot_meta["snapshot_id"]
        start_date = snapshot_meta["effective_start"]
        end_date = snapshot_meta["effective_end"]
        label = snapshot_meta["archive_label"]

        snapshot_dir = os.path.join(self.gtfs_raw_dir, snapshot_id, "extracted")
        snapshot_out_dir = os.path.join(self.output_dir, snapshot_id)
        os.makedirs(snapshot_out_dir, exist_ok=True)

        print(f"\n--- Ingesting Snapshot: {snapshot_id} ({label}) ---")
        t0 = time.time()

        # Helper to get normalized file path
        def gtfs_path(filename: str) -> str:
            return os.path.join(snapshot_dir, filename).replace(os.sep, "/")

        # 1. Agency
        self.con.execute(f"""
            INSERT INTO analytical.gtfs_agency
            SELECT 
                '{snapshot_id}' AS snapshot_id,
                CAST(src.agency_id AS VARCHAR) AS agency_id,
                CAST(src.agency_name AS VARCHAR) AS agency_name,
                CAST(src.agency_url AS VARCHAR) AS agency_url,
                CAST(src.agency_timezone AS VARCHAR) AS agency_timezone,
                CAST(src.agency_lang AS VARCHAR) AS agency_lang,
                CAST(src.agency_phone AS VARCHAR) AS agency_phone,
                CAST(src.agency_fare_url AS VARCHAR) AS agency_fare_url
            FROM read_csv_auto('{gtfs_path("agency.txt")}', all_varchar=True) src;
        """)

        # 2. Routes (handle optional agency_id, route_desc, and route_url / route_rul typos across snapshots)
        routes_file = os.path.join(snapshot_dir, "routes.txt")
        r_cols = get_csv_columns(routes_file)
        agency_id_sql = "CAST(src.agency_id AS VARCHAR)" if "agency_id" in r_cols else "NULL"
        route_desc_sql = "CAST(src.route_desc AS VARCHAR)" if "route_desc" in r_cols else "NULL"
        
        if "route_url" in r_cols:
            route_url_sql = "CAST(src.route_url AS VARCHAR)"
        elif "route_rul" in r_cols:
            route_url_sql = "CAST(src.route_rul AS VARCHAR)"
        else:
            route_url_sql = "NULL"

        route_color_sql = "CAST(src.route_color AS VARCHAR)" if "route_color" in r_cols else "NULL"
        route_text_color_sql = "CAST(src.route_text_color AS VARCHAR)" if "route_text_color" in r_cols else "NULL"

        self.con.execute(f"""
            INSERT INTO analytical.gtfs_routes
            SELECT 
                '{snapshot_id}' AS snapshot_id,
                CAST(src.route_id AS VARCHAR) AS route_id,
                {agency_id_sql} AS agency_id,
                CAST(src.route_short_name AS VARCHAR) AS route_short_name,
                CAST(src.route_long_name AS VARCHAR) AS route_long_name,
                {route_desc_sql} AS route_desc,
                try_cast(src.route_type AS INTEGER) AS route_type,
                {route_url_sql} AS route_url,
                {route_color_sql} AS route_color,
                {route_text_color_sql} AS route_text_color
            FROM read_csv_auto('{gtfs_path("routes.txt")}', all_varchar=True) src;
        """)

        # 3. Calendar
        self.con.execute(f"""
            INSERT INTO analytical.gtfs_calendar
            SELECT 
                '{snapshot_id}' AS snapshot_id,
                CAST(src.service_id AS VARCHAR) AS service_id,
                try_cast(src.monday AS INTEGER) AS monday,
                try_cast(src.tuesday AS INTEGER) AS tuesday,
                try_cast(src.wednesday AS INTEGER) AS wednesday,
                try_cast(src.thursday AS INTEGER) AS thursday,
                try_cast(src.friday AS INTEGER) AS friday,
                try_cast(src.saturday AS INTEGER) AS saturday,
                try_cast(src.sunday AS INTEGER) AS sunday,
                try_strptime(trim(CAST(src.start_date AS VARCHAR)), '%Y%m%d')::DATE AS start_date,
                try_strptime(trim(CAST(src.end_date AS VARCHAR)), '%Y%m%d')::DATE AS end_date
            FROM read_csv_auto('{gtfs_path("calendar.txt")}', all_varchar=True) src;
        """)

        # 4. Calendar Dates
        self.con.execute(f"""
            INSERT INTO analytical.gtfs_calendar_dates
            SELECT 
                '{snapshot_id}' AS snapshot_id,
                CAST(src.service_id AS VARCHAR) AS service_id,
                try_strptime(trim(CAST(src.date AS VARCHAR)), '%Y%m%d')::DATE AS date,
                try_cast(src.exception_type AS INTEGER) AS exception_type
            FROM read_csv_auto('{gtfs_path("calendar_dates.txt")}', all_varchar=True) src;
        """)

        # 5. Trips (handle optional trip_headsign across snapshots)
        trips_file = os.path.join(snapshot_dir, "trips.txt")
        t_cols = get_csv_columns(trips_file)
        headsign_sql = "CAST(src.trip_headsign AS VARCHAR)" if "trip_headsign" in t_cols else "NULL"

        self.con.execute(f"""
            INSERT INTO analytical.gtfs_trips
            SELECT 
                '{snapshot_id}' AS snapshot_id,
                CAST(src.route_id AS VARCHAR) AS route_id,
                CAST(src.service_id AS VARCHAR) AS service_id,
                CAST(src.trip_id AS VARCHAR) AS trip_id,
                {headsign_sql} AS trip_headsign,
                try_cast(src.direction_id AS INTEGER) AS direction_id,
                CAST(src.block_id AS VARCHAR) AS block_id,
                CAST(src.shape_id AS VARCHAR) AS shape_id,
                try_cast(src.wheelchair_accessible AS INTEGER) AS wheelchair_accessible
            FROM read_csv_auto('{gtfs_path("trips.txt")}', all_varchar=True) src;
        """)

        # 6. Stops
        self.con.execute(f"""
            INSERT INTO analytical.gtfs_stops
            SELECT 
                '{snapshot_id}' AS snapshot_id,
                CAST(src.stop_id AS VARCHAR) AS stop_id,
                CAST(src.stop_code AS VARCHAR) AS stop_code,
                CAST(src.stop_name AS VARCHAR) AS stop_name,
                CAST(src.stop_desc AS VARCHAR) AS stop_desc,
                try_cast(src.stop_lat AS DOUBLE) AS stop_lat,
                try_cast(src.stop_lon AS DOUBLE) AS stop_lon,
                try_cast(src.location_type AS INTEGER) AS location_type,
                CAST(src.parent_station AS VARCHAR) AS parent_station,
                try_cast(src.wheelchair_boarding AS INTEGER) AS wheelchair_boarding
            FROM read_csv_auto('{gtfs_path("stops.txt")}', all_varchar=True) src;
        """)

        # 7. Stop Times (Compute seconds, handle >24h without wrapping)
        st_file = os.path.join(snapshot_dir, "stop_times.txt")
        st_cols = get_csv_columns(st_file)
        drop_off_sql = "try_cast(src.drop_off_type AS INTEGER)" if "drop_off_type" in st_cols else "NULL"
        timepoint_sql = "try_cast(src.timepoint AS INTEGER)" if "timepoint" in st_cols else "NULL"

        self.con.execute(f"""
            INSERT INTO analytical.gtfs_stop_times
            SELECT 
                '{snapshot_id}' AS snapshot_id,
                CAST(src.trip_id AS VARCHAR) AS trip_id,
                trim(CAST(src.arrival_time AS VARCHAR)) AS arrival_time,
                trim(CAST(src.departure_time AS VARCHAR)) AS departure_time,
                -- Convert HH:MM:SS directly to cumulative seconds
                (CAST(split_part(trim(CAST(src.arrival_time AS VARCHAR)), ':', 1) AS INTEGER) * 3600 +
                 CAST(split_part(trim(CAST(src.arrival_time AS VARCHAR)), ':', 2) AS INTEGER) * 60 +
                 CAST(split_part(trim(CAST(src.arrival_time AS VARCHAR)), ':', 3) AS INTEGER)) AS arrival_seconds,
                (CAST(split_part(trim(CAST(src.departure_time AS VARCHAR)), ':', 1) AS INTEGER) * 3600 +
                 CAST(split_part(trim(CAST(src.departure_time AS VARCHAR)), ':', 2) AS INTEGER) * 60 +
                 CAST(split_part(trim(CAST(src.departure_time AS VARCHAR)), ':', 3) AS INTEGER)) AS departure_seconds,
                CAST(src.stop_id AS VARCHAR) AS stop_id,
                try_cast(src.stop_sequence AS INTEGER) AS stop_sequence,
                CAST(src.stop_headsign AS VARCHAR) AS stop_headsign,
                try_cast(src.pickup_type AS INTEGER) AS pickup_type,
                {drop_off_sql} AS drop_off_type,
                try_cast(src.shape_dist_traveled AS DOUBLE) AS shape_dist_traveled,
                {timepoint_sql} AS timepoint
            FROM read_csv_auto('{gtfs_path("stop_times.txt")}', all_varchar=True) src;
        """)

        # 8. Frequencies (if present)
        freq_file = gtfs_path("frequencies.txt")
        freq_disk_path = os.path.join(snapshot_dir, "frequencies.txt")
        if os.path.exists(freq_disk_path):
            f_cols = get_csv_columns(freq_disk_path)
            exact_times_sql = "try_cast(src.exact_times AS INTEGER)" if "exact_times" in f_cols else "NULL"
            self.con.execute(f"""
                INSERT INTO analytical.gtfs_frequencies
                SELECT 
                    '{snapshot_id}' AS snapshot_id,
                    CAST(src.trip_id AS VARCHAR) AS trip_id,
                    CAST(src.start_time AS VARCHAR) AS start_time,
                    CAST(src.end_time AS VARCHAR) AS end_time,
                    try_cast(src.headway_secs AS INTEGER) AS headway_secs,
                    {exact_times_sql} AS exact_times
                FROM read_csv_auto('{freq_file}', all_varchar=True) src;
            """)

        # 9. Shapes
        shape_file = gtfs_path("shapes.txt")
        if os.path.exists(os.path.join(snapshot_dir, "shapes.txt")):
            self.con.execute(f"""
                INSERT INTO analytical.gtfs_shapes
                SELECT 
                    '{snapshot_id}' AS snapshot_id,
                    CAST(src.shape_id AS VARCHAR) AS shape_id,
                    try_cast(src.shape_pt_lat AS DOUBLE) AS shape_pt_lat,
                    try_cast(src.shape_pt_lon AS DOUBLE) AS shape_pt_lon,
                    try_cast(src.shape_pt_sequence AS INTEGER) AS shape_pt_sequence,
                    try_cast(src.shape_dist_traveled AS DOUBLE) AS shape_dist_traveled
                FROM read_csv_auto('{shape_file}', all_varchar=True) src;
            """)

        # --- Integrity Audits ---
        # PK Checks
        dup_routes = self.con.execute(f"SELECT COUNT(*) - COUNT(DISTINCT route_id) FROM analytical.gtfs_routes WHERE snapshot_id = '{snapshot_id}'").fetchone()[0]
        dup_trips = self.con.execute(f"SELECT COUNT(*) - COUNT(DISTINCT trip_id) FROM analytical.gtfs_trips WHERE snapshot_id = '{snapshot_id}'").fetchone()[0]
        dup_stops = self.con.execute(f"SELECT COUNT(*) - COUNT(DISTINCT stop_id) FROM analytical.gtfs_stops WHERE snapshot_id = '{snapshot_id}'").fetchone()[0]
        pk_passed = (dup_routes == 0 and dup_trips == 0 and dup_stops == 0)

        # FK Checks
        # Orphan trips (trip.route_id not in routes)
        orphan_trips = self.con.execute(f"""
            SELECT COUNT(*) 
            FROM analytical.gtfs_trips t
            LEFT JOIN analytical.gtfs_routes r
                ON t.snapshot_id = r.snapshot_id AND t.route_id = r.route_id
            WHERE t.snapshot_id = '{snapshot_id}' AND r.route_id IS NULL;
        """).fetchone()[0]

        # Orphan stop_times (stop_times.stop_id not in stops)
        orphan_stop_times_stop = self.con.execute(f"""
            SELECT COUNT(*) 
            FROM analytical.gtfs_stop_times st
            LEFT JOIN analytical.gtfs_stops s
                ON st.snapshot_id = s.snapshot_id AND st.stop_id = s.stop_id
            WHERE st.snapshot_id = '{snapshot_id}' AND s.stop_id IS NULL;
        """).fetchone()[0]

        fk_passed = (orphan_trips == 0 and orphan_stop_times_stop == 0)

        # Record counts
        counts = self.con.execute(f"""
            SELECT 
                (SELECT COUNT(*) FROM analytical.gtfs_agency WHERE snapshot_id = '{snapshot_id}') AS agency,
                (SELECT COUNT(*) FROM analytical.gtfs_routes WHERE snapshot_id = '{snapshot_id}') AS routes,
                (SELECT COUNT(*) FROM analytical.gtfs_trips WHERE snapshot_id = '{snapshot_id}') AS trips,
                (SELECT COUNT(*) FROM analytical.gtfs_stops WHERE snapshot_id = '{snapshot_id}') AS stops,
                (SELECT COUNT(*) FROM analytical.gtfs_stop_times WHERE snapshot_id = '{snapshot_id}') AS stop_times,
                (SELECT COUNT(*) FROM analytical.gtfs_calendar WHERE snapshot_id = '{snapshot_id}') AS calendar,
                (SELECT COUNT(*) FROM analytical.gtfs_calendar_dates WHERE snapshot_id = '{snapshot_id}') AS calendar_dates,
                (SELECT COUNT(*) FROM analytical.gtfs_shapes WHERE snapshot_id = '{snapshot_id}') AS shapes;
        """).fetchone()

        status_str = "VALID" if (pk_passed and fk_passed) else "INTEGRITY_WARNING"

        # Update gtfs_snapshots table
        self.con.execute(f"""
            DELETE FROM analytical.gtfs_snapshots WHERE snapshot_id = '{snapshot_id}';
            INSERT INTO analytical.gtfs_snapshots VALUES (
                '{snapshot_id}',
                '{start_date}',
                '{end_date}',
                '{label}',
                CURRENT_TIMESTAMP,
                {counts[0]},
                {counts[1]},
                {counts[2]},
                {counts[3]},
                {counts[4]},
                {counts[5]},
                {counts[6]},
                {counts[7]},
                {pk_passed},
                {fk_passed},
                '{status_str}'
            );
        """)

        # Export individual snapshot Parquet files
        snap_out_sql = snapshot_out_dir.replace(os.sep, "/")
        self.con.execute(f"COPY (SELECT * FROM analytical.gtfs_routes WHERE snapshot_id = '{snapshot_id}') TO '{snap_out_sql}/routes.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);")
        self.con.execute(f"COPY (SELECT * FROM analytical.gtfs_trips WHERE snapshot_id = '{snapshot_id}') TO '{snap_out_sql}/trips.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);")
        self.con.execute(f"COPY (SELECT * FROM analytical.gtfs_stops WHERE snapshot_id = '{snapshot_id}') TO '{snap_out_sql}/stops.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);")
        self.con.execute(f"COPY (SELECT * FROM analytical.gtfs_calendar WHERE snapshot_id = '{snapshot_id}') TO '{snap_out_sql}/calendar.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);")
        self.con.execute(f"COPY (SELECT * FROM analytical.gtfs_calendar_dates WHERE snapshot_id = '{snapshot_id}') TO '{snap_out_sql}/calendar_dates.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);")

        elapsed = time.time() - t0
        print(f"  Completed in {elapsed:.2f}s | Routes: {counts[1]:,} | Trips: {counts[2]:,} | Stops: {counts[3]:,} | StopTimes: {counts[4]:,} | PK Valid: {pk_passed} | FK Valid: {fk_passed}")

        return {
            "snapshot_id": snapshot_id,
            "label": label,
            "start_date": start_date,
            "end_date": end_date,
            "agency_count": counts[0],
            "routes_count": counts[1],
            "trips_count": counts[2],
            "stops_count": counts[3],
            "stop_times_count": counts[4],
            "calendar_count": counts[5],
            "calendar_dates_count": counts[6],
            "shapes_count": counts[7],
            "pk_passed": pk_passed,
            "fk_passed": fk_passed,
            "status": status_str,
            "elapsed_seconds": elapsed,
        }

    def ingest_all_snapshots(self) -> List[Dict[str, object]]:
        """Ingest all eight snapshots sequentially."""
        self.initialize_tables()
        results = []
        for s in SNAPSHOT_EFFECTIVE_WINDOWS:
            res = self.ingest_single_snapshot(s)
            results.append(res)
        return results

    def close(self):
        """Close connection."""
        self.con.close()
