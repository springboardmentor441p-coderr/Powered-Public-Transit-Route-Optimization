"""GTFS ZIP validation and deterministic Parquet preprocessing."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import polars as pl

from .schemas import OPTIONAL_FILES, PRIMARY_KEYS, REQUIRED_FILES, SUPPORTED_FILES
from .time import parse_gtfs_time

_DATE = re.compile(r"^\d{8}$")
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _issue(code: str, severity: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, **details}


def _read_member(archive: zipfile.ZipFile, name: str) -> pl.DataFrame:
    """Read one CSV member while preserving source values as strings."""
    with archive.open(name) as stream:
        return pl.read_csv(BytesIO(stream.read()), infer_schema=False, try_parse_dates=False)


def _blank_counts(frame: pl.DataFrame) -> dict[str, int]:
    if frame.is_empty():
        return {column: 0 for column in frame.columns}
    return {
        column: frame.select(
            (pl.col(column).is_null() | (pl.col(column).str.strip_chars() == "")).sum()
        ).item()
        for column in frame.columns
    }


def _time_seconds(frame: pl.DataFrame, column: str) -> pl.Expr:
    """Build a vectorized seconds-since-service-day expression."""
    return (
        pl.col(column)
        .str.extract(r"^(\d{1,3}):(\d{2}):(\d{2})$", group_index=1).cast(pl.Int64, strict=False) * 3600
        + pl.col(column)
        .str.extract(r"^(\d{1,3}):(\d{2}):(\d{2})$", group_index=2).cast(pl.Int64, strict=False) * 60
        + pl.col(column)
        .str.extract(r"^(\d{1,3}):(\d{2}):(\d{2})$", group_index=3).cast(pl.Int64, strict=False)
    ).cast(pl.Int64)


def _validate_times(frame: pl.DataFrame, column: str) -> tuple[int, int]:
    text = pl.col(column)
    hours = text.str.extract(r"^(\d{1,3}):(\d{2}):(\d{2})$", 1).cast(pl.Int64, strict=False)
    minutes = text.str.extract(r"^(\d{1,3}):(\d{2}):(\d{2})$", 2).cast(pl.Int64, strict=False)
    seconds = text.str.extract(r"^(\d{1,3}):(\d{2}):(\d{2})$", 3).cast(pl.Int64, strict=False)
    valid = (hours.is_not_null() & (minutes <= 59) & (seconds <= 59))
    counts = frame.select(
        (~valid).sum().alias("invalid"),
        (hours.filter(valid).max()).alias("max_hour"),
    ).row(0)
    return int(counts[0] or 0), int(counts[1] or 0)


def _date_is_valid(value: str) -> bool:
    if not _DATE.fullmatch(value or ""):
        return False
    try:
        datetime.strptime(value, "%Y%m%d")
        return True
    except ValueError:
        return False


def _cast_for_analysis(filename: str, frame: pl.DataFrame) -> pl.DataFrame:
    """Add typed columns while retaining original GTFS string columns."""
    casts: list[pl.Expr] = []
    integer_columns = {
        "route_type", "direction_id", "stop_sequence", "exception_type",
        "shape_pt_sequence", "headway_secs", "transfer_type",
    }
    float_columns = {"stop_lat", "stop_lon", "shape_pt_lat", "shape_pt_lon"}
    for column in frame.columns:
        if column in integer_columns:
            casts.append(pl.col(column).cast(pl.Int64, strict=False).alias(f"{column}_value"))
        elif column in float_columns:
            casts.append(pl.col(column).cast(pl.Float64, strict=False).alias(f"{column}_value"))
    if casts:
        frame = frame.with_columns(casts)
    time_columns = [column for column in ("arrival_time", "departure_time", "start_time", "end_time") if column in frame.columns]
    for column in time_columns:
        frame = frame.with_columns(_time_seconds(frame, column).alias(f"{column}_seconds"))
    return frame


def _relationship_report(tables: dict[str, pl.DataFrame]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    issues: list[dict[str, Any]] = []
    metrics: dict[str, int] = {}

    def values(filename: str, column: str) -> set[str]:
        table = tables.get(filename)
        if table is None or column not in table.columns:
            return set()
        return set(table.get_column(column).drop_nulls().to_list())

    checks = [
        ("routes.txt", "agency_id", "agency.txt", "agency_id", "route_agency"),
        ("trips.txt", "route_id", "routes.txt", "route_id", "trip_route"),
        ("stop_times.txt", "trip_id", "trips.txt", "trip_id", "stop_time_trip"),
        ("stop_times.txt", "stop_id", "stops.txt", "stop_id", "stop_time_stop"),
        ("frequencies.txt", "trip_id", "trips.txt", "trip_id", "frequency_trip"),
        ("transfers.txt", "from_stop_id", "stops.txt", "stop_id", "transfer_from_stop"),
        ("transfers.txt", "to_stop_id", "stops.txt", "stop_id", "transfer_to_stop"),
        ("trips.txt", "shape_id", "shapes.txt", "shape_id", "trip_shape"),
    ]
    for src_file, src_col, dst_file, dst_col, label in checks:
        if src_file not in tables or dst_file not in tables or src_col not in tables[src_file].columns or dst_col not in tables[dst_file].columns:
            continue
        refs, known = values(src_file, src_col), values(dst_file, dst_col)
        # For calendars the combined service definition comes from either calendar file.
        missing = refs - known
        metrics[f"{label}_unique_references"] = len(refs)
        metrics[f"{label}_unresolved_unique_references"] = len(missing)
        if missing:
            issues.append(_issue("unresolved_reference", "error", f"{label} contains unresolved identifiers.", relationship=label, count=len(missing), examples=sorted(missing)[:5]))

    if "routes.txt" in tables and "agency_id" in tables["routes.txt"].columns and "agency.txt" in tables:
        if values("routes.txt", "agency_id") and "agency_id" not in tables["agency.txt"].columns:
            issues.append(_issue("missing_agency_id", "error", "routes.txt uses agency_id, but agency.txt has no agency_id column."))

    if "trips.txt" in tables and ("calendar.txt" in tables or "calendar_dates.txt" in tables):
        trip_services = values("trips.txt", "service_id")
        known_services = values("calendar.txt", "service_id") | values("calendar_dates.txt", "service_id")
        missing_services = trip_services - known_services
        metrics["trip_services_without_calendar_rows"] = len(missing_services)
        if missing_services:
            issues.append(_issue("unresolved_service_calendar", "error", "Trips reference service IDs absent from both calendar definition files.", count=len(missing_services), examples=sorted(missing_services)[:5]))

    if "routes.txt" in tables and "trips.txt" in tables:
        metrics["unreferenced_route_records"] = len(values("routes.txt", "route_id") - values("trips.txt", "route_id"))
    if "stops.txt" in tables and "stop_times.txt" in tables:
        metrics["unreferenced_stop_records"] = len(values("stops.txt", "stop_id") - values("stop_times.txt", "stop_id"))
    if "trips.txt" in tables and ("calendar.txt" in tables or "calendar_dates.txt" in tables):
        calendar_ids = values("calendar.txt", "service_id") | values("calendar_dates.txt", "service_id")
        trip_ids = values("trips.txt", "service_id")
        metrics["unreferenced_calendar_services"] = len(calendar_ids - trip_ids)
        metrics["trip_services_without_calendar_rows"] = len(trip_ids - calendar_ids)
        if metrics["unreferenced_calendar_services"]:
            issues.append(_issue("unused_calendar_services", "warning", "Calendar service records are not referenced by trips.", count=metrics["unreferenced_calendar_services"]))
    for key in ("unreferenced_route_records", "unreferenced_stop_records"):
        if metrics.get(key, 0):
            issues.append(_issue(key, "warning", f"Dataset contains {metrics[key]} records affected by {key.replace('_', ' ')}."))
    return issues, metrics


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# GTFS data quality report", "",
        f"- Source archive: `{report['source_archive']}`",
        f"- Status: **{report['status']}**",
        f"- Processed tables: {len(report['files'])}", "",
        "## File inventory and checks", "",
        "| File | Presence | Rows | Duplicate rows | Blank values |", "|---|---|---:|---:|---:|",
    ]
    for name, detail in report["files"].items():
        lines.append(f"| `{name}` | {detail['presence']} | {detail['rows']} | {detail['duplicate_rows']} | {detail['blank_value_count']} |")
    lines += ["", "## Metrics", ""]
    lines += [f"- `{key}`: {value}" for key, value in report["metrics"].items()]
    lines += ["", "## Findings", ""]
    if not report["issues"]:
        lines.append("No issues found.")
    else:
        for item in report["issues"]:
            details = ", ".join(f"{key}={value!r}" for key, value in item.items() if key not in {"severity", "message"})
            lines.append(f"- **{item['severity'].upper()} — {item['message']}** ({details})")
    lines += ["", "## Interpretation limits", "",
              "This feed describes scheduled service only. It contains no passenger counts, occupancy, traffic observations, actual vehicle locations, or demand data.",
              "Missing optional files are recorded as unavailable; no service exceptions or route shapes are inferred.", ""]
    return "\n".join(lines)


def run_pipeline(archive_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Validate a GTFS ZIP, write one Parquet file per GTFS table and reports.

    Source columns are retained as strings, and numeric/time convenience
    columns are added. Existing source archive bytes are never modified. The
    output directory is a generated artifact location and is created as needed.
    Structural/schema errors are recorded and prevent a successful status;
    quality warnings are reported without silently dropping records.
    """
    archive_path = Path(archive_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[dict[str, Any]] = []
    files: dict[str, dict[str, Any]] = {}
    tables: dict[str, pl.DataFrame] = {}

    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Cannot open GTFS archive {archive_path}: {exc}") from exc

    with archive:
        members = {Path(name).name: name for name in archive.namelist() if not name.endswith("/") and Path(name).suffix.lower() == ".txt"}
        for required in REQUIRED_FILES:
            if required not in members:
                issues.append(_issue("missing_required_file", "error", f"Required GTFS file {required} is missing.", file=required))
        unrecognized = sorted(set(members) - set(SUPPORTED_FILES))
        for name in unrecognized:
            issues.append(_issue("unrecognized_gtfs_file", "warning", "GTFS text file is not supported by the current schema registry.", file=name))
        if "calendar.txt" not in members and "calendar_dates.txt" not in members:
            issues.append(_issue("missing_service_calendar", "error", "GTFS requires calendar.txt, calendar_dates.txt, or both."))

        for filename in SUPPORTED_FILES:
            present = filename in members
            if not present:
                if filename == "calendar_dates.txt":
                    frame = pl.DataFrame(schema={"service_id": pl.String, "date": pl.String, "exception_type": pl.String})
                    tables[filename] = frame
                    frame.write_parquet(output_dir / "calendar_dates.parquet")
                    files[filename] = {"presence": "absent_optional_empty_output", "rows": 0, "columns": list(frame.columns), "duplicate_rows": 0, "blank_value_count": 0, "blank_values_by_column": {}}
                elif filename in REQUIRED_FILES:
                    files[filename] = {"presence": "missing_required", "rows": 0, "columns": [], "duplicate_rows": 0, "blank_value_count": 0, "blank_values_by_column": {}}
                else:
                    files[filename] = {"presence": "absent_optional", "rows": 0, "columns": [], "duplicate_rows": 0, "blank_value_count": 0, "blank_values_by_column": {}}
                    issues.append(_issue("missing_optional_file", "info", f"Optional file {filename} is absent.", file=filename))
                continue

            try:
                frame = _read_member(archive, members[filename])
            except Exception as exc:  # malformed CSV should be recorded in the report
                issues.append(_issue("csv_read_error", "error", f"Could not parse {filename}: {exc}", file=filename))
                files[filename] = {"presence": "invalid_csv", "rows": 0, "columns": [], "duplicate_rows": 0, "blank_value_count": 0, "blank_values_by_column": {}}
                continue
            required_columns = REQUIRED_FILES.get(filename, OPTIONAL_FILES.get(filename, ()))
            missing_columns = [column for column in required_columns if column not in frame.columns]
            if missing_columns:
                issues.append(_issue("missing_required_columns", "error", f"{filename} lacks required columns.", file=filename, columns=missing_columns))
            if filename == "routes.txt" and not ({"route_short_name", "route_long_name"} & set(frame.columns)):
                issues.append(_issue("missing_alternative_required_columns", "error", "routes.txt must contain route_short_name or route_long_name.", file=filename, columns=["route_short_name", "route_long_name"]))
            blank_by_column = _blank_counts(frame)
            blank_total = sum(blank_by_column.values())
            duplicate_rows = int(frame.is_duplicated().sum()) if frame.height else 0
            files[filename] = {
                "presence": "present", "rows": frame.height, "columns": frame.columns,
                "duplicate_rows": duplicate_rows, "blank_value_count": blank_total,
                "blank_values_by_column": blank_by_column,
            }
            if blank_total:
                issues.append(_issue("blank_values", "warning", f"{filename} contains blank fields.", file=filename, count=blank_total, by_column={k: v for k, v in blank_by_column.items() if v}))
            if duplicate_rows:
                issues.append(_issue("duplicate_rows", "warning", f"{filename} contains duplicate full rows.", file=filename, count=duplicate_rows))
            for key_columns in [key for table, key in PRIMARY_KEYS.items() if table == filename]:
                if all(column in frame.columns for column in key_columns):
                    dup_keys = int(frame.select(key_columns).is_duplicated().sum())
                    blanks = sum(blank_by_column.get(column, 0) for column in key_columns)
                    files[filename]["duplicate_primary_key_rows"] = dup_keys
                    if dup_keys:
                        issues.append(_issue("duplicate_primary_key", "error", f"{filename} contains duplicate primary keys.", file=filename, columns=list(key_columns), count=dup_keys))
                    if blanks:
                        issues.append(_issue("blank_primary_key", "error", f"{filename} contains blank primary keys.", file=filename, columns=list(key_columns), count=blanks))

            if filename == "calendar.txt":
                for day in _WEEKDAYS:
                    if day in frame.columns:
                        invalid = frame.filter(~pl.col(day).is_in(["0", "1"]) | pl.col(day).is_null()).height
                        if invalid:
                            issues.append(_issue("invalid_calendar_flag", "error", f"calendar.txt has invalid {day} flags.", column=day, count=invalid))
                for column in ("start_date", "end_date"):
                    if column in frame.columns:
                        invalid = sum(not _date_is_valid(v or "") for v in frame[column].to_list())
                        if invalid:
                            issues.append(_issue("invalid_calendar_date", "error", f"calendar.txt has invalid {column} values.", column=column, count=invalid))
                if {"start_date", "end_date"} <= set(frame.columns):
                    backwards = frame.filter(pl.col("start_date") > pl.col("end_date")).height
                    if backwards:
                        issues.append(_issue("inverted_calendar_range", "error", "calendar.txt start_date is after end_date.", count=backwards))
            if filename == "calendar_dates.txt" and "exception_type" in frame.columns:
                invalid = frame.filter(~pl.col("exception_type").is_in(["1", "2"]) | pl.col("exception_type").is_null()).height
                if invalid:
                    issues.append(_issue("invalid_calendar_exception_type", "error", "calendar_dates.txt exception_type must be 1 or 2.", count=invalid))
                if "date" in frame.columns:
                    invalid_dates = sum(not _date_is_valid(v or "") for v in frame["date"].to_list())
                    if invalid_dates:
                        issues.append(_issue("invalid_calendar_date", "error", "calendar_dates.txt has invalid date values.", count=invalid_dates))
            if filename == "stops.txt" and {"stop_lat", "stop_lon"} <= set(frame.columns):
                cast = frame.with_columns(pl.col("stop_lat").cast(pl.Float64, strict=False), pl.col("stop_lon").cast(pl.Float64, strict=False))
                invalid = cast.filter(pl.col("stop_lat").is_null() | pl.col("stop_lon").is_null() | ~pl.col("stop_lat").is_between(-90, 90) | ~pl.col("stop_lon").is_between(-180, 180)).height
                if invalid:
                    issues.append(_issue("invalid_stop_coordinates", "error", "stops.txt has invalid or out-of-range coordinates.", count=invalid))
            if filename == "routes.txt" and "route_type" in frame.columns:
                route_type = pl.col("route_type").cast(pl.Int64, strict=False)
                invalid = frame.filter(~route_type.is_in([0, 1, 2, 3, 4, 5, 6, 7, 11, 12]) | route_type.is_null()).height
                if invalid:
                    issues.append(_issue("invalid_route_type", "error", "routes.txt contains an invalid GTFS route_type.", count=invalid))
            if filename == "routes.txt" and {"route_short_name", "route_long_name"} <= set(frame.columns):
                unnamed = frame.filter(
                    (pl.col("route_short_name").str.strip_chars() == "")
                    & (pl.col("route_long_name").str.strip_chars() == "")
                ).height
                if unnamed:
                    issues.append(_issue("missing_route_name", "error", "routes.txt rows need a route_short_name or route_long_name.", count=unnamed))
            elif filename == "routes.txt":
                name_column = "route_short_name" if "route_short_name" in frame.columns else "route_long_name" if "route_long_name" in frame.columns else None
                if name_column is not None:
                    unnamed = frame.filter(pl.col(name_column).str.strip_chars() == "").height
                    if unnamed:
                        issues.append(_issue("missing_route_name", "error", f"routes.txt contains blank {name_column} values and has no alternate route name column.", column=name_column, count=unnamed))
            if filename == "trips.txt" and "direction_id" in frame.columns:
                direction = pl.col("direction_id").cast(pl.Int64, strict=False)
                invalid = frame.filter(~direction.is_in([0, 1]) | direction.is_null()).height
                if invalid:
                    issues.append(_issue("invalid_direction_id", "error", "trips.txt direction_id must be 0 or 1 when supplied.", count=invalid))
            if filename == "stop_times.txt":
                max_hour = 0
                for column in ("arrival_time", "departure_time"):
                    if column in frame.columns:
                        invalid, hour = _validate_times(frame, column)
                        max_hour = max(max_hour, hour)
                        if invalid:
                            issues.append(_issue("invalid_gtfs_time", "error", f"stop_times.txt has invalid {column} values.", column=column, count=invalid))
                files[filename]["maximum_time_hour"] = max_hour
                if "stop_sequence" in frame.columns:
                    seq = pl.col("stop_sequence").cast(pl.Int64, strict=False)
                    invalid_seq = frame.select(seq.is_null().sum()).item()
                    if invalid_seq:
                        issues.append(_issue("invalid_stop_sequence", "error", "stop_times.txt contains non-integer stop_sequence values.", count=int(invalid_seq)))
                    elif "trip_id" in frame.columns:
                        ordered = frame.with_row_index("_source_order").with_columns(seq.alias("_sequence"))
                        ordered = ordered.sort(["trip_id", "_source_order"]).with_columns(pl.col("_sequence").diff().over("trip_id").alias("_sequence_delta"))
                        not_increasing = ordered.filter(pl.col("_sequence_delta") <= 0).height
                        if not_increasing:
                            issues.append(_issue("non_increasing_stop_sequence", "error", "stop_sequence is duplicated or does not increase in source order within trips.", count=not_increasing))
                        if {"arrival_time", "departure_time"} <= set(frame.columns):
                            timed = frame.with_columns(
                                seq.alias("_sequence"),
                                _time_seconds(frame, "arrival_time").alias("_arrival_seconds"),
                                _time_seconds(frame, "departure_time").alias("_departure_seconds"),
                            ).sort(["trip_id", "_sequence"])
                            departure_before_arrival = timed.filter(pl.col("_departure_seconds") < pl.col("_arrival_seconds")).height
                            if departure_before_arrival:
                                issues.append(_issue("departure_before_arrival", "error", "Stop-time departures precede arrivals at the same stop.", count=departure_before_arrival))
                            ordered_times = timed.with_columns(
                                pl.col("_arrival_seconds").diff().over("trip_id").alias("_arrival_delta"),
                                pl.col("_departure_seconds").diff().over("trip_id").alias("_departure_delta"),
                            )
                            arrival_regressions = ordered_times.filter(pl.col("_arrival_delta") < 0).height
                            departure_regressions = ordered_times.filter(pl.col("_departure_delta") < 0).height
                            files[filename]["arrival_time_regressions"] = arrival_regressions
                            files[filename]["departure_time_regressions"] = departure_regressions
                            if arrival_regressions:
                                issues.append(_issue("arrival_time_regression", "error", "Arrival times decrease along stop_sequence within trips.", count=arrival_regressions))
                            if departure_regressions:
                                issues.append(_issue("departure_time_regression", "error", "Departure times decrease along stop_sequence within trips.", count=departure_regressions))

            typed = _cast_for_analysis(filename, frame)
            typed.write_parquet(output_dir / f"{Path(filename).stem}.parquet", compression="zstd")
            tables[filename] = frame

    rel_issues, metrics = _relationship_report(tables)
    issues.extend(rel_issues)
    report = {
        "source_archive": str(archive_path),
        "status": "failed" if any(item["severity"] == "error" for item in issues) else "passed_with_warnings" if any(item["severity"] == "warning" for item in issues) else "passed",
        "files": files,
        "metrics": metrics,
        "issues": issues,
        "outputs": {"parquet_directory": str(output_dir), "json_report": str(output_dir / "data_quality_report.json"), "markdown_report": str(output_dir / "data_quality_report.md")},
    }
    (output_dir / "data_quality_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "data_quality_report.md").write_text(_markdown_report(report), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and preprocess a GTFS ZIP into Parquet.")
    parser.add_argument("--archive", type=Path, default=Path("data/raw/mtc-gtfs.zip"), help="GTFS ZIP file")
    parser.add_argument("--output", type=Path, default=Path("data/processed/gtfs"), help="Generated output directory")
    args = parser.parse_args()
    report = run_pipeline(args.archive, args.output)
    print(json.dumps({"status": report["status"], "metrics": report["metrics"], "output": report["outputs"]}, indent=2))
    if report["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

