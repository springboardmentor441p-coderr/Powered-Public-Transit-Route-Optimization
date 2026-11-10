"""Route Business Logic Service for RouteRanker."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from app.core.database import db
from app.schemas.common import PaginatedResponse
from app.schemas.routes import (
    HourlyDepartureDistribution,
    RouteDetailResponse,
    RouteItem,
    RouteScheduleResponse,
    RouteStopItem,
    RouteStopsResponse,
    RouteTripItem,
    RouteTripsResponse,
    ScheduleEntry,
)

logger = logging.getLogger(__name__)


class RouteService:
    """Handles route querying, stops sequence retrieval, and timetable analytics."""

    @staticmethod
    def get_routes(
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
        min_trips: Optional[int] = None,
        sort_by: str = "total_trips",
        sort_order: str = "desc",
    ) -> PaginatedResponse[RouteItem]:
        """Fetch paginated transit routes with optional search and filtering."""
        df = db.get_table("route_features")

        if search:
            s = search.strip().lower()
            df = df[
                df["route_short_name"].astype(str).str.lower().str.contains(s)
                | df["route_long_name"].astype(str).str.lower().str.contains(s)
                | df["route_id"].astype(str).str.lower().str.contains(s)
            ]

        if min_trips is not None and min_trips > 0:
            df = df[df["total_trips"] >= min_trips]

        # Sorting
        if sort_by in df.columns:
            ascending = sort_order.lower() == "asc"
            df = df.sort_values(by=sort_by, ascending=ascending)

        total = len(df)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_df = df.iloc[start_idx:end_idx]

        items = [
            RouteItem(
                route_id=str(row["route_id"]),
                agency_id=str(row.get("agency_id", "69")),
                route_short_name=str(row.get("route_short_name", "")),
                route_long_name=str(row.get("route_long_name", "")),
                route_type=int(row.get("route_type", 3)),
                total_trips=int(row.get("total_trips", 0)),
                service_span_hours=float(row.get("service_span_hours", 0.0)),
                avg_trip_duration_min=float(row.get("avg_trip_duration_min", 0.0)),
                stop_count=int(row.get("stop_count", 0)),
                estimated_distance_km=float(row.get("estimated_distance_km", 0.0)),
                high_frequency_flag=int(row.get("high_frequency_flag", 0)),
            )
            for _, row in page_df.iterrows()
        ]

        return PaginatedResponse[RouteItem](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def get_route_by_id(route_id: str) -> Optional[RouteDetailResponse]:
        """Fetch operational details for a specific route."""
        df = db.get_table("route_features")
        matches = df[df["route_id"].astype(str) == str(route_id).strip()]
        if matches.empty:
            return None

        row = matches.iloc[0]
        return RouteDetailResponse(
            route_id=str(row["route_id"]),
            agency_id=str(row.get("agency_id", "69")),
            agency_name="MTC",
            route_short_name=str(row.get("route_short_name", "")),
            route_long_name=str(row.get("route_long_name", "")),
            route_type=int(row.get("route_type", 3)),
            total_trips=int(row.get("total_trips", 0)),
            direction_0_trips=int(row.get("direction_0_trips", 0)),
            direction_1_trips=int(row.get("direction_1_trips", 0)),
            first_departure_time=str(row.get("first_departure_time", "N/A")),
            last_departure_time=str(row.get("last_departure_time", "N/A")),
            service_span_hours=float(row.get("service_span_hours", 0.0)),
            avg_trip_duration_min=float(row.get("avg_trip_duration_min", 0.0)),
            min_trip_duration_min=float(row.get("min_trip_duration_min", 0.0)),
            max_trip_duration_min=float(row.get("max_trip_duration_min", 0.0)),
            avg_stops_per_trip=float(row.get("avg_stops_per_trip", 0.0)),
            stop_count=int(row.get("stop_count", 0)),
            estimated_distance_km=float(row.get("estimated_distance_km", 0.0)),
            avg_speed_kmh=float(row.get("avg_speed_kmh", 0.0)),
            avg_headway_min=float(row.get("avg_headway_min", 0.0)),
            headway_std_min=float(row.get("headway_std_min", 0.0)),
            headway_cv=float(row.get("headway_cv", 0.0)),
            peak_morning_trips=int(row.get("peak_morning_trips", 0)),
            peak_evening_trips=int(row.get("peak_evening_trips", 0)),
            off_peak_trips=int(row.get("off_peak_trips", 0)),
            night_trips=int(row.get("night_trips", 0)),
            peak_ratio=float(row.get("peak_ratio", 0.0)),
            direction_balance_ratio=float(row.get("direction_balance_ratio", 0.0)),
            hub_stops_count=int(row.get("hub_stops_count", 0)),
            high_frequency_flag=int(row.get("high_frequency_flag", 0)),
        )

    @staticmethod
    def get_route_stops(route_id: str) -> Optional[RouteStopsResponse]:
        """Fetch scheduled stop sequences for a route split by direction."""
        df = db.get_table("route_stops")
        matches = df[df["route_id"].astype(str) == str(route_id).strip()]
        if matches.empty:
            return None

        short_name = str(matches.iloc[0].get("route_short_name", route_id))

        dir0 = matches[matches["direction_id"] == 0].sort_values(by="stop_sequence")
        dir1 = matches[matches["direction_id"] == 1].sort_values(by="stop_sequence")

        def build_items(sub_df: pd.DataFrame) -> List[RouteStopItem]:
            return [
                RouteStopItem(
                    stop_id=str(r["stop_id"]),
                    stop_sequence=int(r["stop_sequence"]),
                    direction_id=int(r["direction_id"]),
                    stop_name=str(r.get("stop_name", "")),
                    stop_lat=float(r.get("stop_lat", 0.0)),
                    stop_lon=float(r.get("stop_lon", 0.0)),
                )
                for _, r in sub_df.iterrows()
            ]

        dir0_items = build_items(dir0)
        dir1_items = build_items(dir1)
        total_unique = matches["stop_id"].nunique()
        all_stops = dir0_items if dir0_items else dir1_items

        return RouteStopsResponse(
            route_id=route_id,
            route_short_name=short_name,
            direction_0_stops=dir0_items,
            direction_1_stops=dir1_items,
            total_stops_served=total_unique,
            items=all_stops,
        )

    @staticmethod
    def get_route_trips(route_id: str, limit: int = 100) -> Optional[RouteTripsResponse]:
        """Fetch scheduled trips for a route."""
        trips_df = db.get_table("trips")
        stop_times_df = db.get_table("stop_times")
        routes_df = db.get_table("routes")

        route_trips = trips_df[trips_df["route_id"].astype(str) == str(route_id).strip()]
        if route_trips.empty:
            return None

        short_name = str(route_id)
        r_match = routes_df[routes_df["route_id"].astype(str) == str(route_id).strip()]
        if not r_match.empty:
            short_name = str(r_match.iloc[0].get("route_short_name", route_id))

        trip_ids = set(route_trips["trip_id"])
        sub_st = stop_times_df[stop_times_df["trip_id"].isin(trip_ids)]

        st_agg = sub_st.groupby("trip_id").agg(
            first_departure=("normalized_departure_time", "first"),
            last_arrival=("normalized_arrival_time", "last"),
            first_sec=("departure_seconds", "min"),
            last_sec=("arrival_seconds", "max"),
            stop_count=("stop_id", "count"),
        ).reset_index()

        merged = route_trips.merge(st_agg, on="trip_id").sort_values(by="first_sec")

        items = []
        for _, r in merged.head(limit).iterrows():
            dur = max(1.0, (r["last_sec"] - r["first_sec"]) / 60.0)
            items.append(
                RouteTripItem(
                    trip_id=str(r["trip_id"]),
                    service_id=str(r.get("service_id", "Regular")),
                    direction_id=int(r.get("direction_id", 0)),
                    first_departure_time=str(r.get("first_departure", "N/A")),
                    last_arrival_time=str(r.get("last_arrival", "N/A")),
                    duration_min=round(dur, 1),
                    stops_count=int(r.get("stop_count", 0)),
                )
            )

        return RouteTripsResponse(
            route_id=route_id,
            route_short_name=short_name,
            total_trips=len(route_trips),
            trips=items,
        )

    @staticmethod
    def get_route_schedule(route_id: str) -> Optional[RouteScheduleResponse]:
        """Fetch scheduled timetable distribution and span breakdown for a route."""
        trips_resp = RouteService.get_route_trips(route_id, limit=5000)
        if not trips_resp:
            return None

        feat_resp = RouteService.get_route_by_id(route_id)
        span_hours = feat_resp.service_span_hours if feat_resp else 0.0
        first_dep = feat_resp.first_departure_time if feat_resp else "N/A"
        last_dep = feat_resp.last_departure_time if feat_resp else "N/A"

        # Group trips by hour
        hour_counts: Dict[int, Dict[str, int]] = {h: {"total": 0, "dir0": 0, "dir1": 0} for h in range(24)}
        for t in trips_resp.trips:
            try:
                hour = int(t.first_departure_time.split(":")[0]) % 24
                hour_counts[hour]["total"] += 1
                if t.direction_id == 0:
                    hour_counts[hour]["dir0"] += 1
                else:
                    hour_counts[hour]["dir1"] += 1
            except Exception:
                continue

        hourly_dist = [
            HourlyDepartureDistribution(
                hour_label=f"{h:02d}:00 - {(h+1)%24:02d}:00",
                hour_int=h,
                scheduled_departures=hour_counts[h]["total"],
                direction_0_count=hour_counts[h]["dir0"],
                direction_1_count=hour_counts[h]["dir1"],
            )
            for h in range(24)
        ]

        active_services = list(set(t.service_id for t in trips_resp.trips))
        earliest = sorted(trips_resp.trips, key=lambda x: x.first_departure_time)[:5]
        latest = sorted(trips_resp.trips, key=lambda x: x.first_departure_time, reverse=True)[:5]

        entries = [
            ScheduleEntry(
                trip_id=t.trip_id,
                direction_id=t.direction_id,
                service_id=t.service_id,
                departure_time=t.first_departure_time,
                stop_id="",
                stop_name=f"Trip departure at {t.first_departure_time}",
            )
            for t in trips_resp.trips
        ]

        return RouteScheduleResponse(
            route_id=route_id,
            route_short_name=trips_resp.route_short_name,
            service_span_hours=span_hours,
            first_departure_time=first_dep,
            last_departure_time=last_dep,
            active_service_ids=active_services,
            hourly_distribution=hourly_dist,
            earliest_trips=earliest,
            latest_trips=latest,
            entries=entries,
        )

