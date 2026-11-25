"""
AI_RouteRanker - Feature Engineering Pipeline Orchestrator
Builds and persists all 5 Milestone 4 feature datasets:
1. ridership_features.parquet
2. route_features.parquet
3. service_features.parquet
4. demand_service_features.parquet
5. model_ready_features.parquet

Enforces strict leakage prevention, chronological sorting, and memory safety.
Complies with Milestone 4 specifications.
"""

import os
import sys
import time
import duckdb
import pandas as pd

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from analytics.features.temporal_features import generate_temporal_features_dataset
from analytics.features.route_features import generate_route_features_dataset
from analytics.features.service_features import generate_service_features_dataset
from analytics.features.demand_features import generate_demand_features_dataset


class FeaturePipelineOrchestrator:
    """Orchestrates generation of individual feature sets and consolidated model-ready dataset."""

    def __init__(
        self,
        features_dir: str = os.path.join("data", "processed", "features"),
        ridership_path: str = os.path.join("data", "processed", "ridership", "cta_ridership_clean.parquet"),
        daily_ridership_path: str = os.path.join("data", "processed", "integrated", "daily_ridership.parquet"),
        hsm_path: str = os.path.join("data", "processed", "integrated", "historical_schedule_match.parquet"),
        db_path: str = os.path.join("data", "processed", "ai_routeranker.duckdb"),
    ):
        self.features_dir = features_dir
        self.ridership_path = ridership_path
        self.daily_ridership_path = daily_ridership_path
        self.hsm_path = hsm_path
        self.db_path = db_path
        os.makedirs(self.features_dir, exist_ok=True)

    def build_all_features(self) -> dict:
        t_start = time.time()
        print("=" * 80)
        print("AI_RouteRanker - Executing Feature Engineering Pipeline")
        print("=" * 80)

        # 1. Temporal features
        print("\n--- [1/5] Building Temporal Features ---")
        temporal_out = os.path.join(self.features_dir, "ridership_features.parquet")
        t0 = time.time()
        df_temporal = generate_temporal_features_dataset(self.daily_ridership_path, temporal_out)
        print(f"  Completed in {time.time() - t0:.2f}s | Rows: {len(df_temporal):,}")

        # 2. Route historical features
        print("\n--- [2/5] Building Route Dynamic Historical Features ---")
        route_out = os.path.join(self.features_dir, "route_features.parquet")
        t0 = time.time()
        df_route = generate_route_features_dataset(self.ridership_path, route_out)
        print(f"  Completed in {time.time() - t0:.2f}s | Rows: {len(df_route):,}")

        # 3. Service features
        print("\n--- [3/5] Building GTFS Service Features ---")
        service_out = os.path.join(self.features_dir, "service_features.parquet")
        t0 = time.time()
        df_service = generate_service_features_dataset(self.ridership_path, self.hsm_path, service_out)
        print(f"  Completed in {time.time() - t0:.2f}s | Rows: {len(df_service):,}")

        # 4. Demand & Interaction features
        print("\n--- [4/5] Building Demand, Lag & Interaction Features ---")
        demand_out = os.path.join(self.features_dir, "demand_service_features.parquet")
        t0 = time.time()
        df_demand = generate_demand_features_dataset(self.ridership_path, self.hsm_path, demand_out)
        print(f"  Completed in {time.time() - t0:.2f}s | Rows: {len(df_demand):,}")

        # 5. Consolidated Model-Ready Features
        print("\n--- [5/5] Consolidating Model-Ready Features Dataset ---")
        model_ready_out = os.path.join(self.features_dir, "model_ready_features.parquet")
        t0 = time.time()

        con = duckdb.connect()
        con.execute(f"""
            CREATE TABLE model_ready AS
            SELECT 
                -- Identifiers and Target
                d.route,
                d.date,
                d.daytype,
                d.rides AS target_rides,
                -- Temporal features
                t.year,
                t.month,
                t.quarter,
                t.day,
                t.day_of_week,
                t.day_of_week_int,
                t.day_of_year,
                t.week_of_year,
                t.is_weekend,
                t.is_month_start,
                t.is_month_end,
                -- Route expanding historical statistics (strictly prior to date t)
                r.historical_mean_rides,
                r.historical_std_rides,
                r.historical_max_rides,
                r.historical_min_rides,
                r.route_observation_count,
                -- Lag features (strictly prior observations)
                d.rides_lag_1,
                d.rides_lag_7,
                d.rides_lag_14,
                d.rides_lag_28,
                -- Rolling window features (prior observations, excluding current target)
                d.rolling_mean_7,
                d.rolling_std_7,
                d.rolling_mean_14,
                d.rolling_std_14,
                d.rolling_mean_28,
                d.rolling_std_28,
                d.ridership_daytype_average,
                d.route_relative_demand,
                -- GTFS Service supply features (NULL for dates/routes without GTFS match)
                s.snapshot_id,
                s.scheduled_trips_count,
                s.scheduled_stop_visits,
                s.service_span_seconds,
                s.service_span_hours,
                s.first_departure_seconds,
                s.last_departure_seconds,
                s.service_active,
                s.schedule_coverage_status,
                -- Demand/Service Ratios (NULL when schedules absent or trips == 0)
                d.rides_per_scheduled_trip,
                d.scheduled_trips_per_service_hour
            FROM '{demand_out}' d
            JOIN '{temporal_out}' t
                ON d.route = t.route AND d.date = t.date
            JOIN '{route_out}' r
                ON d.route = r.route AND d.date = r.date
            JOIN '{service_out}' s
                ON d.route = s.route AND d.date = s.date
            ORDER BY d.route ASC, d.date ASC;
        """)

        # Export to compressed Parquet
        con.execute(f"COPY model_ready TO '{model_ready_out.replace(os.sep, '/')}' (FORMAT PARQUET, COMPRESSION ZSTD);")
        
        row_count = con.execute("SELECT count(*) FROM model_ready").fetchone()[0]
        col_count = len(con.execute("DESCRIBE model_ready").fetchall())
        con.close()

        total_elapsed = time.time() - t_start
        print(f"  Model-ready dataset consolidated: {row_count:,} rows, {col_count} columns in {time.time() - t0:.2f}s -> {model_ready_out}")

        print("\n" + "=" * 80)
        print(f"Feature Engineering Pipeline Complete in {total_elapsed:.2f}s")
        print("=" * 80)

        return {
            "total_rows": row_count,
            "total_cols": col_count,
            "elapsed_seconds": total_elapsed,
        }


def main():
    orchestrator = FeaturePipelineOrchestrator()
    orchestrator.build_all_features()


if __name__ == "__main__":
    main()
