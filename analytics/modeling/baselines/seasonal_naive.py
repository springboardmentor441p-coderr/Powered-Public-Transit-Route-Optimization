"""
AI_RouteRanker - Baseline B: Seasonal Naive (Calendar t-7)
Implements calendar-date weekly seasonal naive baseline with hierarchical fallbacks:
1. Exact calendar date t - 7 days for the same route.
2. Most recent observation for same route and daytype in preceding [t - 28, t - 1] calendar days.
3. Route/daytype expanding historical mean strictly prior to date t.
4. Marked as unavailable (NaN) if no prior history exists. Never silently substitutes zero.
"""

from typing import Optional, Dict, Any
import duckdb
import numpy as np
import pandas as pd


class SeasonalNaiveBaseline:
    """
    Baseline B: Seasonal Naive with Calendar t-7 and 28-day Daytype Fallback Hierarchy.
    Strictly uses calendar date arithmetic (not observation row lags).
    """

    def __init__(self, history_start_date: Optional[str] = None):
        """
        Args:
            history_start_date: Optional earliest date to include in historical pool.
        """
        self.history_start_date = history_start_date

    def generate_predictions(
        self,
        eval_df: pd.DataFrame,
        history_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Generates calendar t-7 seasonal naive predictions with prioritized fallback levels.

        Args:
            eval_df: Target evaluation records (route, date, daytype, target_rides).
            history_df: Historical dataset containing past observations.

        Returns:
            DataFrame with predictions, ground truth, and fallback_level.
        """
        eval_clean = eval_df[["route", "date", "daytype", "target_rides"]].copy()
        eval_clean["date"] = pd.to_datetime(eval_clean["date"])

        hist_clean = history_df[["route", "date", "daytype", "target_rides"]].copy()
        hist_clean["date"] = pd.to_datetime(hist_clean["date"])

        if self.history_start_date:
            hist_clean = hist_clean[hist_clean["date"] >= pd.to_datetime(self.history_start_date)].copy()

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
                SELECT route, date, daytype, MAX(target_rides) AS target_rides
                FROM combined_data
                GROUP BY route, date, daytype
            ),
            -- Expanding historical mean for Level 3 fallback
            expanding_stats AS (
                SELECT 
                    route, date, daytype,
                    AVG(target_rides) OVER (
                        PARTITION BY route, daytype 
                        ORDER BY date ASC 
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) AS exp_daytype_mean,
                    AVG(target_rides) OVER (
                        PARTITION BY route 
                        ORDER BY date ASC 
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) AS exp_route_mean
                FROM distinct_pool
            ),
            -- Level 1: Exact Calendar t - 7 Days Lookup
            exact_t7 AS (
                SELECT 
                    e.route,
                    e.date,
                    e.daytype,
                    prev.target_rides AS pred_t7
                FROM df_eval e
                LEFT JOIN distinct_pool prev
                    ON e.route = prev.route
                    AND prev.date = e.date - INTERVAL 7 DAY
            ),
            -- Level 2: Most recent observation for same route and daytype in preceding [t-28, t-1] days
            recent_28d AS (
                SELECT 
                    e.route,
                    e.date,
                    e.daytype,
                    max_by(past.target_rides, past.date) AS pred_recent_28d,
                    MAX(past.date) AS recent_28d_date
                FROM df_eval e
                LEFT JOIN distinct_pool past
                    ON e.route = past.route
                    AND e.daytype = past.daytype
                    AND past.date >= e.date - INTERVAL 28 DAY
                    AND past.date < e.date
                    AND past.target_rides IS NOT NULL
                GROUP BY e.route, e.date, e.daytype
            )
            SELECT 
                e.route,
                e.date,
                e.daytype,
                e.target_rides,
                ROUND(CASE 
                    WHEN t7.pred_t7 IS NOT NULL THEN CAST(t7.pred_t7 AS DOUBLE)
                    WHEN r28.pred_recent_28d IS NOT NULL THEN CAST(r28.pred_recent_28d AS DOUBLE)
                    WHEN exp.exp_daytype_mean IS NOT NULL THEN exp.exp_daytype_mean
                    WHEN exp.exp_route_mean IS NOT NULL THEN exp.exp_route_mean
                    ELSE NULL
                END, 2) AS prediction,
                CASE 
                    WHEN t7.pred_t7 IS NOT NULL THEN 'calendar_t7'
                    WHEN r28.pred_recent_28d IS NOT NULL THEN 'recent_28d_daytype'
                    WHEN exp.exp_daytype_mean IS NOT NULL THEN 'historical_mean'
                    WHEN exp.exp_route_mean IS NOT NULL THEN 'historical_mean'
                    ELSE 'unavailable'
                END AS fallback_level,
                t7.pred_t7 AS raw_t7_value,
                r28.pred_recent_28d AS raw_28d_value
            FROM df_eval e
            LEFT JOIN exact_t7 t7
                ON e.route = t7.route AND e.date = t7.date AND e.daytype = t7.daytype
            LEFT JOIN recent_28d r28
                ON e.route = r28.route AND e.date = r28.date AND e.daytype = r28.daytype
            LEFT JOIN expanding_stats exp
                ON e.route = exp.route AND e.date = exp.date AND e.daytype = exp.daytype
            ORDER BY e.route ASC, e.date ASC;
            """
            result_df = con.execute(query).df()
            return result_df
        finally:
            con.close()
