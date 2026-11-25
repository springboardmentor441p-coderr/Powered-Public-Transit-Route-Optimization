"""
AI_RouteRanker - Ridership Preprocessing Pipeline
Cleans, normalizes, validates, and partitions raw CTA Daily Bus Ridership data.
Complies with Milestone 3.1 specifications.
"""

import csv
import datetime
import os
from typing import Dict, List, Optional, Set, Tuple
import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Constants
DAYTYPE_MAP = {
    "W": "Weekday",
    "A": "Saturday",
    "U": "Sunday/Holiday",
}


def preprocess_ridership(
    raw_csv_path: str,
    clean_parquet_path: str,
    clean_csv_path: str,
    quarantine_csv_path: str,
    db_path: Optional[str] = None,
) -> Dict[str, object]:
    """
    Load raw ridership, validate schema, normalize daytype, detect duplicates on
    business key (route, date, daytype), isolate invalid rows into quarantine,
    and output clean datasets in Parquet and CSV.
    """
    os.makedirs(os.path.dirname(clean_parquet_path), exist_ok=True)
    os.makedirs(os.path.dirname(clean_csv_path), exist_ok=True)
    os.makedirs(os.path.dirname(quarantine_csv_path), exist_ok=True)

    con = duckdb.connect(database=":memory:")
    con.execute("SET max_memory = '2GB';")

    # Step 1: Ingest raw CSV with explicit VARCHAR typing to prevent auto-coercion loss
    con.execute(f"""
        CREATE TEMPORARY TABLE raw_ridership_stage AS
        SELECT 
            route,
            date,
            daytype,
            rides
        FROM read_csv(
            '{raw_csv_path.replace(os.sep, "/")}',
            header=True,
            all_varchar=True,
            ignore_errors=False
        );
    """)

    total_raw_rows = con.execute("SELECT COUNT(*) FROM raw_ridership_stage").fetchone()[0]

    # Step 2: Parse, trim, and detect validity
    con.execute("""
        CREATE TEMPORARY TABLE parsed_ridership_stage AS
        SELECT
            row_number() OVER () AS raw_row_id,
            trim(route) AS route_raw,
            trim(date) AS date_raw,
            trim(daytype) AS daytype_raw,
            trim(rides) AS rides_raw,
            -- Parsed fields
            trim(route) AS route,
            try_strptime(trim(date), '%m/%d/%Y')::DATE AS parsed_date,
            upper(trim(daytype)) AS daytype_code,
            try_cast(replace(trim(rides), ',', '') AS BIGINT) AS parsed_rides
        FROM raw_ridership_stage;
    """)

    # Step 3: Flag invalid rows for quarantine
    # Invalid conditions: null route, empty route, unparseable date, invalid daytype,
    # null rides, or negative rides.
    con.execute("""
        CREATE TEMPORARY TABLE flagged_ridership AS
        SELECT 
            raw_row_id,
            route_raw,
            date_raw,
            daytype_raw,
            rides_raw,
            route,
            parsed_date,
            daytype_code,
            parsed_rides,
            CASE 
                WHEN route IS NULL OR length(route) = 0 THEN 'MISSING_ROUTE'
                WHEN parsed_date IS NULL THEN 'INVALID_DATE_FORMAT'
                WHEN daytype_code NOT IN ('W', 'A', 'U') THEN 'INVALID_DAYTYPE'
                WHEN parsed_rides IS NULL THEN 'INVALID_OR_NON_NUMERIC_RIDES'
                WHEN parsed_rides < 0 THEN 'NEGATIVE_RIDES'
                ELSE 'VALID'
            END AS validation_status
        FROM parsed_ridership_stage;
    """)

    quarantine_count = con.execute(
        "SELECT COUNT(*) FROM flagged_ridership WHERE validation_status != 'VALID'"
    ).fetchone()[0]

    # Step 4: Detect duplicate business keys (route, parsed_date, daytype_code) among valid rows
    con.execute("""
        CREATE TEMPORARY TABLE valid_with_dups AS
        SELECT 
            raw_row_id,
            route,
            parsed_date AS date,
            daytype_code AS daytype,
            CASE daytype_code
                WHEN 'W' THEN 'Weekday'
                WHEN 'A' THEN 'Saturday'
                WHEN 'U' THEN 'Sunday/Holiday'
                ELSE 'Unknown'
            END AS daytype_label,
            parsed_rides AS rides,
            row_number() OVER (
                PARTITION BY route, parsed_date, daytype_code 
                ORDER BY raw_row_id ASC
            ) AS key_occurrence_rank,
            COUNT(*) OVER (
                PARTITION BY route, parsed_date, daytype_code
            ) AS key_total_count
        FROM flagged_ridership
        WHERE validation_status = 'VALID';
    """)

    duplicate_keys_count = con.execute(
        "SELECT COUNT(*) FROM valid_with_dups WHERE key_total_count > 1 AND key_occurrence_rank = 1"
    ).fetchone()[0]
    duplicate_rows_count = con.execute(
        "SELECT COUNT(*) FROM valid_with_dups WHERE key_occurrence_rank > 1"
    ).fetchone()[0]

    # If duplicate rows exist, rank > 1 records are quarantined as DUPLICATE_BUSINESS_KEY
    con.execute("""
        CREATE TEMPORARY TABLE quarantine_records AS
        SELECT 
            route_raw,
            date_raw,
            daytype_raw,
            rides_raw,
            validation_status AS quarantine_reason
        FROM flagged_ridership
        WHERE validation_status != 'VALID'
        UNION ALL
        SELECT 
            route AS route_raw,
            strftime(date, '%m/%d/%Y') AS date_raw,
            daytype AS daytype_raw,
            CAST(rides AS VARCHAR) AS rides_raw,
            'DUPLICATE_BUSINESS_KEY' AS quarantine_reason
        FROM valid_with_dups
        WHERE key_occurrence_rank > 1;
    """)

    # Clean records table
    con.execute("""
        CREATE TEMPORARY TABLE clean_ridership AS
        SELECT 
            route,
            date,
            daytype,
            daytype_label,
            rides
        FROM valid_with_dups
        WHERE key_occurrence_rank = 1
        ORDER BY date ASC, route ASC;
    """)

    clean_count = con.execute("SELECT COUNT(*) FROM clean_ridership").fetchone()[0]
    distinct_routes = con.execute("SELECT COUNT(DISTINCT route) FROM clean_ridership").fetchone()[0]
    min_date = con.execute("SELECT MIN(date) FROM clean_ridership").fetchone()[0]
    max_date = con.execute("SELECT MAX(date) FROM clean_ridership").fetchone()[0]
    zero_rides_count = con.execute("SELECT COUNT(*) FROM clean_ridership WHERE rides = 0").fetchone()[0]
    total_quarantined = con.execute("SELECT COUNT(*) FROM quarantine_records").fetchone()[0]

    # Step 5: Export clean dataset to Parquet and CSV
    clean_parquet_sql = clean_parquet_path.replace(os.sep, "/")
    clean_csv_sql = clean_csv_path.replace(os.sep, "/")
    quarantine_csv_sql = quarantine_csv_path.replace(os.sep, "/")

    con.execute(f"COPY clean_ridership TO '{clean_parquet_sql}' (FORMAT PARQUET, COMPRESSION ZSTD);")
    con.execute(f"COPY clean_ridership TO '{clean_csv_sql}' (HEADER, DELIMITER ',');")
    con.execute(f"COPY quarantine_records TO '{quarantine_csv_sql}' (HEADER, DELIMITER ',');")

    # If persistent DuckDB analytical database path is provided, persist table
    if db_path:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        con_persist = duckdb.connect(db_path)
        con_persist.execute("CREATE SCHEMA IF NOT EXISTS analytical;")
        con_persist.execute(f"""
            CREATE OR REPLACE TABLE analytical.cta_ridership_clean AS
            SELECT * FROM read_parquet('{clean_parquet_sql}');
        """)
        con_persist.close()

    con.close()

    return {
        "total_raw_records": total_raw_rows,
        "clean_records": clean_count,
        "quarantined_records": total_quarantined,
        "duplicate_keys": duplicate_keys_count,
        "duplicate_rows": duplicate_rows_count,
        "distinct_routes": distinct_routes,
        "min_date": str(min_date),
        "max_date": str(max_date),
        "zero_rides_records": zero_rides_count,
        "clean_parquet_path": clean_parquet_path,
        "clean_csv_path": clean_csv_path,
        "quarantine_csv_path": quarantine_csv_path,
    }
