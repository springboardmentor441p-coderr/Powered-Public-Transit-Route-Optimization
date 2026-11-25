"""
AI_RouteRanker - Temporal Feature Engineering Module
Extracts cyclical and calendar features from service dates:
- year, month, quarter, day, day_of_week, day_of_week_int, day_of_year, week_of_year
- is_weekend, daytype, is_month_start, is_month_end
Complies with Milestone 4 specifications.
"""

import os
import sys
import duckdb
import pandas as pd

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class TemporalFeatureExtractor:
    """Extracts calendar and temporal features from transit service dates."""

    def __init__(self, duckdb_con: duckdb.DuckDBPyConnection = None):
        self.con = duckdb_con if duckdb_con is not None else duckdb.connect()

    def extract_temporal_features(self, source_parquet: str) -> pd.DataFrame:
        """
        Extracts temporal features from daily ridership dataset via DuckDB.
        Guarantees deterministic, calendar-aligned outputs.
        """
        query = f"""
        SELECT 
            route,
            date,
            daytype,
            year(date) AS year,
            month(date) AS month,
            quarter(date) AS quarter,
            day(date) AS day,
            dayname(date) AS day_of_week,
            dayofweek(date) AS day_of_week_int,
            dayofyear(date) AS day_of_year,
            weekofyear(date) AS week_of_year,
            CASE 
                WHEN daytype IN ('A', 'U') OR dayname(date) IN ('Saturday', 'Sunday') THEN true 
                ELSE false 
            END AS is_weekend,
            CASE 
                WHEN day(date) = 1 THEN true 
                ELSE false 
            END AS is_month_start,
            CASE 
                WHEN date = last_day(date) THEN true 
                ELSE false 
            END AS is_month_end
        FROM '{source_parquet}'
        ORDER BY route ASC, date ASC;
        """
        return self.con.execute(query).df()


def generate_temporal_features_dataset(
    input_path: str = os.path.join("data", "processed", "integrated", "daily_ridership.parquet"),
    output_path: str = os.path.join("data", "processed", "features", "ridership_features.parquet"),
) -> pd.DataFrame:
    """Build and persist ridership temporal features dataset."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    extractor = TemporalFeatureExtractor()
    df = extractor.extract_temporal_features(input_path)
    
    # Save to parquet with ZSTD compression
    con = duckdb.connect()
    con.register("df_temporal", df)
    con.execute(f"COPY df_temporal TO '{output_path.replace(os.sep, '/')}' (FORMAT PARQUET, COMPRESSION ZSTD);")
    con.close()
    
    print(f"Temporal features generated: {len(df):,} rows -> {output_path}")
    return df


if __name__ == "__main__":
    generate_temporal_features_dataset()
