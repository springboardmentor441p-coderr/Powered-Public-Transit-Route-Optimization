"""
AI_RouteRanker - Phase 6.1 Demand Aggregator & Feature Preparation Module
Implements route-attributed stop demand aggregation, scheduled headway calculation across
all five approved windows, coverage tiering, and mutually exclusive eligibility classification.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd


# Approved canonical parameters
CANONICAL_SNAPSHOT_ID = "mdb-389-202605300003"
REPRESENTATIVE_DATE = "2026-06-10"  # Wednesday
TIER2_TRAIN_START = "2025-11-23"
TIER2_TRAIN_END = "2026-04-23"  # 152 calendar days

# Approved headway operational time windows (clock and seconds)
HEADWAY_WINDOWS: Dict[str, Tuple[int, int]] = {
    "AM_PEAK": (25200, 32400),       # 07:00:00 - 08:59:59 (2 hours)
    "MIDDAY": (32400, 57600),        # 09:00:00 - 15:59:59 (7 hours)
    "PM_PEAK": (57600, 64800),       # 16:00:00 - 17:59:59 (2 hours)
    "EVENING": (64800, 79200),       # 18:00:00 - 21:59:59 (4 hours)
    "OVERNIGHT": (79200, 104400),    # 22:00:00 - 28:59:59 (7 hours, next-day 04:59:59)
}


class DemandAggregator:
    """
    Aggregates historical route demand onto physical transit stops using proportional
    scheduled service frequency, and computes scheduled inter-arrival spacing (headways).
    """

    @staticmethod
    def parse_gtfs_time_to_seconds(time_str: str) -> int:
        """
        Parses GTFS HH:MM:SS format to integer seconds, preserving hours >= 24.
        Example: '25:30:00' -> 91,800 seconds.
        """
        parts = time_str.strip().split(":")
        h = int(parts[0])
        m = int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
        return h * 3600 + m * 60 + s

    @staticmethod
    def compute_route_stop_demand_attribution(
        stop_visits_df: pd.DataFrame,
        route_demand_df: pd.DataFrame,
        mapped_routes: set,
    ) -> pd.DataFrame:
        """
        Attributes historical route weekday demand to stops based on relative scheduled visits.
        
        Formula:
          D_{s, r} = Y_bar_{r, W} * (v_{s, r} / V_r)
          D_s = sum_{r in R_mapped} D_{s, r}
        
        Args:
          stop_visits_df: DataFrame with ['stop_id', 'route_id', 'visits']
          route_demand_df: DataFrame with ['route_id', 'mean_daily_rides']
          mapped_routes: Set of route IDs with confirmed exact_match status.
          
        Returns:
          DataFrame indexed by stop_id with attributed demand, mapped visits, and coverage status.
        """
        df = stop_visits_df.copy()
        df["is_mapped"] = df["route_id"].isin(mapped_routes)

        # Merge demand for mapped routes only
        df = df.merge(route_demand_df[["route_id", "mean_daily_rides"]], on="route_id", how="left")

        # Total visits per route across the entire network
        route_total_visits = df.groupby("route_id")["visits"].transform("sum")
        df["route_total_visits"] = route_total_visits

        # Attributed demand per stop-route
        # D_{s, r} = mean_daily_rides * (visits / total_visits)
        # If route has 0 total visits or is unmapped, demand is not attributed
        def _calc_demand(row):
            if not row["is_mapped"] or pd.isna(row["mean_daily_rides"]):
                return np.nan
            if row["route_total_visits"] <= 0:
                return 0.0
            return float(row["mean_daily_rides"]) * (float(row["visits"]) / float(row["route_total_visits"]))

        df["attributed_route_demand"] = df.apply(_calc_demand, axis=1)

        # Aggregate at stop level
        def _agg_stop(group):
            total_visits = group["visits"].sum()
            routes_served = group["route_id"].nunique()
            
            mapped_rows = group[group["is_mapped"]]
            unmapped_rows = group[~group["is_mapped"]]
            
            n_mapped_routes = mapped_rows["route_id"].nunique()
            n_unmapped_routes = unmapped_rows["route_id"].nunique()
            
            mapped_visits = mapped_rows["visits"].sum()
            unmapped_visits = unmapped_rows["visits"].sum()

            if n_mapped_routes == routes_served and routes_served > 0:
                coverage_status = "COMPLETE"
            elif n_mapped_routes > 0 and n_unmapped_routes > 0:
                coverage_status = "PARTIAL"
            else:
                coverage_status = "UNAVAILABLE"

            if n_mapped_routes > 0:
                # Sum attributed demand over mapped routes; preserve confirmed 0.0
                attributed_demand = mapped_rows["attributed_route_demand"].sum(min_count=1)
            else:
                attributed_demand = np.nan

            return pd.Series({
                "total_visits": total_visits,
                "routes_served": routes_served,
                "mapped_routes_served": n_mapped_routes,
                "unmapped_routes_served": n_unmapped_routes,
                "mapped_visits": mapped_visits,
                "unmapped_visits": unmapped_visits,
                "attributed_demand": attributed_demand,
                "demand_coverage_status": coverage_status,
            })

        stop_summary = df.groupby("stop_id", group_keys=False).apply(_agg_stop).reset_index()
        return stop_summary

    @staticmethod
    def calculate_headways_for_window(
        stop_times_df: pd.DataFrame,
        window_name: str,
    ) -> pd.DataFrame:
        """
        Calculates scheduled inter-arrival spacing (headways) for a designated operational window.
        
        Strict Rules:
          - Partition: (stop_id, route_id, direction_id)
          - Consecutive intervals: Delta t_k = (A_k - A_{k-1}) / 60 [minutes]
          - Intervals must NOT cross window boundaries: both A_{k-1} and A_k in [W_start, W_end)
          - Single arrival in window yields np.nan (NULL), never 0.
          - Returns interval-weighted mean, route-equal mean, pooled median, and valid group count.
        """
        if window_name not in HEADWAY_WINDOWS:
            raise ValueError(f"Unknown window name: {window_name}. Choose from {list(HEADWAY_WINDOWS.keys())}")

        w_start, w_end = HEADWAY_WINDOWS[window_name]
        df = stop_times_df.copy()

        # Filter trips whose arrival falls within window
        df_window = df[(df["arrival_seconds"] >= w_start) & (df["arrival_seconds"] < w_end)].copy()
        
        # Build grouping keys dynamically: include service_date when present
        group_keys = ["stop_id", "route_id", "direction_id"]
        if "service_date" in df_window.columns:
            group_keys.append("service_date")

        df_window = df_window.sort_values(by=group_keys + ["arrival_seconds"])

        # Compute consecutive arrival differences within each route-direction group
        df_window["prev_arrival"] = df_window.groupby(group_keys)["arrival_seconds"].shift(1)
        df_window["headway_min"] = (df_window["arrival_seconds"] - df_window["prev_arrival"]) / 60.0

        # Valid intervals are non-null
        valid_intervals = df_window.dropna(subset=["headway_min"]).copy()

        # Stop-level aggregations across valid route-direction groups
        # 1. Group-level summary
        group_summary = valid_intervals.groupby(group_keys).agg(
            n_intervals=("headway_min", "count"),
            interval_sum=("headway_min", "sum"),
            group_mean=("headway_min", "mean")
        ).reset_index()

        # 2. Stop-level aggregation
        stop_interval_weighted = group_summary.groupby("stop_id").agg(
            total_intervals=("n_intervals", "sum"),
            total_interval_sum=("interval_sum", "sum"),
            valid_route_dirs=("route_id", "count"),
            route_equal_mean=("group_mean", "mean")
        ).reset_index()

        stop_interval_weighted[f"mean_headway_interval_weighted_{window_name.lower()}"] = (
            stop_interval_weighted["total_interval_sum"] / stop_interval_weighted["total_intervals"]
        )
        stop_interval_weighted[f"mean_headway_route_equal_{window_name.lower()}"] = (
            stop_interval_weighted["route_equal_mean"]
        )
        stop_interval_weighted[f"valid_route_dirs_{window_name.lower()}"] = (
            stop_interval_weighted["valid_route_dirs"]
        )

        # 3. Pooled median headway per stop
        stop_median = valid_intervals.groupby("stop_id")["headway_min"].median().reset_index()
        stop_median = stop_median.rename(columns={"headway_min": f"median_headway_{window_name.lower()}"})

        res = stop_interval_weighted[[
            "stop_id",
            f"mean_headway_interval_weighted_{window_name.lower()}",
            f"mean_headway_route_equal_{window_name.lower()}",
            f"valid_route_dirs_{window_name.lower()}",
        ]].merge(stop_median, on="stop_id", how="left")

        return res

    @staticmethod
    def compute_demand_intensity(
        attributed_demand: float,
        mapped_visits: float,
    ) -> float:
        """
        Computes demand intensity proxy: I_s = D_{s, mapped} / v_{s, mapped}
        Units: estimated passengers / scheduled vehicle visit.
        Returns np.nan if mapped visits == 0 or demand is NaN.
        """
        if pd.isna(attributed_demand) or pd.isna(mapped_visits) or mapped_visits <= 0:
            return np.nan
        return float(attributed_demand) / float(mapped_visits)

    @staticmethod
    def classify_stop_eligibility(
        stops_feature_df: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Assigns mutually exclusive eligibility status following strict priority waterfall:
          1. EXCLUDED_ZERO_VISITS: v_s == 0
          2. EXCLUDED_UNAVAILABLE_DEMAND: D_s is NULL / NaN
          3. EXCLUDED_NO_AM_HEADWAY: AM Peak headway is NULL / NaN (< 2 arrivals)
          4. EXCLUDED_NON_FINITE_FEATURE: Any required feature is NaN/Inf
          5. ELIGIBLE: All 5 features valid, finite, and D_s >= 0
          
        Also preserves secondary diagnostic flags.
        Reconciles exactly to N_total and 100.00%.
        """
        df = stops_feature_df.copy()
        n_total = len(df)

        # Compute secondary diagnostic flags
        df["flag_zero_visits"] = df["total_visits"] <= 0
        df["flag_unavailable_demand"] = df["attributed_demand"].isna()
        df["flag_no_am_headway"] = df["mean_headway_interval_weighted_am_peak"].isna()
        df["flag_partial_demand"] = df["demand_coverage_status"] == "PARTIAL"

        primary_status = []
        for _, row in df.iterrows():
            if row["total_visits"] <= 0:
                primary_status.append("EXCLUDED_ZERO_VISITS")
            elif pd.isna(row["attributed_demand"]):
                primary_status.append("EXCLUDED_UNAVAILABLE_DEMAND")
            elif pd.isna(row["mean_headway_interval_weighted_am_peak"]):
                primary_status.append("EXCLUDED_NO_AM_HEADWAY")
            elif (
                pd.isna(row.get("service_span_hours", 1.0))
                or not np.isfinite(row.get("service_span_hours", 1.0))
                or not np.isfinite(row.get("routes_served", 1.0))
            ):
                primary_status.append("EXCLUDED_NON_FINITE_FEATURE")
            else:
                primary_status.append("ELIGIBLE")

        df["primary_eligibility_status"] = primary_status

        # Reconciliation table
        status_counts = df["primary_eligibility_status"].value_counts().to_dict()
        categories = [
            "ELIGIBLE",
            "EXCLUDED_ZERO_VISITS",
            "EXCLUDED_UNAVAILABLE_DEMAND",
            "EXCLUDED_NO_AM_HEADWAY",
            "EXCLUDED_NON_FINITE_FEATURE",
        ]
        reconciliation_table = {}
        sum_counts = 0
        for cat in categories:
            cnt = status_counts.get(cat, 0)
            pct = (cnt / n_total * 100.0) if n_total > 0 else 0.0
            reconciliation_table[cat] = {"count": cnt, "percentage": pct}
            sum_counts += cnt

        reconciliation_summary = {
            "total_stops": n_total,
            "sum_partition_counts": sum_counts,
            "is_fully_reconciled": (sum_counts == n_total),
            "table": reconciliation_table,
        }

        return df, reconciliation_summary
