"""Route Overlap Analysis Service for RouteRanker."""

from __future__ import annotations

import logging
from typing import List, Optional
import pandas as pd

from app.core.database import db
from app.schemas.overlap import OverlapPairItem, RouteOverlapDetailResponse

logger = logging.getLogger(__name__)


class OverlapService:
    """Identifies overlapping route corridors to optimize network efficiency."""

    @staticmethod
    def get_top_overlaps(limit: int = 50, min_overlap_pct: float = 20.0) -> List[OverlapPairItem]:
        """Fetch the highest overlapping route pairs across the network."""
        df = db.get_table("route_stop_overlap")
        filtered = df[df["jaccard_overlap_pct"] >= min_overlap_pct]
        sorted_df = filtered.sort_values(by="jaccard_overlap_pct", ascending=False).head(limit)

        return [
            OverlapPairItem(
                route_id_a=str(r["route_id_a"]),
                route_id_b=str(r["route_id_b"]),
                route_short_name_a=str(r.get("route_short_name_a", "")),
                route_short_name_b=str(r.get("route_short_name_b", "")),
                shared_stops=int(r.get("shared_stops", 0)),
                stops_count_a=int(r.get("stops_count_a", 0)),
                stops_count_b=int(r.get("stops_count_b", 0)),
                overlap_ratio_a=float(r.get("overlap_ratio_a", 0.0)),
                overlap_ratio_b=float(r.get("overlap_ratio_b", 0.0)),
                jaccard_overlap_pct=float(r.get("jaccard_overlap_pct", 0.0)),
            )
            for _, r in sorted_df.iterrows()
        ]

    @staticmethod
    def get_route_overlap(route_id: str) -> Optional[RouteOverlapDetailResponse]:
        """Fetch all routes that overlap with a specific route."""
        df = db.get_table("route_stop_overlap")
        r_id = str(route_id).strip()

        matches = df[(df["route_id_a"].astype(str) == r_id) | (df["route_id_b"].astype(str) == r_id)]
        if matches.empty:
            # Check if route exists in routes table
            routes_df = db.get_table("routes")
            r_row = routes_df[routes_df["route_id"].astype(str) == r_id]
            if r_row.empty:
                return None
            short_name = str(r_row.iloc[0].get("route_short_name", r_id))
            return RouteOverlapDetailResponse(
                route_id=r_id,
                route_short_name=short_name,
                total_stops=0,
                overlapping_routes_count=0,
                highest_jaccard_overlap_pct=0.0,
                overlapping_routes=[],
            )

        # Determine short name and total stops
        first_row = matches.iloc[0]
        if str(first_row["route_id_a"]) == r_id:
            short_name = str(first_row.get("route_short_name_a", r_id))
            total_stops = int(first_row.get("stops_count_a", 0))
        else:
            short_name = str(first_row.get("route_short_name_b", r_id))
            total_stops = int(first_row.get("stops_count_b", 0))

        sorted_matches = matches.sort_values(by="jaccard_overlap_pct", ascending=False)
        highest_pct = float(sorted_matches.iloc[0]["jaccard_overlap_pct"])

        items = [
            OverlapPairItem(
                route_id_a=str(r["route_id_a"]),
                route_id_b=str(r["route_id_b"]),
                route_short_name_a=str(r.get("route_short_name_a", "")),
                route_short_name_b=str(r.get("route_short_name_b", "")),
                shared_stops=int(r.get("shared_stops", 0)),
                stops_count_a=int(r.get("stops_count_a", 0)),
                stops_count_b=int(r.get("stops_count_b", 0)),
                overlap_ratio_a=float(r.get("overlap_ratio_a", 0.0)),
                overlap_ratio_b=float(r.get("overlap_ratio_b", 0.0)),
                jaccard_overlap_pct=float(r.get("jaccard_overlap_pct", 0.0)),
            )
            for _, r in sorted_matches.iterrows()
        ]

        return RouteOverlapDetailResponse(
            route_id=r_id,
            route_short_name=short_name,
            total_stops=total_stops,
            overlapping_routes_count=len(items),
            highest_jaccard_overlap_pct=highest_pct,
            overlapping_routes=items,
        )

