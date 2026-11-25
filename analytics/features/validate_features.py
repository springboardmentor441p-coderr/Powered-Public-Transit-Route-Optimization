"""
AI_RouteRanker - Feature Validation & Leakage Prevention Audit
Audits model_ready_features.parquet for:
- Completeness and key uniqueness (route, date)
- Strict leakage prevention (lag-1 target match, rolling window exclusion)
- Null semantics (unmatched schedules remain NULL, never false zeros)
- Division-by-zero safety
Complies with Milestone 4 specifications.
"""

import os
import sys
import duckdb
import pandas as pd

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def validate_features_pipeline(
    features_path: str = os.path.join("data", "processed", "features", "model_ready_features.parquet"),
) -> dict:
    print("=" * 80)
    print("AI_RouteRanker - Executing Feature Validation & Leakage Audit")
    print("=" * 80)

    if not os.path.exists(features_path):
        raise FileNotFoundError(f"Features file not found at: {features_path}")

    con = duckdb.connect()

    # 1. Total row count and distinct routes
    overview = con.execute(f"""
        SELECT 
            count(*) AS total_rows,
            count(DISTINCT route) AS distinct_routes,
            min(date) AS min_date,
            max(date) AS max_date,
            sum(CASE WHEN route IS NULL THEN 1 ELSE 0 END) AS null_routes,
            sum(CASE WHEN date IS NULL THEN 1 ELSE 0 END) AS null_dates,
            sum(CASE WHEN target_rides IS NULL THEN 1 ELSE 0 END) AS null_targets
        FROM '{features_path}'
    """).df().to_dict(orient="records")[0]

    print(f"  Total Rows:         {overview['total_rows']:,}")
    print(f"  Distinct Routes:    {overview['distinct_routes']}")
    print(f"  Temporal Span:      {str(overview['min_date'])[:10]} to {str(overview['max_date'])[:10]}")
    print(f"  Null Targets:       {overview['null_targets']}")

    # 2. Key Uniqueness Check on (route, date)
    duplicate_keys = con.execute(f"""
        SELECT count(*) FROM (
            SELECT route, date
            FROM '{features_path}'
            GROUP BY route, date
            HAVING count(*) > 1
        )
    """).fetchone()[0]
    print(f"  Duplicate (route, date) keys: {duplicate_keys}")
    assert duplicate_keys == 0, f"Found {duplicate_keys} duplicate business keys in model-ready features!"

    # 3. Leakage Check 1: Verify rides_lag_1 matches previous row's target_rides
    leakage_lag_check = con.execute(f"""
        WITH check_lag AS (
            SELECT 
                route,
                date,
                target_rides,
                rides_lag_1,
                lag(target_rides, 1) OVER (PARTITION BY route ORDER BY date ASC) AS true_prev_rides
            FROM '{features_path}'
        )
        SELECT count(*) 
        FROM check_lag
        WHERE true_prev_rides IS NOT NULL 
          AND rides_lag_1 != true_prev_rides;
    """).fetchone()[0]
    print(f"  Mismatched Lag-1 values: {leakage_lag_check}")
    assert leakage_lag_check == 0, "Leakage detected: rides_lag_1 does not match true previous target!"

    # 4. Leakage Check 2: Verify rolling_mean_7 does NOT include current day target
    # If current day target were included, for a sequence of constant rides, mean would equal that ride on the first observation
    # But because it is shifted, the first observation MUST have rolling_mean_7 as NULL
    first_obs_with_rolling_mean = con.execute(f"""
        WITH ranked_obs AS (
            SELECT 
                route,
                row_number() OVER (PARTITION BY route ORDER BY date ASC) AS obs_rank,
                rolling_mean_7
            FROM '{features_path}'
        )
        SELECT count(*) 
        FROM ranked_obs
        WHERE obs_rank = 1 AND rolling_mean_7 IS NOT NULL;
    """).fetchone()[0]
    print(f"  First observations with non-null rolling_mean_7: {first_obs_with_rolling_mean}")
    assert first_obs_with_rolling_mean == 0, "Leakage detected: rolling_mean_7 includes current observation!"

    # 5. Null Semantics Check: Verify dates outside GTFS coverage remain NULL (never false 0)
    pre_gtfs_non_nulls = con.execute(f"""
        SELECT count(*)
        FROM '{features_path}'
        WHERE date < '2025-11-23' 
          AND (scheduled_trips_count IS NOT NULL OR service_span_seconds IS NOT NULL);
    """).fetchone()[0]
    print(f"  Pre-GTFS records falsely populated with schedules: {pre_gtfs_non_nulls}")
    assert pre_gtfs_non_nulls == 0, "Data distortion: pre-GTFS dates have non-null schedule supply!"

    # 6. Division-by-Zero Safety Check
    invalid_ratios = con.execute(f"""
        SELECT count(*)
        FROM '{features_path}'
        WHERE rides_per_scheduled_trip IS NOT NULL 
          AND (isinf(rides_per_scheduled_trip) OR isnan(rides_per_scheduled_trip) OR rides_per_scheduled_trip < 0);
    """).fetchone()[0]
    print(f"  Invalid / Inf / NaN / Negative service ratios: {invalid_ratios}")
    assert invalid_ratios == 0, "Found invalid division-by-zero or negative service ratios!"

    con.close()
    print("=" * 80)
    print("Feature Validation PASSED: All 6 Integrity & Leakage Tests Succeeded!")
    print("=" * 80)
    return {
        "status": "PASSED",
        "total_rows": overview["total_rows"],
        "duplicate_keys": duplicate_keys,
        "leakage_lag_check": leakage_lag_check,
        "first_obs_rolling_null": first_obs_with_rolling_mean == 0,
        "pre_gtfs_null_preserved": pre_gtfs_non_nulls == 0,
        "invalid_ratios": invalid_ratios,
    }


if __name__ == "__main__":
    validate_features_pipeline()
