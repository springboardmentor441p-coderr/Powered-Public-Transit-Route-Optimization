"""
AI_RouteRanker - Route Feature Engineering Module
Builds route-level historical statistical features with strict data leakage prevention:
- Expanding window historical statistics prior to current prediction date:
  historical_mean_rides, historical_std_rides, historical_max_rides,
  historical_min_rides, route_observation_count
- Distinct static descriptive route profiles clearly partitioned to prevent training leakage.
Complies with Milestone 4 specifications.
"""

import os
import sys
import duckdb
import pandas as pd

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class RouteFeatureExtractor:
    """Extracts route-level features with strict temporal leakage prevention."""

    def __init__(self, duckdb_con: duckdb.DuckDBPyConnection = None):
        self.con = duckdb_con if duckdb_con is not None else duckdb.connect()

    def extract_dynamic_route_features(self, source_parquet: str) -> pd.DataFrame:
        """
        Calculates expanding historical metrics strictly using observations prior to date t
        (ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING).
        Guarantees zero target or future leakage.
        """
        query = f"""
        SELECT 
            route,
            date,
            round(avg(rides) OVER w, 2) AS historical_mean_rides,
            round(stddev_samp(rides) OVER w, 2) AS historical_std_rides,
            max(rides) OVER w AS historical_max_rides,
            min(rides) OVER w AS historical_min_rides,
            count(rides) OVER w AS route_observation_count
        FROM '{source_parquet}'
        WINDOW w AS (
            PARTITION BY route 
            ORDER BY date ASC 
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        )
        ORDER BY route ASC, date ASC;
        """
        return self.con.execute(query).df()

    def extract_static_route_profiles(self, source_parquet: str) -> pd.DataFrame:
        """
        Calculates static full-history descriptive route metrics for exploratory analysis
        and route clustering. Clearly labeled as 'descriptive' to avoid prediction leakage.
        """
        query = f"""
        SELECT 
            route,
            count(*) AS descriptive_total_obs,
            sum(rides) AS descriptive_total_rides,
            round(avg(rides), 2) AS descriptive_mean_rides,
            round(median(rides), 2) AS descriptive_median_rides,
            round(stddev_samp(rides), 2) AS descriptive_std_rides,
            min(rides) AS descriptive_min_rides,
            max(rides) AS descriptive_max_rides,
            round(stddev_samp(rides) / NULLIF(avg(rides), 0), 4) AS descriptive_cv
        FROM '{source_parquet}'
        GROUP BY route
        ORDER BY route ASC;
        """
        return self.con.execute(query).df()


def generate_route_features_dataset(
    input_path: str = os.path.join("data", "processed", "ridership", "cta_ridership_clean.parquet"),
    output_path: str = os.path.join("data", "processed", "features", "route_features.parquet"),
) -> pd.DataFrame:
    """Build and persist route-level feature dataset."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    extractor = RouteFeatureExtractor()
    df = extractor.extract_dynamic_route_features(input_path)

    con = duckdb.connect()
    con.register("df_route_features", df)
    con.execute(f"COPY df_route_features TO '{output_path.replace(os.sep, '/')}' (FORMAT PARQUET, COMPRESSION ZSTD);")
    con.close()

    print(f"Route features generated: {len(df):,} rows -> {output_path}")
    return df


if __name__ == "__main__":
    generate_route_features_dataset()
