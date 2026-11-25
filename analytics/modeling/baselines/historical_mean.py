"""
AI_RouteRanker - Baseline A: Route/Daytype Expanding Historical Mean
Calculates the mean of all eligible historical observations for the same route
and daytype strictly prior to the prediction date (< t).
Enforces zero target-date leakage and rolling one-day-ahead causal updates.
"""

from typing import Optional, Dict, Any
import duckdb
import numpy as np
import pandas as pd


class HistoricalMeanBaseline:
    """
    Baseline A: Route and Daytype-Specific Expanding Historical Mean.
    For each target observation (route r, daytype d, date t), predicts the average
    ridership of prior observations for (r, d) strictly before date t.
    """

    def __init__(self, history_start_date: Optional[str] = None):
        """
        Args:
            history_start_date: Optional earliest date to include in historical pool
                                (e.g. '2022-01-01' for Tier 1, '2025-11-23' for Tier 2).
        """
        self.history_start_date = history_start_date

    def generate_predictions(
        self,
        eval_df: pd.DataFrame,
        history_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Generates rolling one-day-ahead expanding historical mean predictions.

        Args:
            eval_df: DataFrame of target dates to predict (must contain route, date, daytype, target_rides).
            history_df: Full historical dataset containing eligible observations prior to and including eval period.

        Returns:
            DataFrame with predictions, ground truth, observation counts, and fallback flags.
        """
        # Ensure dates are datetime
        eval_clean = eval_df[["route", "date", "daytype", "target_rides"]].copy()
        eval_clean["date"] = pd.to_datetime(eval_clean["date"])

        hist_clean = history_df[["route", "date", "daytype", "target_rides"]].copy()
        hist_clean["date"] = pd.to_datetime(hist_clean["date"])

        if self.history_start_date:
            hist_clean = hist_clean[hist_clean["date"] >= pd.to_datetime(self.history_start_date)].copy()

        # Combine history and eval for DuckDB window computation
        con = duckdb.connect()
        try:
            con.register("df_all", hist_clean)
            con.register("df_eval", eval_clean)

            query = """
            WITH combined_data AS (
                SELECT route, date, daytype, target_rides FROM df_all
                UNION ALL
                SELECT route, date, daytype, NULL AS target_rides FROM df_eval
            ),
            distinct_pool AS (
                -- History non-null target_rides takes precedence over eval NULLs
                SELECT route, date, daytype, MAX(target_rides) AS target_rides
                FROM combined_data
                GROUP BY route, date, daytype
            ),
            expanding_stats AS (
                SELECT 
                    route,
                    date,
                    daytype,
                    target_rides,
                    -- Expanding mean for exact (route, daytype) strictly prior to date t
                    AVG(target_rides) OVER (
                        PARTITION BY route, daytype 
                        ORDER BY date ASC 
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) AS exp_daytype_mean,
                    COUNT(target_rides) OVER (
                        PARTITION BY route, daytype 
                        ORDER BY date ASC 
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) AS exp_daytype_count,
                    -- Expanding mean for route across all daytypes strictly prior to date t (fallback 1)
                    AVG(target_rides) OVER (
                        PARTITION BY route 
                        ORDER BY date ASC 
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) AS exp_route_mean,
                    COUNT(target_rides) OVER (
                        PARTITION BY route 
                        ORDER BY date ASC 
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) AS exp_route_count
                FROM distinct_pool
            )
            SELECT 
                e.route,
                e.date,
                e.daytype,
                e.target_rides,
                ROUND(CASE 
                    WHEN s.exp_daytype_mean IS NOT NULL THEN s.exp_daytype_mean
                    WHEN s.exp_route_mean IS NOT NULL THEN s.exp_route_mean
                    ELSE NULL
                END, 2) AS prediction,
                CASE 
                    WHEN s.exp_daytype_mean IS NOT NULL THEN 'route_daytype_mean'
                    WHEN s.exp_route_mean IS NOT NULL THEN 'route_mean_fallback'
                    ELSE 'unavailable'
                END AS fallback_level,
                COALESCE(s.exp_daytype_count, 0) AS prior_obs_count
            FROM df_eval e
            LEFT JOIN expanding_stats s
                ON e.route = s.route AND e.date = s.date AND e.daytype = s.daytype
            ORDER BY e.route ASC, e.date ASC;
            """
            result_df = con.execute(query).df()
            return result_df
        finally:
            con.close()
