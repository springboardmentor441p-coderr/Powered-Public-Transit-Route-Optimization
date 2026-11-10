"""Feature Engineering Module for RouteRanker.

Extracts rich, schedule-derived operational features for every bus route.
Features are strictly derived from GTFS timetables and stop coordinates.
Never fabricates ridership, congestion, or unobserved passenger demand.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False

logger = logging.getLogger(__name__)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two GPS coordinates in kilometers."""
    if any(pd.isna([lat1, lon1, lat2, lon2])):
        return 0.0

    r = 6371.0088  # Earth mean radius in km
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    return float(r * c)


class RouteFeatureEngineer:
    """Computes ML features for transit routes based purely on GTFS schedules."""

    def __init__(self, processed_dir: Optional[Path] = None) -> None:
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.processed_dir = processed_dir or (self.project_root / "data" / "processed")

    def _read_table(self, table_name: str) -> pd.DataFrame:
        """Read parquet table from processed directory."""
        path = self.processed_dir / f"{table_name}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Parquet table not found: {path}. Run preprocessing first.")
        if HAS_POLARS:
            try:
                return pl.read_parquet(path).to_pandas()
            except Exception:
                return pd.DataFrame(pl.read_parquet(path).to_dict())
        return pd.read_parquet(path)

    def compute_route_distances(self, route_stops_df: pd.DataFrame) -> Dict[str, float]:
        """Compute estimated route distance in kilometers from sequential stop coordinates."""
        distances: Dict[str, float] = {}
        # Group by route and direction
        for (route_id, direction_id), group in route_stops_df.groupby(["route_id", "direction_id"]):
            sorted_stops = group.sort_values(by="stop_sequence")
            lats = sorted_stops["stop_lat"].values
            lons = sorted_stops["stop_lon"].values
            total_dist = 0.0
            for i in range(len(lats) - 1):
                if not (np.isnan(lats[i]) or np.isnan(lons[i]) or np.isnan(lats[i+1]) or np.isnan(lons[i+1])):
                    total_dist += haversine_distance_km(lats[i], lons[i], lats[i+1], lons[i+1])
            # Store max distance across directions for the route
            if route_id not in distances or total_dist > distances[route_id]:
                distances[route_id] = round(total_dist, 2)
        return distances

    def compute_temporal_features(
        self,
        trips_df: pd.DataFrame,
        stop_times_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Extract departure distributions, peak/off-peak counts, and headway metrics."""
        # Find first departure time of each trip
        first_deps = stop_times_df.groupby("trip_id")["departure_seconds"].min().reset_index()
        trip_dep = trips_df[["trip_id", "route_id", "direction_id"]].merge(first_deps, on="trip_id")

        features_list = []
        for route_id, group in trip_dep.groupby("route_id"):
            deps = group["departure_seconds"].sort_values().values
            n_trips = len(deps)
            if n_trips == 0:
                continue

            # Peak intervals (seconds from midnight)
            # Morning Peak: 06:00 - 10:00 (21600 - 36000)
            morning_peak = np.sum((deps >= 21600) & (deps < 36000))
            # Evening Peak: 16:00 - 20:00 (57600 - 72000)
            evening_peak = np.sum((deps >= 57600) & (deps < 72000))
            # Mid-day Off-Peak: 10:00 - 16:00 (36000 - 57600)
            off_peak = np.sum((deps >= 36000) & (deps < 57600))
            # Night / Early: < 21600 or >= 72000
            night_trips = np.sum((deps < 21600) | (deps >= 72000))

            peak_ratio = round((morning_peak + evening_peak) / max(1, n_trips), 3)

            # Headways (consecutive departures)
            if n_trips > 1:
                headways_min = np.diff(deps) / 60.0
                # Filter out overnight gaps (> 240 mins) for headway statistics
                active_headways = headways_min[headways_min < 240.0]
                if len(active_headways) > 0:
                    avg_headway = round(float(np.mean(active_headways)), 1)
                    std_headway = round(float(np.std(active_headways)), 1)
                    headway_cv = round(float(std_headway / max(0.1, avg_headway)), 2)
                else:
                    avg_headway = 60.0
                    std_headway = 0.0
                    headway_cv = 0.0
            else:
                avg_headway = 120.0
                std_headway = 0.0
                headway_cv = 0.0

            features_list.append({
                "route_id": route_id,
                "peak_morning_trips": int(morning_peak),
                "peak_evening_trips": int(evening_peak),
                "off_peak_trips": int(off_peak),
                "night_trips": int(night_trips),
                "peak_ratio": peak_ratio,
                "avg_headway_min": avg_headway,
                "headway_std_min": std_headway,
                "headway_cv": headway_cv,
            })

        return pd.DataFrame(features_list)

    def build_features(self) -> pd.DataFrame:
        """Build complete operational feature matrix for all routes."""
        logger.info("Building route features from processed GTFS tables...")
        routes_df = self._read_table("routes")
        trips_df = self._read_table("trips")
        stop_times_df = self._read_table("stop_times")
        route_stops_df = self._read_table("route_stops")
        summary_df = self._read_table("route_service_summary")
        coverage_df = self._read_table("stop_coverage")

        # 1. Distances
        route_distances = self.compute_route_distances(route_stops_df)

        # 2. Temporal features
        temporal_df = self.compute_temporal_features(trips_df, stop_times_df)

        # 3. Hub connections count
        hubs = set(coverage_df[coverage_df["is_transfer_hub"]]["stop_id"])
        hubs_per_route = route_stops_df[route_stops_df["stop_id"].isin(hubs)].groupby("route_id")["stop_id"].nunique().to_dict()

        # 4. Stop counts per route
        stops_per_route = route_stops_df.groupby("route_id")["stop_id"].nunique().to_dict()

        # 5. Merge all into comprehensive feature matrix
        df = summary_df.copy()
        df = df.merge(temporal_df, on="route_id", how="left").fillna({
            "peak_morning_trips": 0,
            "peak_evening_trips": 0,
            "off_peak_trips": 0,
            "night_trips": 0,
            "peak_ratio": 0.0,
            "avg_headway_min": 120.0,
            "headway_std_min": 0.0,
            "headway_cv": 0.0,
        })

        df["estimated_distance_km"] = df["route_id"].map(route_distances).fillna(10.0)
        df["stop_count"] = df["route_id"].map(stops_per_route).fillna(df["avg_stops_per_trip"]).astype(int)
        df["hub_stops_count"] = df["route_id"].map(hubs_per_route).fillna(0).astype(int)

        # Estimated average speed (km/h) = distance_km / (avg_trip_duration_min / 60)
        dur_hours = (df["avg_trip_duration_min"] / 60.0).clip(lower=0.1)
        df["avg_speed_kmh"] = (df["estimated_distance_km"] / dur_hours).round(1).clip(lower=5.0, upper=60.0)

        # Stop density per km
        df["stop_density_per_km"] = (df["stop_count"] / df["estimated_distance_km"].clip(lower=1.0)).round(2)

        # Direction balance ratio (0 to 1)
        dir0 = df["direction_0_trips"]
        dir1 = df["direction_1_trips"]
        max_dir = np.maximum(dir0, dir1).replace(0, 1)
        min_dir = np.minimum(dir0, dir1)
        df["direction_balance_ratio"] = (min_dir / max_dir).round(3)

        # High frequency classification (schedule-derived)
        df["high_frequency_flag"] = (
            (df["total_trips"] >= 30) & (df["avg_headway_min"] <= 20.0)
        ).astype(int)

        # Data provenance label
        df["data_source"] = "GTFS_Timetable_Schedule_Derived"

        # Save route_features.parquet
        output_path = self.processed_dir / "route_features.parquet"
        if HAS_POLARS:
            try:
                pl.from_pandas(df).write_parquet(output_path)
            except Exception:
                pl.from_dict(df.to_dict(orient="list")).write_parquet(output_path)
        else:
            df.to_parquet(output_path, index=False)

        logger.info(f"Generated route_features.parquet with {len(df)} routes and {df.shape[1]} features.")
        return df
