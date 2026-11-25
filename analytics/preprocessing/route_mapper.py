"""
AI_RouteRanker - Route Identifier Mapping Engine
Performs auditable, provenance-tracked matching between CTA ridership routes
and GTFS route identifiers across historical snapshots.
Complies with Milestone 3.1 specifications.
"""

import os
from typing import Dict, List, Optional, Set, Tuple
import duckdb
import pandas as pd


class RouteIdentifierMapper:
    """
    Maps CTA ridership route codes to GTFS route identifiers (route_short_name, route_id)
    per snapshot and across all historical GTFS feeds.
    """

    def __init__(self, duckdb_con: duckdb.DuckDBPyConnection):
        self.con = duckdb_con

    def compute_route_mappings(self) -> pd.DataFrame:
        """
        Build cross-snapshot route mapping matrix.
        Matches CTA ridership routes against GTFS routes per snapshot using exact normalized strings.
        Flags exact_match, unmatched, and ambiguous candidates.
        """
        query = """
        WITH ridership_routes AS (
            SELECT DISTINCT trim(route) AS ridership_route
            FROM analytical.cta_ridership_clean
            WHERE route IS NOT NULL AND length(trim(route)) > 0
        ),
        gtfs_routes_norm AS (
            SELECT 
                snapshot_id,
                route_id,
                trim(route_short_name) AS route_short_name,
                trim(route_long_name) AS route_long_name,
                route_type
            FROM analytical.gtfs_routes
        ),
        -- Cartesian product across all registered snapshots
        snapshots AS (
            SELECT snapshot_id FROM analytical.gtfs_snapshots
        ),
        route_snapshot_grid AS (
            SELECT 
                r.ridership_route,
                s.snapshot_id
            FROM ridership_routes r
            CROSS JOIN snapshots s
        ),
        matched_stage AS (
            SELECT 
                grid.ridership_route,
                grid.snapshot_id,
                g.route_id AS gtfs_route_id,
                g.route_short_name AS gtfs_route_short_name,
                g.route_long_name AS gtfs_route_long_name,
                g.route_type AS gtfs_route_type,
                CASE 
                    WHEN g.route_short_name IS NOT NULL THEN 'exact_route_short_name'
                    WHEN g.route_id = grid.ridership_route THEN 'exact_route_id'
                    ELSE 'none'
                END AS mapping_method
            FROM route_snapshot_grid grid
            LEFT JOIN gtfs_routes_norm g
                ON grid.snapshot_id = g.snapshot_id
                AND (
                    grid.ridership_route = g.route_short_name 
                    OR grid.ridership_route = g.route_id
                )
        ),
        candidate_counts AS (
            SELECT 
                ridership_route,
                snapshot_id,
                COUNT(gtfs_route_id) AS match_candidates_count
            FROM matched_stage
            GROUP BY ridership_route, snapshot_id
        )
        SELECT 
            m.ridership_route,
            m.snapshot_id,
            m.gtfs_route_short_name,
            m.gtfs_route_id,
            m.gtfs_route_long_name,
            m.gtfs_route_type,
            m.mapping_method,
            c.match_candidates_count,
            CASE 
                WHEN m.ridership_route IS NULL OR length(m.ridership_route) = 0 THEN 'invalid'
                WHEN c.match_candidates_count = 0 THEN 'unmatched'
                WHEN c.match_candidates_count = 1 THEN 'exact_match'
                ELSE 'ambiguous'
            END AS match_status
        FROM matched_stage m
        JOIN candidate_counts c
            ON m.ridership_route = c.ridership_route
            AND m.snapshot_id = c.snapshot_id
        ORDER BY m.snapshot_id, m.ridership_route;
        """
        mapping_df = self.con.execute(query).df()
        return mapping_df

    def save_mapping_table(self, output_parquet_path: str, output_csv_path: Optional[str] = None) -> pd.DataFrame:
        """Execute mapping and persist to Parquet and optional CSV."""
        os.makedirs(os.path.dirname(output_parquet_path), exist_ok=True)
        df = self.compute_route_mappings()
        df.to_parquet(output_parquet_path, index=False, compression="zstd")
        if output_csv_path:
            os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
            df.to_csv(output_csv_path, index=False)

        # Also store in DuckDB analytical schema
        self.con.execute("CREATE SCHEMA IF NOT EXISTS analytical;")
        self.con.execute(f"""
            CREATE OR REPLACE TABLE analytical.route_mapping AS
            SELECT * FROM read_parquet('{output_parquet_path.replace(os.sep, "/")}');
        """)
        return df
