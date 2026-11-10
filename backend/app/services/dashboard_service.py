"""Dashboard Overview Service for RouteRanker."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List
import pandas as pd

from app.core.config import settings
from app.core.database import db
from app.schemas.dashboard import DashboardSummaryResponse, TopRouteItem

logger = logging.getLogger(__name__)


class DashboardService:
    """Aggregates executive-level metrics and system performance indicators."""

    @staticmethod
    def get_dashboard_summary() -> DashboardSummaryResponse:
        """Calculate system-level capacity metrics from GTFS schedules."""
        routes_df = db.get_table("route_features")
        stops_df = db.get_table("stops")
        trips_df = db.get_table("trips")
        coverage_df = db.get_table("stop_coverage")

        total_routes = len(routes_df)
        total_stops = len(stops_df)
        total_trips = len(trips_df)

        hf_count = int(routes_df["high_frequency_flag"].sum()) if "high_frequency_flag" in routes_df.columns else 0

        # Vehicle hours = sum(trips * (duration_min / 60))
        veh_hours = float((routes_df["total_trips"] * (routes_df["avg_trip_duration_min"] / 60.0)).sum())
        # Vehicle km = sum(trips * distance_km)
        veh_km = float((routes_df["total_trips"] * routes_df["estimated_distance_km"]).sum())

        avg_headway = float(routes_df["avg_headway_min"].mean()) if total_routes else 0.0
        avg_duration = float(routes_df["avg_trip_duration_min"].mean()) if total_routes else 0.0
        avg_stops = float(routes_df["stop_count"].mean()) if total_routes else 0.0
        avg_trips = float(routes_df["total_trips"].mean()) if total_routes else 0.0

        # Read data quality score from JSON report if available
        q_score = 100.0
        q_report_path = settings.DATA_PROCESSED_DIR / "data_quality_report.json"
        if q_report_path.exists():
            try:
                with open(q_report_path, "r", encoding="utf-8") as f:
                    q_data = json.load(f)
                    q_score = float(q_data.get("quality_score", 100.0))
            except Exception:
                pass

        # Top 5 most frequent routes
        top_df = routes_df.sort_values(by="total_trips", ascending=False).head(5)
        top_routes = [
            TopRouteItem(
                route_id=str(r["route_id"]),
                route_short_name=str(r.get("route_short_name", "")),
                route_long_name=str(r.get("route_long_name", "")),
                total_trips=int(r.get("total_trips", 0)),
                trip_count=int(r.get("total_trips", 0)),
                stop_count=int(r.get("stop_count", 0)),
                avg_headway_min=float(r.get("avg_headway_min", 0.0)),
                service_span_hours=float(r.get("service_span_hours", 0.0)),
            )
            for _, r in top_df.iterrows()
        ]

        # Top 15 routes by trips for frontend charts
        top_15_trips = routes_df.sort_values(by="total_trips", ascending=False).head(15)
        routes_by_trips = [
            {
                "route_id": str(r["route_id"]),
                "route_short_name": str(r.get("route_short_name", "")),
                "trip_count": int(r.get("total_trips", 0)),
            }
            for _, r in top_15_trips.iterrows()
        ]

        # Top 15 routes by stops for frontend charts
        top_15_stops = routes_df.sort_values(by="stop_count", ascending=False).head(15)
        routes_by_stops = [
            {
                "route_id": str(r["route_id"]),
                "route_short_name": str(r.get("route_short_name", "")),
                "stop_count": int(r.get("stop_count", 0)),
            }
            for _, r in top_15_stops.iterrows()
        ]

        # Service distribution by calendar
        service_counts = trips_df["service_id"].value_counts().to_dict()
        service_dist = [
            {"service_id": str(k), "trip_count": int(v)}
            for k, v in service_counts.items()
        ]

        # Multi-route stops distribution
        routes_per_stop = coverage_df["routes_count"].value_counts().sort_index()
        # Group into buckets: 1, 2-4, 5-9, 10+
        multi_stops = [
            {"stop_count": 1, "num_stops": int((coverage_df["routes_count"] == 1).sum())},
            {"stop_count": 2, "num_stops": int(((coverage_df["routes_count"] >= 2) & (coverage_df["routes_count"] <= 4)).sum())},
            {"stop_count": 5, "num_stops": int(((coverage_df["routes_count"] >= 5) & (coverage_df["routes_count"] <= 9)).sum())},
            {"stop_count": 10, "num_stops": int((coverage_df["routes_count"] >= 10).sum())},
        ]

        # Trip distribution buckets
        trip_dist = [
            {"bucket": "1-10", "count": int((routes_df["total_trips"] <= 10).sum())},
            {"bucket": "11-25", "count": int(((routes_df["total_trips"] > 10) & (routes_df["total_trips"] <= 25)).sum())},
            {"bucket": "26-50", "count": int(((routes_df["total_trips"] > 25) & (routes_df["total_trips"] <= 50)).sum())},
            {"bucket": "50+", "count": int((routes_df["total_trips"] > 50).sum())},
        ]

        return DashboardSummaryResponse(
            total_routes=total_routes,
            total_stops=total_stops,
            total_trips=total_trips,
            total_service_ids=len(service_counts),
            avg_stops_per_route=round(avg_stops, 1),
            avg_trips_per_route=round(avg_trips, 1),
            high_frequency_routes_count=hf_count,
            total_scheduled_vehicle_hours=round(veh_hours, 1),
            total_scheduled_vehicle_km=round(veh_km, 1),
            system_avg_headway_min=round(avg_headway, 1),
            system_avg_trip_duration_min=round(avg_duration, 1),
            agency_name="MTC (Metropolitan Transport Corporation Chennai)",
            data_quality_score=q_score,
            top_frequent_routes=top_routes,
            top_routes_by_trips=routes_by_trips,
            top_routes_by_stops=routes_by_stops,
            trip_distribution=trip_dist,
            multi_route_stops=multi_stops,
            service_distribution=service_dist,
        )
