"""GTFS file inventory and minimum required columns."""

from __future__ import annotations

REQUIRED_FILES: dict[str, tuple[str, ...]] = {
    "agency.txt": ("agency_name", "agency_url", "agency_timezone"),
    "stops.txt": ("stop_id", "stop_name", "stop_lat", "stop_lon"),
    "routes.txt": ("route_id", "route_type"),
    "trips.txt": ("route_id", "service_id", "trip_id"),
    "stop_times.txt": ("trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"),
}

OPTIONAL_FILES: dict[str, tuple[str, ...]] = {
    "calendar.txt": ("service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "start_date", "end_date"),
    "calendar_dates.txt": ("service_id", "date", "exception_type"),
    "feed_info.txt": ("feed_publisher_name", "feed_publisher_url", "feed_lang"),
    "shapes.txt": ("shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"),
    "frequencies.txt": ("trip_id", "start_time", "end_time", "headway_secs"),
    "transfers.txt": ("from_stop_id", "to_stop_id", "transfer_type"),
}

SUPPORTED_FILES = {**REQUIRED_FILES, **OPTIONAL_FILES}
PRIMARY_KEYS = {
    "agency.txt": ("agency_id",),
    "stops.txt": ("stop_id",),
    "routes.txt": ("route_id",),
    "trips.txt": ("trip_id",),
    "calendar.txt": ("service_id",),
    "calendar_dates.txt": ("service_id", "date"),
}

