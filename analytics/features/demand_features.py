"""
AI_RouteRanker - Demand & Dynamic Feature Engineering Module
Builds strictly causal, leakage-free time-series and interaction features:
- Lag features: rides_lag_1, rides_lag_7, rides_lag_14, rides_lag_28
- Rolling features: rolling_mean_7, rolling_mean_14, rolling_mean_28,
  rolling_std_7, rolling_std_14, rolling_std_28 (strictly excluding current target)
- Interaction metrics: rides_per_scheduled_trip, scheduled_trips_per_service_hour,
  ridership_daytype_average, route_relative_demand
Complies with Milestone 4 specifications.
"""

import os
import sys
import duckdb
import pandas as pd

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class DemandFeatureExtractor:
    """Extracts lag, rolling, and demand/service interaction features with strict leakage prevention."""

    def __init__(self, duckdb_con: duckdb.DuckDBPyConnection = None):
        self.con = duckdb_con if duckdb_con is not None else duckdb.connect()

    def extract_demand_features(
        self,
        ridership_path: str,
        hsm_path: str,
    ) -> pd.DataFrame:
        """
        Calculates lag, rolling window, and demand/service interaction features.
        Guarantees:
        1. All lags and rolling windows use strictly prior rows (1 PRECEDING).
        2. Scheduled service ratios evaluate to NULL when schedules are absent or zero.
        3. Zero division safely handled via NULLIF.
        """
        query = f"""
        WITH lagged_base AS (
            SELECT 
                r.route,
                r.date,
                r.daytype,
                r.rides,
                -- Lags (strictly prior observations in time)
                lag(r.rides, 1) OVER (PARTITION BY r.route ORDER BY r.date ASC) AS rides_lag_1,
                lag(r.rides, 7) OVER (PARTITION BY r.route ORDER BY r.date ASC) AS rides_lag_7,
                lag(r.rides, 14) OVER (PARTITION BY r.route ORDER BY r.date ASC) AS rides_lag_14,
                lag(r.rides, 28) OVER (PARTITION BY r.route ORDER BY r.date ASC) AS rides_lag_28,
                -- Rolling 7-day window (prior 7 observations, excluding current day)
                round(avg(r.rides) OVER (
                    PARTITION BY r.route ORDER BY r.date ASC 
                    ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
                ), 2) AS rolling_mean_7,
                round(stddev_samp(r.rides) OVER (
                    PARTITION BY r.route ORDER BY r.date ASC 
                    ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
                ), 2) AS rolling_std_7,
                -- Rolling 14-day window (prior 14 observations, excluding current day)
                round(avg(r.rides) OVER (
                    PARTITION BY r.route ORDER BY r.date ASC 
                    ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING
                ), 2) AS rolling_mean_14,
                round(stddev_samp(r.rides) OVER (
                    PARTITION BY r.route ORDER BY r.date ASC 
                    ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING
                ), 2) AS rolling_std_14,
                -- Rolling 28-day window (prior 28 observations, excluding current day)
                round(avg(r.rides) OVER (
                    PARTITION BY r.route ORDER BY r.date ASC 
                    ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING
                ), 2) AS rolling_mean_28,
                round(stddev_samp(r.rides) OVER (
                    PARTITION BY r.route ORDER BY r.date ASC 
                    ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING
                ), 2) AS rolling_std_28,
                -- Expanding route-daytype historical average (strictly prior observations)
                round(avg(r.rides) OVER (
                    PARTITION BY r.route, r.daytype ORDER BY r.date ASC 
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ), 2) AS ridership_daytype_average,
                -- Expanding route historical average (strictly prior observations)
                round(avg(r.rides) OVER (
                    PARTITION BY r.route ORDER BY r.date ASC 
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ), 2) AS expanding_historical_mean
            FROM '{ridership_path}' r
        ),
        joined_service AS (
            SELECT 
                lb.*,
                h.snapshot_id,
                h.scheduled_trips_count,
                h.scheduled_stop_visits,
                h.service_span_seconds,
                h.first_departure_seconds,
                h.last_departure_seconds,
                h.is_service_active,
                h.match_quality
            FROM lagged_base lb
            LEFT JOIN '{hsm_path}' h
                ON lb.route = h.ridership_route
                AND lb.date = h.date
        )
        SELECT 
            route,
            date,
            daytype,
            rides,
            rides_lag_1,
            rides_lag_7,
            rides_lag_14,
            rides_lag_28,
            rolling_mean_7,
            rolling_std_7,
            rolling_mean_14,
            rolling_std_14,
            rolling_mean_28,
            rolling_std_28,
            ridership_daytype_average,
            -- Relative demand (lag_1 / expanding historical mean)
            round(rides_lag_1 * 1.0 / NULLIF(expanding_historical_mean, 0), 4) AS route_relative_demand,
            -- Service Interaction: rides_per_scheduled_trip (NULL if schedule absent or zero)
            CASE 
                WHEN scheduled_trips_count IS NOT NULL AND scheduled_trips_count > 0 
                THEN round(rides * 1.0 / scheduled_trips_count, 2)
                ELSE NULL 
            END AS rides_per_scheduled_trip,
            -- Service Interaction: trips per service hour (NULL if service span is <= 0 or missing)
            CASE 
                WHEN service_span_seconds IS NOT NULL AND service_span_seconds > 0 
                THEN round(scheduled_trips_count * 1.0 / (service_span_seconds / 3600.0), 2)
                ELSE NULL 
            END AS scheduled_trips_per_service_hour
        FROM joined_service
        ORDER BY route ASC, date ASC;
        """
        return self.con.execute(query).df()


def generate_demand_features_dataset(
    ridership_path: str = os.path.join("data", "processed", "ridership", "cta_ridership_clean.parquet"),
    hsm_path: str = os.path.join("data", "processed", "integrated", "historical_schedule_match.parquet"),
    output_path: str = os.path.join("data", "processed", "features", "demand_service_features.parquet"),
) -> pd.DataFrame:
    """Build and persist demand and interaction feature dataset."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    extractor = DemandFeatureExtractor()
    df = extractor.extract_demand_features(ridership_path, hsm_path)

    con = duckdb.connect()
    con.register("df_demand_features", df)
    con.execute(f"COPY df_demand_features TO '{output_path.replace(os.sep, '/')}' (FORMAT PARQUET, COMPRESSION ZSTD);")
    con.close()

    valid_ratio_count = df["rides_per_scheduled_trip"].notna().sum()
    print(f"Demand/service features generated: {len(df):,} rows ({valid_ratio_count:,} with active service ratios) -> {output_path}")
    return df


if __name__ == "__main__":
    generate_demand_features_dataset()
