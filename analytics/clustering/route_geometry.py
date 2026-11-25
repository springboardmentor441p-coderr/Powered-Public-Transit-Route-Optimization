"""
AI_RouteRanker - Phase 6.2 Route Geometry Module
Handles extraction, validation, projection, and downsampling of route-direction
representative GTFS shape trajectories.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from analytics.clustering.spatial_projection import SpatialProjector

# Canonical bounding box for Chicago transit network
LAT_MIN: float = 41.50
LAT_MAX: float = 42.25
LON_MIN: float = -88.10
LON_MAX: float = -87.40


class RouteGeometryExtractor:
    """
    Extracts, validates, projects, and downsamples representative GTFS shape polylines
    for all active route-direction patterns.
    """

    def __init__(self, target_downsample_dist: float = 50.0):
        """
        Args:
            target_downsample_dist: Target spacing in meters between consecutive vertices (default 50m).
        """
        self.target_dist = float(target_downsample_dist)
        self.projector = SpatialProjector()

    @staticmethod
    def select_representative_shapes(
        trips_df: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Identifies active route-direction patterns and selects the representative shape
        based on the highest scheduled trip count.

        Args:
            trips_df: DataFrame containing ['route_id', 'direction_id', 'trip_id', 'shape_id'].

        Returns:
            Tuple of:
              - rep_shapes_df: DataFrame with ['route_id', 'direction_id', 'representative_shape_id',
                                               'trip_count', 'total_route_dir_trips', 'shape_coverage_ratio',
                                               'alternative_shapes_count']
              - exclusions_df: DataFrame recording route-directions with no valid shape.
        """
        df = trips_df.copy()
        
        # Group by route_id and direction_id
        valid_trips = df.dropna(subset=["route_id", "direction_id"]).copy()
        valid_trips["direction_id"] = valid_trips["direction_id"].astype(int)

        rep_rows = []
        exclusions = []

        for (route_id, direction_id), group in valid_trips.groupby(["route_id", "direction_id"]):
            total_trips = len(group)
            with_shape = group.dropna(subset=["shape_id"]).copy()
            
            if len(with_shape) == 0:
                exclusions.append({
                    "route_id": str(route_id),
                    "direction_id": int(direction_id),
                    "reason": "NO_VALID_SHAPES_FOR_ACTIVE_TRIPS",
                    "total_trips": total_trips,
                })
                continue

            shape_counts = with_shape["shape_id"].value_counts()
            rep_shape_id = str(shape_counts.index[0])
            rep_count = int(shape_counts.iloc[0])
            alt_count = len(shape_counts) - 1
            cov_ratio = float(rep_count / total_trips) if total_trips > 0 else 0.0

            rep_rows.append({
                "route_id": str(route_id),
                "direction_id": int(direction_id),
                "representative_shape_id": rep_shape_id,
                "trip_count": rep_count,
                "total_route_dir_trips": total_trips,
                "shape_coverage_ratio": cov_ratio,
                "alternative_shapes_count": alt_count,
            })

        rep_shapes_df = pd.DataFrame(rep_rows)
        exclusions_df = pd.DataFrame(exclusions)
        return rep_shapes_df, exclusions_df

    def process_and_project_shape(
        self,
        shape_points_df: pd.DataFrame,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Validates, sorts, projects, and downsamples a single GTFS shape polyline.

        Args:
            shape_points_df: DataFrame containing ['shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence'].

        Returns:
            Tuple of:
              - downsampled_projected_coords: (M, 2) array of metric (x, y) coordinates.
              - metadata: Dict of summary statistics (raw count, downsampled count, total length, etc.).
        """
        df = shape_points_df.copy()

        # 1. Validation: check required columns
        required_cols = ["shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # 2. Validation: check finite values and drop NaNs
        if df[required_cols].isna().any().any():
            raise ValueError("Shape points contain NaN values!")

        # 3. Validation: check duplicate sequence records
        if df["shape_pt_sequence"].duplicated().any():
            raise ValueError("Duplicate shape_pt_sequence detected in shape points!")

        # 4. Sort strictly ascending by sequence
        df = df.sort_values("shape_pt_sequence").reset_index(drop=True)

        lats = df["shape_pt_lat"].values.astype(float)
        lons = df["shape_pt_lon"].values.astype(float)

        # 5. Validation: bounds check
        if np.any(lats < LAT_MIN) or np.any(lats > LAT_MAX) or np.any(lons < LON_MIN) or np.any(lons > LON_MAX):
            raise ValueError(f"Shape coordinates exceed Chicago bounding box [{LAT_MIN}, {LAT_MAX}], [{LON_MIN}, {LON_MAX}]!")

        if len(df) < 2:
            raise ValueError("Shape contains fewer than 2 points; cannot form a trajectory polyline.")

        # 6. Project to Euclidean (x, y) meters
        proj_x, proj_y = self.projector.forward(lats, lons)
        coords = np.column_stack([proj_x, proj_y])

        # 7. Calculate total cumulative path length
        diffs = np.diff(coords, axis=0)
        segment_lengths = np.sqrt(np.sum(diffs**2, axis=1))
        total_length_m = float(np.sum(segment_lengths))

        # 8. Downsample polyline preserving exact start and end points
        downsampled = self._downsample_polyline(coords, target_spacing=self.target_dist)

        metadata = {
            "raw_point_count": len(df),
            "downsampled_point_count": len(downsampled),
            "total_length_meters": total_length_m,
            "target_spacing_meters": self.target_dist,
            "start_point_projected": (float(coords[0, 0]), float(coords[0, 1])),
            "end_point_projected": (float(coords[-1, 0]), float(coords[-1, 1])),
        }
        return downsampled, metadata

    @staticmethod
    def _downsample_polyline(
        coords: np.ndarray,
        target_spacing: float = 50.0,
    ) -> np.ndarray:
        """
        Equidistant spatial downsampling along polyline path, strictly preserving endpoints.
        """
        if len(coords) <= 2:
            return coords.copy()

        diffs = np.diff(coords, axis=0)
        seg_lengths = np.sqrt(np.sum(diffs**2, axis=1))
        cum_dist = np.insert(np.cumsum(seg_lengths), 0, 0.0)
        total_dist = cum_dist[-1]

        if total_dist <= target_spacing:
            # If line is shorter than target spacing, keep only start and end
            return np.array([coords[0], coords[-1]])

        # Generate sample distances
        sample_distances = np.arange(0.0, total_dist, target_spacing)
        if total_dist - sample_distances[-1] > (target_spacing * 0.25):
            sample_distances = np.append(sample_distances, total_dist)
        else:
            sample_distances[-1] = total_dist

        # Linear interpolation along cumulative path
        downsampled_x = np.interp(sample_distances, cum_dist, coords[:, 0])
        downsampled_y = np.interp(sample_distances, cum_dist, coords[:, 1])

        # Explicitly ensure exact start and end points match
        downsampled = np.column_stack([downsampled_x, downsampled_y])
        downsampled[0] = coords[0]
        downsampled[-1] = coords[-1]

        return downsampled
