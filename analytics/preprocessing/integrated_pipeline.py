"""
AI_RouteRanker - Integrated Analytical Pipeline
Builds integrated dimension and fact tables in DuckDB and exports Parquet datasets:
1. snapshot_metadata.parquet
2. route_mapping.parquet
3. gtfs_route_dim.parquet
4. daily_ridership.parquet
5. historical_schedule_match.parquet

Complies with Milestone 3.1 specifications.
"""

import datetime
import os
import time
from typing import Dict, List, Optional
import duckdb
import pandas as pd

from analytics.preprocessing.route_mapper import RouteIdentifierMapper


class IntegratedAnalyticalPipeline:
    """
    Coordinates creation and persistence of all Milestone 3.1 integrated tables:
    - Snapshot Metadata
    - Route Mapping Matrix
    - GTFS Route Dimension
    - Daily Ridership with GTFS Window flags
    - Historical Schedule Matching
    """

    def __init__(
        self,
        db_path: str = os.path.join("data", "processed", "ai_routeranker.duckdb"),
        integrated_dir: str = os.path.join("data", "processed", "integrated"),
        memory_limit: str = "4GB",
    ):
        self.db_path = db_path
        self.integrated_dir = integrated_dir
        self.memory_limit = memory_limit
        os.makedirs(self.integrated_dir, exist_ok=True)

        self.con = duckdb.connect(self.db_path)
        self.con.execute(f"SET memory_limit = '{self.memory_limit}';")
        self.con.execute("SET preserve_insertion_order = false;")
        self.con.execute("CREATE SCHEMA IF NOT EXISTS analytical;")

    def close(self):
        """Safely close DuckDB connection."""
        if self.con:
            self.con.close()
            self.con = None

    def build_snapshot_metadata(self) -> pd.DataFrame:
        """
        Builds analytical.snapshot_metadata table and snapshot_metadata.parquet.
        Captures snapshot windows, checksums, and table record counts.
        """
        print("\n--- [1/5] Building Snapshot Metadata ---")
        t0 = time.time()

        # Query existing metadata table and enrich
        df = self.con.execute("""
            SELECT 
                snapshot_id,
                archive_label,
                effective_start_date,
                effective_end_date,
                ingestion_timestamp,
                agency_count,
                routes_count,
                trips_count,
                stops_count,
                stop_times_count,
                calendar_count,
                calendar_dates_count,
                shapes_count,
                pk_integrity_passed,
                fk_integrity_passed,
                status
            FROM analytical.gtfs_snapshots
            ORDER BY effective_start_date ASC;
        """).df()

        # Persist to DuckDB table
        self.con.execute("DROP TABLE IF EXISTS analytical.snapshot_metadata;")
        self.con.execute("""
            CREATE TABLE analytical.snapshot_metadata AS 
            SELECT * FROM df;
        """)

        # Export to Parquet
        parquet_path = os.path.join(self.integrated_dir, "snapshot_metadata.parquet")
        self.con.execute(f"COPY analytical.snapshot_metadata TO '{parquet_path.replace(os.sep, '/')}' (FORMAT PARQUET, COMPRESSION ZSTD);")

        elapsed = time.time() - t0
        print(f"  Snapshot metadata built: {len(df)} snapshots in {elapsed:.2f}s -> {parquet_path}")
        return df

    def build_route_mapping(self) -> pd.DataFrame:
        """
        Builds analytical.route_mapping and route_mapping.parquet.
        Executes RouteIdentifierMapper cross-matching ridership routes against GTFS.
        """
        print("\n--- [2/5] Building Route Mapping Matrix ---")
        t0 = time.time()

        mapper = RouteIdentifierMapper(self.con)
        mapping_df = mapper.compute_route_mappings()

        # Persist to DuckDB table
        self.con.register("temp_route_mapping_df", mapping_df)
        self.con.execute("DROP TABLE IF EXISTS analytical.route_mapping;")
        self.con.execute("""
            CREATE TABLE analytical.route_mapping AS 
            SELECT * FROM temp_route_mapping_df;
        """)
        self.con.unregister("temp_route_mapping_df")

        # Export to Parquet
        parquet_path = os.path.join(self.integrated_dir, "route_mapping.parquet")
        self.con.execute(f"COPY analytical.route_mapping TO '{parquet_path.replace(os.sep, '/')}' (FORMAT PARQUET, COMPRESSION ZSTD);")

        status_counts = mapping_df["match_status"].value_counts().to_dict()
        elapsed = time.time() - t0
        print(f"  Route mapping built: {len(mapping_df)} route-snapshot pairs in {elapsed:.2f}s -> {parquet_path}")
        print(f"  Match distribution: {status_counts}")
        return mapping_df

    def build_gtfs_route_dim(self) -> pd.DataFrame:
        """
        Builds analytical.gtfs_route_dim and gtfs_route_dim.parquet.
        Aggregates route dimension across snapshots with trip and stop counts.
        """
        print("\n--- [3/5] Building GTFS Route Dimension ---")
        t0 = time.time()

        self.con.execute("DROP TABLE IF EXISTS analytical.gtfs_route_dim;")
        self.con.execute("""
            CREATE TABLE analytical.gtfs_route_dim AS
            WITH route_trips AS (
                SELECT 
                    snapshot_id,
                    route_id,
                    COUNT(trip_id) AS total_trips
                FROM analytical.gtfs_trips
                GROUP BY snapshot_id, route_id
            ),
            route_stops AS (
                SELECT 
                    t.snapshot_id,
                    t.route_id,
                    COUNT(DISTINCT st.stop_id) AS distinct_stops_count
                FROM analytical.gtfs_trips t
                JOIN analytical.gtfs_stop_times st
                    ON t.snapshot_id = st.snapshot_id
                    AND t.trip_id = st.trip_id
                GROUP BY t.snapshot_id, t.route_id
            )
            SELECT 
                r.snapshot_id,
                r.route_id,
                r.route_short_name,
                r.route_long_name,
                r.route_type,
                r.route_url,
                r.route_color,
                r.route_text_color,
                COALESCE(rt.total_trips, 0) AS total_trips,
                COALESCE(rs.distinct_stops_count, 0) AS distinct_stops_count
            FROM analytical.gtfs_routes r
            LEFT JOIN route_trips rt
                ON r.snapshot_id = rt.snapshot_id
                AND r.route_id = rt.route_id
            LEFT JOIN route_stops rs
                ON r.snapshot_id = rs.snapshot_id
                AND r.route_id = rs.route_id
            ORDER BY r.snapshot_id, r.route_short_name;
        """)

        parquet_path = os.path.join(self.integrated_dir, "gtfs_route_dim.parquet")
        self.con.execute(f"COPY analytical.gtfs_route_dim TO '{parquet_path.replace(os.sep, '/')}' (FORMAT PARQUET, COMPRESSION ZSTD);")

        row_count = self.con.execute("SELECT count(*) FROM analytical.gtfs_route_dim").fetchone()[0]
        elapsed = time.time() - t0
        print(f"  GTFS route dimension built: {row_count} rows in {elapsed:.2f}s -> {parquet_path}")
        return self.con.execute("SELECT * FROM analytical.gtfs_route_dim").df()

    def build_daily_ridership(self) -> pd.DataFrame:
        """
        Builds analytical.daily_ridership and daily_ridership.parquet.
        Enriches clean CTA ridership with calendar features and GTFS snapshot window alignment.
        """
        print("\n--- [4/5] Building Daily Ridership Dimension ---")
        t0 = time.time()

        self.con.execute("DROP TABLE IF EXISTS analytical.daily_ridership;")
        self.con.execute("""
            CREATE TABLE analytical.daily_ridership AS
            SELECT 
                c.route,
                c.date,
                c.daytype,
                c.rides,
                dayname(c.date) AS day_of_week,
                dayofweek(c.date) AS day_of_week_int,
                CASE 
                    WHEN c.daytype IN ('A', 'U') OR dayname(c.date) IN ('Saturday', 'Sunday') THEN true 
                    ELSE false 
                END AS is_weekend,
                s.snapshot_id AS matched_snapshot_id,
                s.archive_label AS matched_snapshot_label,
                CASE WHEN s.snapshot_id IS NOT NULL THEN true ELSE false END AS in_gtfs_coverage
            FROM analytical.cta_ridership_clean c
            LEFT JOIN analytical.gtfs_snapshots s
                ON c.date >= s.effective_start_date 
                AND c.date <= s.effective_end_date
            ORDER BY c.date ASC, c.route ASC;
        """)

        parquet_path = os.path.join(self.integrated_dir, "daily_ridership.parquet")
        self.con.execute(f"COPY analytical.daily_ridership TO '{parquet_path.replace(os.sep, '/')}' (FORMAT PARQUET, COMPRESSION ZSTD);")

        total_rows = self.con.execute("SELECT count(*) FROM analytical.daily_ridership").fetchone()[0]
        coverage_rows = self.con.execute("SELECT count(*) FROM analytical.daily_ridership WHERE in_gtfs_coverage = true").fetchone()[0]
        elapsed = time.time() - t0
        print(f"  Daily ridership built: {total_rows:,} rows ({coverage_rows:,} in GTFS coverage) in {elapsed:.2f}s -> {parquet_path}")
        return self.con.execute("SELECT * FROM analytical.daily_ridership LIMIT 100").df()

    def build_historical_schedule_match(self) -> pd.DataFrame:
        """
        Builds analytical.historical_schedule_match and historical_schedule_match.parquet.
        Computes active schedule metrics for all ridership dates inside GTFS coverage:
        - Evaluates calendar.txt + calendar_dates.txt exception logic per (service_id, date)
        - Computes scheduled trips, stop visits, span, earliest/latest departure times
        - Integrates with daily ridership counts
        """
        print("\n--- [5/5] Building Historical Schedule Match ---")
        t0 = time.time()

        # Step A: Pre-aggregate trip metrics from stop_times (stop count, departure window)
        print("  Pre-aggregating trip-level metrics from stop_times...")
        self.con.execute("DROP TABLE IF EXISTS temp_trip_metrics;")
        self.con.execute("""
            CREATE TEMP TABLE temp_trip_metrics AS
            SELECT 
                snapshot_id,
                trip_id,
                COUNT(stop_sequence) AS stop_count,
                COUNT(DISTINCT stop_id) AS distinct_stops,
                MIN(departure_seconds) AS min_departure_sec,
                MAX(departure_seconds) AS max_departure_sec
            FROM analytical.gtfs_stop_times
            GROUP BY snapshot_id, trip_id;
        """)

        # Step B: Associate trip metrics with route_id and service_id
        self.con.execute("DROP TABLE IF EXISTS temp_trip_summary;")
        self.con.execute("""
            CREATE TEMP TABLE temp_trip_summary AS
            SELECT 
                t.snapshot_id,
                t.route_id,
                t.service_id,
                t.trip_id,
                m.stop_count,
                m.distinct_stops,
                m.min_departure_sec,
                m.max_departure_sec
            FROM analytical.gtfs_trips t
            JOIN temp_trip_metrics m 
                ON t.snapshot_id = m.snapshot_id 
                AND t.trip_id = m.trip_id;
        """)

        # Step C: Generate calendar service activation matrix for each snapshot and date
        print("  Evaluating service calendar activation rules...")
        self.con.execute("DROP TABLE IF EXISTS temp_active_services;")
        self.con.execute("""
            CREATE TEMP TABLE temp_active_services AS
            WITH snapshot_dates AS (
                SELECT DISTINCT
                    matched_snapshot_id AS snapshot_id,
                    date
                FROM analytical.daily_ridership
                WHERE in_gtfs_coverage = true
            ),
            all_services AS (
                SELECT DISTINCT snapshot_id, service_id FROM analytical.gtfs_trips
            ),
            service_date_grid AS (
                SELECT 
                    sd.snapshot_id,
                    sd.date,
                    s.service_id
                FROM snapshot_dates sd
                JOIN all_services s ON sd.snapshot_id = s.snapshot_id
            ),
            calendar_evaluated AS (
                SELECT 
                    g.snapshot_id,
                    g.date,
                    g.service_id,
                    cd.exception_type,
                    c.start_date,
                    c.end_date,
                    CASE 
                        -- Rule 1: Calendar dates override
                        WHEN cd.exception_type = 1 THEN true
                        WHEN cd.exception_type = 2 THEN false
                        -- Rule 2: Base weekly calendar
                        WHEN c.service_id IS NOT NULL 
                             AND g.date >= c.start_date 
                             AND g.date <= c.end_date 
                             AND (
                                 (dayname(g.date) = 'Monday' AND c.monday = 1) OR
                                 (dayname(g.date) = 'Tuesday' AND c.tuesday = 1) OR
                                 (dayname(g.date) = 'Wednesday' AND c.wednesday = 1) OR
                                 (dayname(g.date) = 'Thursday' AND c.thursday = 1) OR
                                 (dayname(g.date) = 'Friday' AND c.friday = 1) OR
                                 (dayname(g.date) = 'Saturday' AND c.saturday = 1) OR
                                 (dayname(g.date) = 'Sunday' AND c.sunday = 1)
                             ) THEN true
                        ELSE false
                    END AS is_active
                FROM service_date_grid g
                LEFT JOIN analytical.gtfs_calendar c
                    ON g.snapshot_id = c.snapshot_id
                    AND g.service_id = c.service_id
                LEFT JOIN analytical.gtfs_calendar_dates cd
                    ON g.snapshot_id = cd.snapshot_id
                    AND g.service_id = cd.service_id
                    AND g.date = cd.date
            )
            SELECT snapshot_id, date, service_id
            FROM calendar_evaluated
            WHERE is_active = true;
        """)

        # Step D: Aggregate active schedule metrics per (snapshot_id, route_id, date)
        print("  Aggregating active schedule metrics per route and date...")
        self.con.execute("DROP TABLE IF EXISTS temp_daily_scheduled_routes;")
        self.con.execute("""
            CREATE TEMP TABLE temp_daily_scheduled_routes AS
            SELECT 
                ts.snapshot_id,
                act.date,
                ts.route_id,
                COUNT(ts.trip_id) AS scheduled_trips_count,
                SUM(ts.stop_count) AS scheduled_stop_visits,
                MIN(ts.min_departure_sec) AS first_departure_seconds,
                MAX(ts.max_departure_sec) AS last_departure_seconds
            FROM temp_trip_summary ts
            JOIN temp_active_services act
                ON ts.snapshot_id = act.snapshot_id
                AND ts.service_id = act.service_id
            GROUP BY ts.snapshot_id, act.date, ts.route_id;
        """)

        # Step E: Join with Ridership in GTFS coverage and Route Mapping
        print("  Integrating schedule metrics with daily ridership counts...")
        self.con.execute("DROP TABLE IF EXISTS analytical.historical_schedule_match;")
        self.con.execute("""
            CREATE TABLE analytical.historical_schedule_match AS
            WITH ridership_coverage AS (
                SELECT 
                    matched_snapshot_id AS snapshot_id,
                    matched_snapshot_label AS archive_label,
                    date,
                    route AS ridership_route,
                    daytype,
                    day_of_week,
                    is_weekend,
                    rides
                FROM analytical.daily_ridership
                WHERE in_gtfs_coverage = true
            ),
            mapped_ridership AS (
                SELECT 
                    rc.snapshot_id,
                    rc.archive_label,
                    rc.date,
                    rc.ridership_route,
                    rc.daytype,
                    rc.day_of_week,
                    rc.is_weekend,
                    rc.rides,
                    rm.gtfs_route_id,
                    rm.gtfs_route_short_name,
                    rm.gtfs_route_long_name,
                    rm.match_status
                FROM ridership_coverage rc
                LEFT JOIN analytical.route_mapping rm
                    ON rc.snapshot_id = rm.snapshot_id
                    AND rc.ridership_route = rm.ridership_route
            )
            SELECT 
                mr.snapshot_id,
                mr.archive_label,
                mr.date,
                mr.ridership_route,
                mr.gtfs_route_id,
                mr.gtfs_route_short_name,
                mr.gtfs_route_long_name,
                mr.daytype,
                mr.day_of_week,
                mr.is_weekend,
                mr.rides,
                COALESCE(sr.scheduled_trips_count, 0) AS scheduled_trips_count,
                COALESCE(sr.scheduled_stop_visits, 0) AS scheduled_stop_visits,
                sr.first_departure_seconds,
                sr.last_departure_seconds,
                CASE 
                    WHEN sr.first_departure_seconds IS NOT NULL THEN
                        printf('%02d:%02d:%02d', 
                               CAST(sr.first_departure_seconds // 3600 AS INTEGER), 
                               CAST((sr.first_departure_seconds % 3600) // 60 AS INTEGER), 
                               CAST(sr.first_departure_seconds % 60 AS INTEGER))
                    ELSE NULL 
                END AS first_departure_time,
                CASE 
                    WHEN sr.last_departure_seconds IS NOT NULL THEN
                        printf('%02d:%02d:%02d', 
                               CAST(sr.last_departure_seconds // 3600 AS INTEGER), 
                               CAST((sr.last_departure_seconds % 3600) // 60 AS INTEGER), 
                               CAST(sr.last_departure_seconds % 60 AS INTEGER))
                    ELSE NULL 
                END AS last_departure_time,
                CASE 
                    WHEN sr.last_departure_seconds IS NOT NULL AND sr.first_departure_seconds IS NOT NULL THEN
                        sr.last_departure_seconds - sr.first_departure_seconds
                    ELSE NULL
                END AS service_span_seconds,
                CASE 
                    WHEN COALESCE(sr.scheduled_trips_count, 0) > 0 THEN true 
                    ELSE false 
                END AS is_service_active,
                CASE 
                    WHEN mr.match_status != 'exact_match' OR mr.gtfs_route_id IS NULL THEN 'unmatched_route'
                    WHEN COALESCE(sr.scheduled_trips_count, 0) = 0 THEN 'zero_scheduled_trips'
                    ELSE 'matched'
                END AS match_quality
            FROM mapped_ridership mr
            LEFT JOIN temp_daily_scheduled_routes sr
                ON mr.snapshot_id = sr.snapshot_id
                AND mr.gtfs_route_id = sr.route_id
                AND mr.date = sr.date
            ORDER BY mr.date ASC, mr.ridership_route ASC;
        """)

        # Clean up temp tables
        self.con.execute("DROP TABLE IF EXISTS temp_trip_metrics;")
        self.con.execute("DROP TABLE IF EXISTS temp_trip_summary;")
        self.con.execute("DROP TABLE IF EXISTS temp_active_services;")
        self.con.execute("DROP TABLE IF EXISTS temp_daily_scheduled_routes;")

        # Export to Parquet
        parquet_path = os.path.join(self.integrated_dir, "historical_schedule_match.parquet")
        self.con.execute(f"COPY analytical.historical_schedule_match TO '{parquet_path.replace(os.sep, '/')}' (FORMAT PARQUET, COMPRESSION ZSTD);")

        row_count = self.con.execute("SELECT count(*) FROM analytical.historical_schedule_match").fetchone()[0]
        quality_counts = self.con.execute("SELECT match_quality, count(*) FROM analytical.historical_schedule_match GROUP BY match_quality").fetchall()
        elapsed = time.time() - t0
        print(f"  Historical schedule match built: {row_count:,} rows in {elapsed:.2f}s -> {parquet_path}")
        print(f"  Quality distribution: {dict(quality_counts)}")
        return self.con.execute("SELECT * FROM analytical.historical_schedule_match LIMIT 100").df()

    def run_all(self):
        """Execute complete analytical table integration workflow."""
        t_start = time.time()
        print("=" * 80)
        print("AI_RouteRanker - Executing Integrated Analytical Tables Generation")
        print("=" * 80)

        self.build_snapshot_metadata()
        self.build_route_mapping()
        self.build_gtfs_route_dim()
        self.build_daily_ridership()
        self.build_historical_schedule_match()

        total_elapsed = time.time() - t_start
        print("\n" + "=" * 80)
        print(f"Analytical Integration Pipeline Complete in {total_elapsed:.2f}s")
        print("=" * 80)
