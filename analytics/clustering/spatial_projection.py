"""
AI_RouteRanker - Phase 6.1 Spatial Projection Module
Implements localized conformal Equirectangular projection and geodesic distance functions
using pure NumPy without external C/C++ DLL dependencies.
"""

from typing import Tuple, Union
import numpy as np


class SpatialProjector:
    """
    Local Equirectangular planar projection for the Chicago transit network.
    
    Parameters are calibrated to the canonical CTA stop bounding box:
      Latitude:  [41.6441576, 42.0731530]
      Longitude: [-87.90422307, -87.52569948]
      Centroid:  phi_0 = 41.8586553 deg N, lambda_0 = -87.7149613 deg W
      Earth Radius: R = 6,371,008.8 meters (WGS 84 mean radius)
    """

    DEFAULT_LAT_0: float = 41.8586553
    DEFAULT_LON_0: float = -87.7149613
    EARTH_RADIUS_METERS: float = 6371008.8

    def __init__(
        self,
        lat_0: float = DEFAULT_LAT_0,
        lon_0: float = DEFAULT_LON_0,
        radius: float = EARTH_RADIUS_METERS,
    ):
        self.lat_0 = float(lat_0)
        self.lon_0 = float(lon_0)
        self.radius = float(radius)
        self.phi_0_rad = np.radians(self.lat_0)
        self.cos_phi_0 = np.cos(self.phi_0_rad)

    def forward(
        self, lat: Union[float, np.ndarray], lon: Union[float, np.ndarray]
    ) -> Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]:
        """
        Forward projection: (latitude, longitude) in degrees -> (x, y) in meters.
        
        Equations:
          x = R * (lambda - lambda_0) * cos(phi_0)
          y = R * (phi - phi_0)
        """
        lat_rad = np.radians(lat)
        lon_rad = np.radians(lon)
        phi_0_rad = self.phi_0_rad
        lon_0_rad = np.radians(self.lon_0)

        x = self.radius * (lon_rad - lon_0_rad) * self.cos_phi_0
        y = self.radius * (lat_rad - phi_0_rad)
        return x, y

    def inverse(
        self, x: Union[float, np.ndarray], y: Union[float, np.ndarray]
    ) -> Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]:
        """
        Inverse projection: (x, y) in meters -> (latitude, longitude) in degrees.
        
        Equations:
          phi = phi_0 + (y / R)
          lambda = lambda_0 + x / (R * cos(phi_0))
        """
        lat_rad = self.phi_0_rad + (y / self.radius)
        lon_rad = np.radians(self.lon_0) + (x / (self.radius * self.cos_phi_0))
        return np.degrees(lat_rad), np.degrees(lon_rad)

    @classmethod
    def haversine_distance(
        cls,
        lat1: Union[float, np.ndarray],
        lon1: Union[float, np.ndarray],
        lat2: Union[float, np.ndarray],
        lon2: Union[float, np.ndarray],
        radius: float = EARTH_RADIUS_METERS,
    ) -> Union[float, np.ndarray]:
        """
        Computes great-circle distance in meters using the Haversine formula.
        """
        phi1 = np.radians(lat1)
        phi2 = np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlam = np.radians(lon2 - lon1)

        a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2.0) ** 2
        c = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
        return radius * c

    def projected_euclidean_distance(
        self,
        lat1: Union[float, np.ndarray],
        lon1: Union[float, np.ndarray],
        lat2: Union[float, np.ndarray],
        lon2: Union[float, np.ndarray],
    ) -> Union[float, np.ndarray]:
        """
        Computes Euclidean distance in projected coordinates (meters).
        """
        x1, y1 = self.forward(lat1, lon1)
        x2, y2 = self.forward(lat2, lon2)
        return np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    def calculate_distortion(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> Tuple[float, float, float]:
        """
        Calculates projection distortion against true Haversine distance.
        Returns: (d_haversine, d_projected, relative_error_percentage)
        """
        d_hav = float(self.haversine_distance(lat1, lon1, lat2, lon2, self.radius))
        d_proj = float(self.projected_euclidean_distance(lat1, lon1, lat2, lon2))
        err_pct = (abs(d_proj - d_hav) / d_hav * 100.0) if d_hav > 0 else 0.0
        return d_hav, d_proj, err_pct
