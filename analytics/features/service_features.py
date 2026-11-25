"""
AI_RouteRanker - Service Feature Engineering Module
Extracts GTFS scheduled supply features from relational schedule match:
- scheduled_trips_count, scheduled_stop_visits, service_span_seconds, service_span_hours
- first_departure_seconds, last_departure_seconds, service_active, snapshot_id
Preserves strict NULL semantics for dates outside GTFS coverage or unmatched routes.
Complies with Milestone 4 specifications.
"""

import os
import sys
import duckdb
import pandas as pd

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class ServiceFeatureExtractor:
    """Extracts schedule-based capacity and service duration features."""

    def __init__(self, duckdb_con: duckdb.DuckDBPyConnection = None):
        self.con = duckdb_con if duckdb_con is not None else duckdb.connect()

    def extract_service_features(
        self,
        ridership_path: str,
        hsm_path: str,
    ) -> pd.DataFrame:
        """
        Left-joins daily ridership with matched GTFS schedule records.
        For dates/routes outside GTFS coverage or unmatched, service fields remain NULL.
        """
        query = f"""
        SELECT 
            r.route,
            r.date,
            s.snapshot_id,
            s.scheduled_trips_count,
            s.scheduled_stop_visits,
            s.service_span_seconds,
            round(s.service_span_seconds / 3600.0, 2) AS service_span_hours,
            s.first_departure_seconds,
            s.last_departure_seconds,
            s.is_service_active AS service_active,
            CASE 
                WHEN s.match_quality IS NOT NULL THEN s.match_quality 
                ELSE 'no_gtfs_coverage' 
            END AS schedule_coverage_status
        FROM '{ridership_path}' r
        LEFT JOIN '{hsm_path}' s
            ON r.route = s.ridership_route
            AND r.date = s.date
        ORDER BY r.route ASC, r.date ASC;
        """
        return self.con.execute(query).df()


def generate_service_features_dataset(
    ridership_path: str = os.path.join("data", "processed", "ridership", "cta_ridership_clean.parquet"),
    hsm_path: str = os.path.join("data", "processed", "integrated", "historical_schedule_match.parquet"),
    output_path: str = os.path.join("data", "processed", "features", "service_features.parquet"),
) -> pd.DataFrame:
    """Build and persist service features dataset."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    extractor = ServiceFeatureExtractor()
    df = extractor.extract_service_features(ridership_path, hsm_path)

    con = duckdb.connect()
    con.register("df_service_features", df)
    con.execute(f"COPY df_service_features TO '{output_path.replace(os.sep, '/')}' (FORMAT PARQUET, COMPRESSION ZSTD);")
    con.close()

    coverage_count = df["snapshot_id"].notna().sum()
    print(f"Service features generated: {len(df):,} rows ({coverage_count:,} with GTFS coverage) -> {output_path}")
    return df


if __name__ == "__main__":
    generate_service_features_dataset()
