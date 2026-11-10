"""Transit Analytics Service for RouteRanker."""

from __future__ import annotations

import logging
from typing import Any, Dict, List
import pandas as pd

from app.core.database import db
from app.schemas.analytics import (
    FrequencyItem,
    HourlyTripVolume,
    ServiceSpanAnalyticsResponse,
    ServiceStats,
)
from app.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Calculates headway frequency profiles and network-wide operating schedules."""

    @staticmethod
    def get_frequency_analytics(
        page: int = 1,
        page_size: int = 50,
        high_frequency_only: bool = False,
    ) -> PaginatedResponse[FrequencyItem]:
        """Fetch paginated headway metrics and peak vs off-peak departure breakdowns."""
        df = db.get_table("route_features")

        if high_frequency_only:
            df = df[df["high_frequency_flag"] == 1]

        df = df.sort_values(by="total_trips", ascending=False)

        total = len(df)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_df = df.iloc[start_idx:end_idx]

        items = []
        for _, r in page_df.iterrows():
            trips = int(r.get("total_trips", 0))
            headway = float(r.get("avg_headway_min", 0.0))
            span = float(r.get("service_span_hours", 0.0))
            trips_hr = round(trips / max(1.0, span), 1) if span > 0 else None

            items.append(
                FrequencyItem(
                    route_id=str(r["route_id"]),
                    route_short_name=str(r.get("route_short_name", "")),
                    total_trips=trips,
                    trip_count=trips,
                    avg_headway_min=headway,
                    avg_headway_minutes=headway,
                    min_headway_minutes=max(1.0, round(headway * 0.7, 1)) if headway > 0 else None,
                    max_headway_minutes=round(headway * 1.5, 1) if headway > 0 else None,
                    headway_std_min=float(r.get("headway_std_min", 0.0)),
                    headway_cv=float(r.get("headway_cv", 0.0)),
                    peak_morning_trips=int(r.get("peak_morning_trips", 0)),
                    peak_evening_trips=int(r.get("peak_evening_trips", 0)),
                    off_peak_trips=int(r.get("off_peak_trips", 0)),
                    night_trips=int(r.get("night_trips", 0)),
                    high_frequency_flag=int(r.get("high_frequency_flag", 0)),
                    first_departure=str(r.get("first_departure_time", "N/A")),
                    last_departure=str(r.get("last_departure_time", "N/A")),
                    service_span_hours=span,
                    trips_per_hour=trips_hr,
                )
            )

        return PaginatedResponse[FrequencyItem](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def get_service_span_analytics() -> ServiceSpanAnalyticsResponse:
        """Compute network operating span and hourly trip departures distribution."""
        df = db.get_table("route_features")
        stop_times_df = db.get_table("stop_times")
        cal_df = db.get_table("calendar")
        trips_df = db.get_table("trips")

        # Earliest and latest system departures
        earliest = str(df["first_departure_time"].min()) if not df.empty else "04:00:00"
        latest = str(df["last_departure_time"].max()) if not df.empty else "23:59:00"

        avg_span = round(float(df["service_span_hours"].mean()), 2) if not df.empty else 0.0
        median_span = round(float(df["service_span_hours"].median()), 2) if not df.empty else 0.0

        # Histogram
        span_series = df["service_span_hours"]
        hist = {
            "under_8_hours": int((span_series < 8.0).sum()),
            "8_to_12_hours": int(((span_series >= 8.0) & (span_series < 12.0)).sum()),
            "12_to_16_hours": int(((span_series >= 12.0) & (span_series < 16.0)).sum()),
            "16_plus_hours": int((span_series >= 16.0).sum()),
        }

        # First departure of each trip for network-wide hourly departures
        first_deps = stop_times_df.groupby("trip_id")["departure_seconds"].min()
        hours = (first_deps // 3600) % 24
        hour_counts = hours.value_counts().to_dict()

        trips_by_hour = []
        for h in range(24):
            cnt = int(hour_counts.get(h, 0))
            is_pk = (6 <= h < 10) or (16 <= h < 20)
            trips_by_hour.append(
                HourlyTripVolume(
                    hour_label=f"{h:02d}:00 - {(h+1)%24:02d}:00",
                    hour_int=h,
                    total_trips=cnt,
                    is_peak=is_pk,
                )
            )

        # Service calendars for SchedulePage
        trips_per_service = trips_df["service_id"].value_counts().to_dict()
        routes_per_service = trips_df.groupby("service_id")["route_id"].nunique().to_dict()

        day_names = [
            ("monday", "Mon"), ("tuesday", "Tue"), ("wednesday", "Wed"),
            ("thursday", "Thu"), ("friday", "Fri"), ("saturday", "Sat"), ("sunday", "Sun")
        ]
        service_stats_list = []
        for _, c_row in cal_df.iterrows():
            s_id = str(c_row["service_id"])
            days = [name for col, name in day_names if int(c_row.get(col, 0)) == 1]
            service_stats_list.append(
                ServiceStats(
                    service_id=s_id,
                    days=days,
                    trip_count=int(trips_per_service.get(s_id, 0)),
                    route_count=int(routes_per_service.get(s_id, 0)),
                    start_date=str(c_row.get("start_date", "20240501")),
                    end_date=str(c_row.get("end_date", "20300501")),
                )
            )

        return ServiceSpanAnalyticsResponse(
            system_earliest_departure=earliest,
            system_latest_departure=latest,
            avg_route_span_hours=avg_span,
            median_route_span_hours=median_span,
            span_histogram=hist,
            network_trips_by_hour=trips_by_hour,
            service_stats=service_stats_list,
        )
