"""Network Coverage Service for RouteRanker."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import pandas as pd

from app.core.database import db
from app.schemas.common import PaginatedResponse
from app.schemas.coverage import (
    CoverageSummaryResponse,
    ServiceDensityDistribution,
    TransferHubItem,
)
from app.schemas.stops import StopItem

logger = logging.getLogger(__name__)


class CoverageService:
    """Calculates spatial and service density coverage across all transit stops."""

    @staticmethod
    def get_coverage_summary() -> CoverageSummaryResponse:
        """Calculate network-wide stop coverage and transfer hub distribution."""
        df = db.get_table("stop_coverage")

        total_stops = len(df)
        hubs = df[df["is_transfer_hub"]]
        total_hubs = len(hubs)

        avg_routes = round(float(df["routes_count"].mean()), 2) if total_stops else 0.0
        max_routes = int(df["routes_count"].max()) if total_stops else 0

        # Distribution
        density_dist = ServiceDensityDistribution(
            single_route=int((df["routes_count"] == 1).sum()),
            two_to_four_routes=int(((df["routes_count"] >= 2) & (df["routes_count"] <= 4)).sum()),
            five_to_nine_routes=int(((df["routes_count"] >= 5) & (df["routes_count"] <= 9)).sum()),
            ten_plus_routes=int((df["routes_count"] >= 10).sum()),
        )

        # Top transfer hubs
        top_hubs_df = df.sort_values(by=["routes_count", "trips_per_day"], ascending=False).head(10)
        top_hubs = [
            TransferHubItem(
                stop_id=str(r["stop_id"]),
                stop_name=str(r.get("stop_name", "")),
                stop_lat=float(r.get("stop_lat", 0.0)),
                stop_lon=float(r.get("stop_lon", 0.0)),
                routes_count=int(r.get("routes_count", 0)),
                trips_per_day=int(r.get("trips_per_day", 0)),
                sample_routes=[s for s in str(r.get("routes_served", "")).split(",") if s][:6],
            )
            for _, r in top_hubs_df.iterrows()
        ]

        bounds = {
            "min_lat": float(df["stop_lat"].min()) if total_stops else 0.0,
            "max_lat": float(df["stop_lat"].max()) if total_stops else 0.0,
            "min_lon": float(df["stop_lon"].min()) if total_stops else 0.0,
            "max_lon": float(df["stop_lon"].max()) if total_stops else 0.0,
        }

        top_shared_stops = [
            {
                "stop_id": str(r["stop_id"]),
                "stop_name": str(r.get("stop_name", "")),
                "route_count": int(r.get("routes_count", 0)),
                "stop_lat": float(r.get("stop_lat", 0.0)),
                "stop_lon": float(r.get("stop_lon", 0.0)),
            }
            for _, r in top_hubs_df.iterrows()
        ]

        return CoverageSummaryResponse(
            total_stops=total_stops,
            total_transfer_hubs=total_hubs,
            avg_routes_per_stop=avg_routes,
            max_routes_at_single_stop=max_routes,
            density_distribution=density_dist,
            top_transfer_hubs=top_hubs,
            geographic_bounds=bounds,
            stops_single_route=int((df["routes_count"] == 1).sum()),
            stops_multi_route=int((df["routes_count"] > 1).sum()),
            max_routes_per_stop=max_routes,
            top_shared_stops=top_shared_stops,
        )

    @staticmethod
    def get_coverage_stops(
        page: int = 1,
        page_size: int = 50,
        is_hub_only: bool = False,
        search: Optional[str] = None,
    ) -> PaginatedResponse[StopItem]:
        """Fetch paginated stops with route count and hub indicators."""
        df = db.get_table("stop_coverage")

        if is_hub_only:
            df = df[df["is_transfer_hub"]]

        if search:
            s = search.strip().lower()
            df = df[
                df["stop_name"].astype(str).str.lower().str.contains(s)
                | df["stop_id"].astype(str).str.lower().str.contains(s)
            ]

        df = df.sort_values(by="routes_count", ascending=False)

        total = len(df)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_df = df.iloc[start_idx:end_idx]

        items = [
            StopItem(
                stop_id=str(r["stop_id"]),
                stop_name=str(r.get("stop_name", "")),
                stop_lat=float(r.get("stop_lat", 0.0)),
                stop_lon=float(r.get("stop_lon", 0.0)),
                routes_count=int(r.get("routes_count", 0)),
                trips_per_day=int(r.get("trips_per_day", 0)),
                is_transfer_hub=bool(r.get("is_transfer_hub", False)),
                routes_served=str(r.get("routes_served", "")),
            )
            for _, r in page_df.iterrows()
        ]

        return PaginatedResponse[StopItem](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

