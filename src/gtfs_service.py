"""Build route/date scheduled-service indicators from versioned CTA GTFS ZIPs."""

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import defaultdict
from contextlib import nullcontext
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from .data_loader import load_bus_ridership


WEEKDAY_COLUMNS = (
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _member(archive: zipfile.ZipFile | Path, filename: str) -> str | Path:
    if isinstance(archive, Path):
        matches = [name for name in archive.rglob(filename) if name.name == filename]
    else:
        matches = [name for name in archive.namelist() if Path(name).name == filename]
    if len(matches) != 1:
        label = archive.filename if isinstance(archive, zipfile.ZipFile) else archive
        raise ValueError(f"Expected exactly one {filename} in {label}; found {len(matches)}")
    return matches[0]


def _rows(archive: zipfile.ZipFile | Path, filename: str):
    member = _member(archive, filename)
    binary_file = archive.open(member) if isinstance(archive, zipfile.ZipFile) else member.open("rb")
    with binary_file as binary:
        text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
        yield from csv.DictReader(text)


def _optional_rows(archive: zipfile.ZipFile | Path, filename: str):
    if isinstance(archive, Path):
        present = any(archive.rglob(filename))
    else:
        present = any(Path(name).name == filename for name in archive.namelist())
    if not present:
        return
    yield from _rows(archive, filename)


def _directory_fingerprint(path: Path) -> str:
    """Fingerprint important extracted table bytes, independent of folder order."""
    digest = hashlib.sha256()
    names = ("routes.txt", "trips.txt", "stop_times.txt", "calendar.txt", "calendar_dates.txt", "frequencies.txt")
    for filename in names:
        matches = sorted(path.rglob(filename))
        if len(matches) > 1:
            raise ValueError(f"Expected at most one extracted {filename} in {path}; found {len(matches)}")
        if matches:
            digest.update(filename.encode("utf-8"))
            with matches[0].open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()


def _gtfs_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y%m%d").date()


def _gtfs_time(value: str | None) -> int | None:
    """Parse GTFS HH:MM:SS, allowing service times beyond 24:00:00."""
    if not value:
        return None
    try:
        hours, minutes, seconds = (int(part) for part in value.split(":"))
    except (TypeError, ValueError):
        return None
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        return None
    return hours * 3600 + minutes * 60 + seconds


def _read_manifest(path: Path, base: Path) -> list[dict]:
    manifest = pd.read_csv(path, dtype="string").fillna("")
    required = {"archive_id", "retrieved_date", "zip_path", "expected_sha256"}
    if not required.issubset(manifest.columns):
        raise ValueError(f"Archive manifest must contain {sorted(required)}")
    rows = []
    for item in manifest.to_dict("records"):
        retrieved = pd.Timestamp(item["retrieved_date"]).date()
        zip_path = Path(item["zip_path"])
        if not zip_path.is_absolute():
            zip_path = base / zip_path
        rows.append({**item, "retrieved_date_obj": retrieved, "zip_path_obj": zip_path})
    rows.sort(key=lambda row: row["retrieved_date_obj"])
    if len({row["retrieved_date_obj"] for row in rows}) != len(rows):
        raise ValueError("Archive retrieval dates must be unique")
    if not rows or any(not row["zip_path_obj"].exists() for row in rows):
        missing = [str(row["zip_path_obj"]) for row in rows if not row["zip_path_obj"].exists()]
        raise FileNotFoundError(f"Missing one or more GTFS archives: {missing}")
    return rows


def _load_snapshot(entry: dict) -> dict:
    """Read a ZIP and aggregate route/service trip counts and trip durations."""
    path = entry["zip_path_obj"]
    is_archive = path.is_file()
    archive_hash = _sha256(path) if is_archive else None
    expected_hash = str(entry["expected_sha256"]).strip().lower()
    if is_archive and expected_hash and archive_hash != expected_hash:
        raise ValueError(
            f"SHA-256 mismatch for {entry['archive_id']}: expected {expected_hash}, got {archive_hash}"
        )

    source_context = zipfile.ZipFile(path) if is_archive else nullcontext(path)
    with source_context as archive:
        routes = {}
        short_name_to_ids = defaultdict(set)
        for row in _rows(archive, "routes.txt"):
            if row.get("route_type", "").strip() != "3":
                continue
            route_id = row.get("route_id", "").strip()
            short_name = row.get("route_short_name", "").strip()
            if not route_id or not short_name:
                continue
            routes[route_id] = short_name
            short_name_to_ids[short_name].add(route_id)
        ambiguous = {name: sorted(ids) for name, ids in short_name_to_ids.items() if len(ids) > 1}
        if ambiguous:
            raise ValueError(f"Ambiguous bus route_short_name crosswalk in {entry['archive_id']}: {ambiguous}")

        trips_by_service = defaultdict(lambda: defaultdict(list))
        trip_ids = set()
        for row in _rows(archive, "trips.txt"):
            route_id = row.get("route_id", "").strip()
            if route_id not in routes:
                continue
            trip_id = row.get("trip_id", "").strip()
            service_id = row.get("service_id", "").strip()
            if not trip_id or not service_id or trip_id in trip_ids:
                raise ValueError(f"Missing or duplicate bus trip_id/service_id in {entry['archive_id']}")
            trip_ids.add(trip_id)
            trips_by_service[service_id][routes[route_id]].append(trip_id)

        # Frequency-based templates change the number of trips and must not be
        # mistaken for one scheduled trip per template.
        frequency_rows = list(_optional_rows(archive, "frequencies.txt"))
        if frequency_rows:
            raise NotImplementedError(
                f"Non-empty frequencies.txt in {entry['archive_id']}; expand frequency templates before counting trips"
            )

        calendars = {}
        for row in _optional_rows(archive, "calendar.txt"):
            service_id = row.get("service_id", "").strip()
            flag_values = tuple(row.get(column, "0").strip() for column in WEEKDAY_COLUMNS)
            if any(value not in {"0", "1"} for value in flag_values):
                raise ValueError(f"Invalid weekly calendar flags in {entry['archive_id']} for {service_id}")
            if service_id in calendars:
                raise ValueError(f"Duplicate calendar service_id in {entry['archive_id']}: {service_id}")
            flags = tuple(value == "1" for value in flag_values)
            calendars[service_id] = (
                _gtfs_date(row["start_date"]), _gtfs_date(row["end_date"]), flags
            )
        exceptions = defaultdict(dict)
        for row in _optional_rows(archive, "calendar_dates.txt"):
            service_id = row.get("service_id", "").strip()
            exception_date = _gtfs_date(row["date"])
            exception_type = int(row["exception_type"])
            if exception_type not in (1, 2):
                raise ValueError(f"Invalid calendar exception type in {entry['archive_id']}")
            if service_id in exceptions[exception_date]:
                raise ValueError(f"Duplicate service/date exception in {entry['archive_id']}")
            exceptions[exception_date][service_id] = exception_type
        known_services = set(calendars) | {
            service for date_exceptions in exceptions.values() for service in date_exceptions
        }
        if not known_services:
            raise ValueError(f"No calendar or calendar_dates service definitions in {entry['archive_id']}")
        undefined = set(trips_by_service) - known_services
        if undefined:
            raise ValueError(f"Bus trips reference undefined service IDs in {entry['archive_id']}: {sorted(undefined)[:20]}")

        # Retain only endpoint information per bus trip while streaming all stop
        # events; this bounds memory on the multi-million-row stop_times table.
        endpoints = {}
        duplicate_endpoint_sequences = set()
        for row in _rows(archive, "stop_times.txt"):
            trip_id = row.get("trip_id", "").strip()
            if trip_id not in trip_ids:
                continue
            try:
                sequence = int(row.get("stop_sequence", ""))
            except ValueError:
                continue
            if sequence < 0:
                continue
            current = endpoints.get(trip_id)
            arrival = row.get("arrival_time", "").strip()
            departure = row.get("departure_time", "").strip()
            if current is None:
                endpoints[trip_id] = [sequence, departure, 1, sequence, arrival, 1]
                continue
            if sequence < current[0]:
                current[0], current[1], current[2] = sequence, departure, 1
            elif sequence == current[0]:
                current[2] += 1
                duplicate_endpoint_sequences.add(trip_id)
            if sequence > current[3]:
                current[3], current[4], current[5] = sequence, arrival, 1
            elif sequence == current[3]:
                current[5] += 1
                duplicate_endpoint_sequences.add(trip_id)

        durations = {}
        for trip_id in trip_ids:
            endpoint = endpoints.get(trip_id)
            if endpoint is None or trip_id in duplicate_endpoint_sequences:
                durations[trip_id] = None
                continue
            first_departure = _gtfs_time(endpoint[1])
            last_arrival = _gtfs_time(endpoint[4])
            seconds = last_arrival - first_departure if first_departure is not None and last_arrival is not None else -1
            durations[trip_id] = seconds if seconds > 0 else None

    by_service = {}
    for service_id, routes_for_service in trips_by_service.items():
        by_service[service_id] = {}
        for route, ids in routes_for_service.items():
            valid = [durations[trip_id] for trip_id in ids if durations[trip_id] is not None]
            by_service[service_id][route] = {
                "scheduled_trips": len(ids),
                "valid_duration_trips": len(valid),
                "duration_seconds": sum(valid),
            }
    return {
        "by_service": by_service,
        "calendars": calendars,
        "exceptions": exceptions,
        "archive_hash": archive_hash,
        "source_hash": archive_hash or _directory_fingerprint(path),
        "archive_hash_verified": bool(is_archive and (not expected_hash or archive_hash == expected_hash)),
        "source_kind": "zip" if is_archive else "extracted_directory",
        "route_count": len(routes),
        "bus_trip_count": len(trip_ids),
        "duration_complete_trip_count": sum(value is not None for value in durations.values()),
    }


def _active_services(snapshot: dict, day: date) -> set[str]:
    active = set()
    for service_id, (start, end, weekdays) in snapshot["calendars"].items():
        if start <= day <= end and weekdays[day.weekday()]:
            active.add(service_id)
    for service_id, exception_type in snapshot["exceptions"].get(day, {}).items():
        if exception_type == 1:
            active.add(service_id)
        else:
            active.discard(service_id)
    return active


def build_service_table(
    ridership_path: str | Path,
    manifest_path: str | Path,
    output_path: str | Path,
    report_path: str | Path,
) -> dict:
    """Select one globally dated feed per service date and exact-join boardings."""
    root = Path.cwd()
    ridership_path, manifest_path = Path(ridership_path), Path(manifest_path)
    manifest = _read_manifest(manifest_path, root)
    snapshots = []
    for entry in manifest:
        snapshots.append({**entry, "snapshot": _load_snapshot(entry)})

    demand = load_bus_ridership(ridership_path)
    start = max(demand["date"].min().date(), manifest[0]["retrieved_date_obj"])
    end = demand["date"].max().date()
    if end < start:
        raise ValueError("Ridership observations do not overlap the archive retrieval period")
    retrieval_dates = [entry["retrieved_date_obj"] for entry in snapshots]
    schedule_rows, no_snapshot_dates, no_active_service_dates = [], [], []
    for service_day in (start + timedelta(days=offset) for offset in range((end - start).days + 1)):
        eligible = [i for i, retrieved in enumerate(retrieval_dates) if retrieved <= service_day]
        if not eligible:
            no_snapshot_dates.append(service_day.isoformat())
            continue
        index = eligible[-1]
        entry = snapshots[index]
        snapshot = entry["snapshot"]
        active = _active_services(snapshot, service_day)
        if not active:
            no_active_service_dates.append(service_day.isoformat())
            continue
        aggregate = defaultdict(lambda: {"scheduled_trips": 0, "valid_duration_trips": 0, "duration_seconds": 0})
        for service_id in active:
            for route, counts in snapshot["by_service"].get(service_id, {}).items():
                for key in aggregate[route]:
                    aggregate[route][key] += counts[key]
        for route, values in aggregate.items():
            complete = values["scheduled_trips"] == values["valid_duration_trips"]
            schedule_rows.append({
                "route": route,
                "date": pd.Timestamp(service_day),
                "scheduled_trips": values["scheduled_trips"],
                "scheduled_service_hours": values["duration_seconds"] / 3600 if complete else None,
                "duration_complete": complete,
                "source_snapshot": entry["archive_id"],
                "archive_available_from": entry["retrieved_date_obj"],
            })

    schedules = pd.DataFrame(schedule_rows)
    if schedules.empty:
        raise ValueError("No active route/date schedule records were produced")
    schedules["route"] = schedules["route"].astype("string")
    schedules["date"] = pd.to_datetime(schedules["date"]).dt.normalize()
    if schedules.duplicated(["route", "date"]).any():
        raise ValueError("Selected schedule table contains duplicate route/date keys")
    merged = demand.merge(schedules, on=["route", "date"], how="outer", validate="one_to_one", indicator=True)
    merged["match_status"] = merged.pop("_merge").map({
        "both": "matched", "left_only": "ridership_without_schedule", "right_only": "schedule_without_ridership"
    })
    output_path, report_path = Path(output_path), Path(report_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    report = {
        "ridership_sha256": _sha256(Path(ridership_path)),
        "date_range_processed": [start.isoformat(), end.isoformat()],
        "archive_versions": [
            {"archive_id": entry["archive_id"], "retrieved_date": entry["retrieved_date_obj"].isoformat(),
             "archive_sha256": entry["snapshot"]["archive_hash"],
             "archive_sha256_verified": entry["snapshot"]["archive_hash_verified"],
             "source_kind": entry["snapshot"]["source_kind"],
             "source_fingerprint": entry["snapshot"]["source_hash"],
             "bus_routes": entry["snapshot"]["route_count"],
             "bus_trip_templates": entry["snapshot"]["bus_trip_count"]}
            for entry in snapshots
        ],
        "schedule_route_date_rows": int(len(schedules)),
        "matched_route_date_rows": int((merged["match_status"] == "matched").sum()),
        "ridership_without_schedule_rows": int((merged["match_status"] == "ridership_without_schedule").sum()),
        "schedule_without_ridership_rows": int((merged["match_status"] == "schedule_without_ridership").sum()),
        "dates_without_snapshot": no_snapshot_dates,
        "dates_without_active_service": no_active_service_dates,
        "service_hours_policy": "Null unless every counted trip for route/date has valid first-departure and last-arrival duration",
        "archive_selection_policy": "Globally select latest retrieval date on or before each service date; never route-level fallback",
        "output_csv": str(output_path),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ridership", default="data/raw/cta_bus_ridership.csv")
    parser.add_argument("--manifest", default="data/raw/gtfs_archive_manifest.csv")
    parser.add_argument("--output", default="data/processed/cta_route_date_demand_service.csv")
    parser.add_argument("--report", default="outputs/reports/gtfs_service_import.json")
    args = parser.parse_args()
    print(json.dumps(build_service_table(args.ridership, args.manifest, args.output, args.report), indent=2))


if __name__ == "__main__":
    main()
