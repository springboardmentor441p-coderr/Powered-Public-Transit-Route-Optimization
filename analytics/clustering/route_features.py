"""
AI_RouteRanker - Phase 6.2 Route Operational Features Module
Extracts the five canonical route-level operational features for all 133 GTFS routes:
  1. ln(total_scheduled_trips + 1)
  2. service_span_hours
  3. am_peak_mean_headway_min (using scheduled DEPARTURES within [07:00, 09:00))
  4. route_length_km
  5. unique_stops_count
Preserves bus/rail route_type and maintains missing demand without false zeros.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd


class RouteFeatureExtractor:
    """
    Computes route-level operational and service features on the representative service date.
    """

    AM_START_SECONDS: int = 25200   # 07:00:00 (inclusive)
    AM_END_SECONDS: int = 32400     # 09:00:00 (exclusive: [25200, 32400))

    @classmethod
    def compute_route_features(
        cls,
        routes_df: pd.DataFrame,
        trips_df: pd.DataFrame,
        stop_times_df: pd.DataFrame,
        route_lengths_km: Dict[str, float],
        ridership_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Computes the complete route-level operational feature dataset.

        Args:
            routes_df: DataFrame of all routes with ['route_id', 'route_short_name', 'route_type'].
            trips_df: DataFrame of active trips on representative date with ['trip_id', 'route_id', 'direction_id'].
                      Can optionally include 'service_date'.
            stop_times_df: DataFrame of active stop times with ['trip_id', 'stop_id', 'arrival_seconds', 'departure_seconds'].
            route_lengths_km: Dict mapping route_id -> aggregated length in km.
            ridership_df: Optional DataFrame with ['route_id', 'mean_daily_rides'].

        Returns:
            DataFrame containing route feature records with complete operational metrics.
        """
        all_routes = routes_df[["route_id", "route_short_name", "route_type"]].drop_duplicates().copy()
        all_routes["route_id"] = all_routes["route_id"].astype(str)

        # Merge trips and stop_times avoiding column collisions
        trip_cols = ["trip_id", "route_id", "direction_id"]
        if "service_date" in trips_df.columns:
            trip_cols.append("service_date")

        cols_to_merge = [c for c in trip_cols if c == "trip_id" or c not in stop_times_df.columns]
        if len(cols_to_merge) > 1:
            trip_stop = stop_times_df.merge(
                trips_df[cols_to_merge],
                on="trip_id",
                how="inner"
            )
        else:
            trip_stop = stop_times_df.copy()
        trip_stop["route_id"] = trip_stop["route_id"].astype(str)

        feature_rows = []

        for _, route_row in all_routes.iterrows():
            r_id = route_row["route_id"]
            short_name = route_row["route_short_name"]
            r_type = int(route_row["route_type"])

            r_trips = trips_df[trips_df["route_id"].astype(str) == r_id]
            r_st = trip_stop[trip_stop["route_id"] == r_id]

            total_trips = len(r_trips)
            log_trips = float(np.log1p(total_trips))

            # Service span: (max_departure - min_arrival) / 3600 preserving hours >= 24
            if len(r_st) > 0:
                min_arr = r_st["arrival_seconds"].min()
                max_dep = r_st["departure_seconds"].max()
                span_hours = float((max_dep - min_arr) / 3600.0)
                unique_stops = int(r_st["stop_id"].nunique())
            else:
                span_hours = 0.0
                unique_stops = 0

            # Scheduled AM peak headway using scheduled DEPARTURE times in [25200, 32400)
            am_st = r_st[(r_st["departure_seconds"] >= cls.AM_START_SECONDS) & (r_st["departure_seconds"] < cls.AM_END_SECONDS)].copy()
            am_hw = cls._calculate_route_am_headway(am_st)

            # Route length
            r_len = float(route_lengths_km.get(r_id, np.nan))

            feature_rows.append({
                "route_id": r_id,
                "route_short_name": short_name,
                "route_type": r_type,
                "is_rail": (r_type == 1),
                "total_scheduled_trips": total_trips,
                "log_scheduled_trips": log_trips,
                "service_span_hours": span_hours,
                "am_peak_mean_headway_min": am_hw,
                "route_length_km": r_len,
                "unique_stops_count": unique_stops,
            })

        feat_df = pd.DataFrame(feature_rows)

        # Merge supplementary descriptive ridership if provided (WITHOUT turning NaN into 0)
        if ridership_df is not None and not ridership_df.empty:
            r_map = ridership_df[["route_id", "mean_daily_rides"]].copy()
            r_map["route_id"] = r_map["route_id"].astype(str)
            feat_df = feat_df.merge(r_map, on="route_id", how="left")
        else:
            feat_df["mean_daily_rides"] = np.nan

        return feat_df

    @classmethod
    def _calculate_route_am_headway(
        cls,
        am_stop_times: pd.DataFrame,
    ) -> float:
        """
        Calculates scheduled AM peak mean headway in minutes across stops and directions.
        Methodology:
          - Consecutive scheduled DEPARTURE differences at the same stop_id and direction_id.
          - If 'service_date' is present, groups by service_date as well to prevent cross-date intervals.
          - Half-open window [25200, 32400) seconds.
          - Returns np.nan if fewer than 2 departures exist within valid stop-direction groups.
        """
        if len(am_stop_times) < 2:
            return np.nan

        group_keys = ["stop_id", "direction_id"]
        if "service_date" in am_stop_times.columns:
            group_keys.append("service_date")

        df = am_stop_times.sort_values(by=group_keys + ["departure_seconds"]).copy()
        df["prev_dep"] = df.groupby(group_keys)["departure_seconds"].shift(1)
        df["hw_sec"] = df["departure_seconds"] - df["prev_dep"]

        valid_hw = df.dropna(subset=["hw_sec"])
        if len(valid_hw) == 0:
            return np.nan

        mean_sec = valid_hw["hw_sec"].mean()
        return float(mean_sec / 60.0)
