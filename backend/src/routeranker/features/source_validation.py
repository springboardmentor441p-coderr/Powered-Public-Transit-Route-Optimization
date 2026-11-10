"""Streaming source-feed snapshot for feature validation.

This module reads only the supplied GTFS ZIP and keeps compact identifier sets
and per-trip endpoints. It never extracts or modifies the source archive.
"""

from __future__ import annotations

import csv
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from routeranker.ingestion.time import parse_gtfs_time

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


@dataclass
class SourceSnapshot:
    """Compact counts and relationships read directly from source GTFS."""

    row_counts: dict[str, int]
    routes: dict[str, dict[str, str]]
    stops: dict[str, dict[str, str]]
    trip_meta: dict[str, tuple[str, str, str]]
    route_trip_counts: Counter[str]
    route_stops: dict[str, set[str]]
    stop_routes: dict[str, set[str]]
    stop_trips: dict[str, set[str]]
    trip_endpoints: dict[str, tuple[int, int, int, int]]
    service_weekdays: dict[str, set[str]]
    trip_stop_time_rows: int


def _read_rows(archive: zipfile.ZipFile, members: dict[str, str], filename: str):
    with archive.open(members[filename]) as binary:
        import io

        text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
        yield from csv.DictReader(text)


def load_source_snapshot(archive_path: str) -> SourceSnapshot:
    """Stream core source tables and build reference metrics for QA checks."""
    with zipfile.ZipFile(archive_path) as archive:
        members = {
            PurePosixPath(name).name: name
            for name in archive.namelist()
            if not name.endswith("/") and PurePosixPath(name).suffix.lower() == ".txt"
        }
        required = {"routes.txt", "stops.txt", "trips.txt", "stop_times.txt", "calendar.txt"}
        absent = sorted(required - set(members))
        if absent:
            raise ValueError(f"Source GTFS archive lacks required Phase 3 files: {absent}")

        routes: dict[str, dict[str, str]] = {}
        for row in _read_rows(archive, members, "routes.txt"):
            route_id = row["route_id"]
            if route_id in routes:
                raise ValueError(f"Duplicate route_id in source GTFS: {route_id!r}")
            routes[route_id] = {
                key: row.get(key, "") or ""
                for key in ("route_short_name", "route_long_name", "route_type")
            }

        stops: dict[str, dict[str, str]] = {}
        for row in _read_rows(archive, members, "stops.txt"):
            stop_id = row["stop_id"]
            if stop_id in stops:
                raise ValueError(f"Duplicate stop_id in source GTFS: {stop_id!r}")
            stops[stop_id] = {"stop_name": row.get("stop_name", "") or ""}

        trip_meta: dict[str, tuple[str, str, str]] = {}
        route_trip_counts: Counter[str] = Counter()
        for row in _read_rows(archive, members, "trips.txt"):
            trip_id = row["trip_id"]
            if trip_id in trip_meta:
                raise ValueError(f"Duplicate trip_id in source GTFS: {trip_id!r}")
            route_id = row["route_id"]
            if route_id not in routes:
                raise ValueError(f"Trip references unknown route_id: {route_id!r}")
            trip_meta[trip_id] = (route_id, row["service_id"], row.get("direction_id", ""))
            route_trip_counts[route_id] += 1

        service_weekdays: dict[str, set[str]] = {}
        for row in _read_rows(archive, members, "calendar.txt"):
            service_id = row["service_id"]
            if service_id in service_weekdays:
                raise ValueError(f"Duplicate service_id in source calendar.txt: {service_id!r}")
            flags = {day for day in WEEKDAYS if row.get(day) == "1"}
            if any(row.get(day) not in {"0", "1"} for day in WEEKDAYS):
                raise ValueError(f"Invalid weekday flag for service_id {service_id!r}")
            service_weekdays[service_id] = flags

        route_stops: dict[str, set[str]] = defaultdict(set)
        stop_routes: dict[str, set[str]] = defaultdict(set)
        stop_trips: dict[str, set[str]] = defaultdict(set)
        endpoints: dict[str, tuple[int, int, int, int]] = {}
        row_count = 0
        for row_count, row in enumerate(_read_rows(archive, members, "stop_times.txt"), start=1):
            trip_id = row["trip_id"]
            if trip_id not in trip_meta:
                raise ValueError(f"stop_times references unknown trip_id: {trip_id!r}")
            stop_id = row["stop_id"]
            if stop_id not in stops:
                raise ValueError(f"stop_times references unknown stop_id: {stop_id!r}")
            route_id = trip_meta[trip_id][0]
            route_stops[route_id].add(stop_id)
            stop_routes[stop_id].add(route_id)
            stop_trips[stop_id].add(trip_id)
            try:
                sequence = int(row["stop_sequence"])
                arrival = parse_gtfs_time(row["arrival_time"])
                departure = parse_gtfs_time(row["departure_time"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid stop_time row {row_count}: {exc}") from exc
            old = endpoints.get(trip_id)
            if old is None:
                endpoints[trip_id] = (sequence, departure, sequence, arrival)
            else:
                min_seq, first_departure, max_seq, last_arrival = old
                endpoints[trip_id] = (
                    (sequence, departure) if sequence < min_seq else (min_seq, first_departure)
                ) + (
                    (sequence, arrival) if sequence > max_seq else (max_seq, last_arrival)
                )

        missing_trip_times = set(trip_meta) - set(endpoints)
        if missing_trip_times:
            raise ValueError(f"{len(missing_trip_times)} source trips have no stop_times records")
        missing_calendar_services = {meta[1] for meta in trip_meta.values()} - set(service_weekdays)
        if missing_calendar_services:
            raise ValueError(f"{len(missing_calendar_services)} trip service IDs are absent from calendar.txt")

        counts = {
            "routes.txt": len(routes),
            "stops.txt": len(stops),
            "trips.txt": len(trip_meta),
            "stop_times.txt": row_count,
            "calendar.txt": len(service_weekdays),
        }
        return SourceSnapshot(
            row_counts=counts,
            routes=routes,
            stops=stops,
            trip_meta=trip_meta,
            route_trip_counts=route_trip_counts,
            route_stops=dict(route_stops),
            stop_routes=dict(stop_routes),
            stop_trips=dict(stop_trips),
            trip_endpoints=endpoints,
            service_weekdays=service_weekdays,
            trip_stop_time_rows=row_count,
        )


def derive_source_route_metrics(source: SourceSnapshot) -> dict[str, dict[str, Any]]:
    """Derive reference route features directly from source records."""
    starts_by_group: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    peak_week = Counter()
    off_peak_week = Counter()
    route_starts: dict[str, list[int]] = defaultdict(list)
    route_terminal_arrivals: dict[str, list[int]] = defaultdict(list)
    for trip_id, (route_id, service_id, direction_id) in source.trip_meta.items():
        first_departure = source.trip_endpoints[trip_id][1]
        last_arrival = source.trip_endpoints[trip_id][3]
        starts_by_group[(route_id, service_id, direction_id)].append(first_departure)
        route_starts[route_id].append(first_departure)
        route_terminal_arrivals[route_id].append(last_arrival)
        hour = first_departure // 3600
        is_peak = 7 <= hour < 10 or 16 <= hour < 19
        for weekday in source.service_weekdays.get(service_id, set()):
            (peak_week if is_peak else off_peak_week)[route_id] += 1

    headway_sum = Counter()
    headway_count = Counter()
    for (route_id, _service, _direction), starts in starts_by_group.items():
        starts.sort()
        gaps = [later - earlier for earlier, later in zip(starts, starts[1:])]
        headway_sum[route_id] += sum(gaps)
        headway_count[route_id] += len(gaps)

    features: dict[str, dict[str, Any]] = {}
    for route_id in source.routes:
        stop_ids = source.route_stops.get(route_id, set())
        shared_stops = sum(len(source.stop_routes.get(stop_id, set())) > 1 for stop_id in stop_ids)
        starts = route_starts.get(route_id, [])
        arrivals = route_terminal_arrivals.get(route_id, [])
        count = int(source.route_trip_counts.get(route_id, 0))
        intervals = int(headway_count.get(route_id, 0))
        first_departure = min(starts) if starts else None
        last_departure = max(starts) if starts else None
        last_arrival = max(arrivals) if arrivals else None
        features[route_id] = {
            "total_scheduled_trip_records": count,
            "unique_stop_count": len(stop_ids),
            "average_first_stop_headway_seconds": headway_sum[route_id] / intervals if intervals else None,
            "headway_interval_count": intervals,
            "peak_scheduled_departures_per_template_week": int(peak_week[route_id]),
            "off_peak_scheduled_departures_per_template_week": int(off_peak_week[route_id]),
            "first_scheduled_departure_seconds": first_departure,
            "last_scheduled_departure_seconds": last_departure,
            "scheduled_service_span_seconds": last_arrival - first_departure if first_departure is not None and last_arrival is not None else None,
            "_last_terminal_arrival_seconds": last_arrival,
            "shared_stop_count": shared_stops,
            "shared_stop_ratio": shared_stops / len(stop_ids) if stop_ids else None,
        }
    return features

