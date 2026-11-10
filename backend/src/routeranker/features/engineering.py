"""RouteRanker route, stop, and route-pair feature engineering."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from .source_validation import SourceSnapshot, derive_source_route_metrics, load_source_snapshot

PEAK_HOUR_RANGES = ((7, 10), (16, 19))
ROUTE_NUMERIC_TO_SCALE = (
    "total_scheduled_trip_records",
    "unique_stop_count",
    "average_first_stop_headway_seconds",
    "headway_interval_count",
    "peak_scheduled_departures_per_template_week",
    "off_peak_scheduled_departures_per_template_week",
    "scheduled_service_span_seconds",
    "shared_stop_count",
)
STOP_NUMERIC_TO_SCALE = ("routes_serving_stop", "scheduled_trip_records_serving_stop")
PAIR_NUMERIC_TO_SCALE = ("shared_stop_count", "route_a_unique_stop_count", "route_b_unique_stop_count")


def _format_time(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    hour, remainder = divmod(int(seconds), 3600)
    minute, second = divmod(remainder, 60)
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def _normalize_frame(
    frame: pl.DataFrame,
    identifiers: tuple[str, ...],
    columns: tuple[str, ...],
    preserve_columns: tuple[str, ...] = (),
) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Median-impute numeric features then standardize each feature (z-score)."""
    if not columns:
        return frame.select(list(identifiers + preserve_columns)), {"training_rows": frame.height, "features": {}}
    matrix = frame.select(list(columns)).to_numpy().astype(np.float64, copy=False)
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    imputed = imputer.fit_transform(matrix)
    scaler = StandardScaler()
    standardized = scaler.fit_transform(imputed)
    result = frame.select(list(identifiers + preserve_columns))
    preserved_imputation: dict[str, float] = {}
    for column in preserve_columns:
        if result.schema[column].is_numeric() and result[column].null_count():
            non_null = result[column].drop_nulls()
            fill = float(non_null.median()) if non_null.len() else 0.0
            result = result.with_columns(pl.col(column).fill_null(fill))
            preserved_imputation[column] = fill
    result = result.with_columns(
        [pl.Series(f"{column}_z", standardized[:, index]) for index, column in enumerate(columns)]
    )
    for index, column in enumerate(columns):
        if not np.isfinite(standardized[:, index]).all():
            raise ValueError(f"Normalized feature {column} contains non-finite values")
    parameters = {
        "training_rows": frame.height,
        "imputation": {column: float(imputer.statistics_[index]) for index, column in enumerate(columns)},
        "standard_scaling": {
            column: {
                "mean": float(scaler.mean_[index]),
                "scale": float(scaler.scale_[index]),
                "variance": float(scaler.var_[index]),
            }
            for index, column in enumerate(columns)
        },
        "preserved_numeric_imputation": preserved_imputation,
    }
    return result, parameters


def _feature_dictionary() -> list[dict[str, str]]:
    """Return descriptions for every engineered feature and model column."""
    definitions = [
        ("route_id", "identifier", "Primary route identifier from routes.txt.", "string", "Kept as an identifier; never normalized."),
        ("stop_id", "identifier", "Primary stop identifier from stops.txt.", "string", "Kept as an identifier; never normalized."),
        ("route_id_a / route_id_b", "route pair identifiers", "Lexicographically ordered identifiers for the compared routes.", "strings", "Not numerical features."),
        ("route_short_name / route_long_name / route_type", "route metadata", "Source route labels and GTFS route type copied from routes.txt.", "strings", "Descriptive source metadata, not numeric model inputs."),
        ("stop_name", "stop metadata", "Source stop label copied from stops.txt.", "string", "Descriptive source metadata, not a numeric model input."),
        ("total_scheduled_trip_records", "route", "Count of trip_id records assigned to route_id in trips.txt.", "trips", "Preserves every supplied trip record; not a daily service or ridership count."),
        ("unique_stop_count", "route", "Distinct stop_id values used by any trip on the route.", "stops", "A stop visited on multiple trips is counted once."),
        ("average_first_stop_headway_seconds", "route", "Weighted mean of consecutive first-stop departure gaps, grouped by route, service_id, and direction_id; group means are weighted by gap count.", "seconds", "Null when no group has two departures; missing values are median-imputed only in the normalized output."),
        ("headway_interval_count", "route", "Number of consecutive-departure gaps contributing to the average headway.", "intervals", "A zero-length gap from simultaneous schedule entries is retained."),
        ("peak_scheduled_departures_per_template_week", "route", "Sum of trip first departures in 07:00-10:00 and 16:00-19:00 across weekdays enabled by each trip's calendar service.", "calendar-flagged trip instances/week", "Fixed local GTFS service-hour windows; calendar_dates exceptions are unavailable."),
        ("off_peak_scheduled_departures_per_template_week", "route", "Sum of trip first departures outside 07:00-10:00 and 16:00-19:00 across calendar-enabled weekdays.", "calendar-flagged trip instances/week", "Includes all other hours and trips whose service_id has no active calendar weekday contributes zero to this weekly template measure."),
        ("first_scheduled_departure_seconds", "route", "Earliest trip departure at its lowest stop_sequence, measured from GTFS service-day start.", "seconds after service-day start", "GTFS hours may exceed 24; not converted to a wall-clock time."),
        ("last_scheduled_departure_seconds", "route", "Latest trip departure at its lowest stop_sequence, measured from GTFS service-day start.", "seconds after service-day start", "This is the last trip start, not the last terminal arrival."),
        ("first_scheduled_departure_time", "route", "HH:MM:SS rendering of the earliest first-stop departure.", "GTFS time", "Retains service hours above 24."),
        ("last_scheduled_departure_time", "route", "HH:MM:SS rendering of the latest first-stop departure.", "GTFS time", "Retains service hours above 24."),
        ("scheduled_service_span_seconds", "route", "Latest final-stop scheduled arrival minus earliest first-stop scheduled departure across route trips.", "seconds", "Schedule envelope, not trip duration, travel time, or actual operating span; null for routes without trips."),
        ("shared_stop_count", "route", "Number of route stops whose stop_id is used by at least one other route.", "stops", "Measures shared identifiers in the supplied network, not transfers or passenger interchange."),
        ("shared_stop_count", "route pair", "Number of distinct stop IDs present in both route stop sets.", "stops", "A count of shared stop identifiers; route pair outputs include pairs sharing at least one stop."),
        ("shared_stop_ratio", "route", "shared_stop_count divided by unique_stop_count.", "ratio [0,1]", "Null when the route has no stop records in raw features; median-imputed but left unscaled in normalized features."),
        ("headway_missing", "route", "1 when the route has no estimable first-stop headway; otherwise 0.", "indicator", "A missing estimate means fewer than two comparable scheduled starts, not zero headway."),
        ("service_span_missing", "route", "1 when no scheduled service span can be calculated; otherwise 0.", "indicator", "Usually marks route records with no trip records."),
        ("shared_stop_ratio_missing", "route", "1 when a route has no stops and the ratio denominator is unavailable; otherwise 0.", "indicator", "Preserves distinction between unavailable and a measured zero ratio."),
        ("routes_serving_stop", "stop", "Number of distinct route_id values with a stop_time at this stop.", "routes", "Zero for unused stop records."),
        ("scheduled_trip_records_serving_stop", "stop", "Number of distinct trip_id values with a stop_time at this stop.", "trip records", "Counts scheduled trip definitions, not daily operations or passenger activity."),
        ("route_a_unique_stop_count", "route pair", "Distinct stop_id count for route_id_a.", "stops", "Pair endpoints are ordered lexicographically by route_id."),
        ("route_b_unique_stop_count", "route pair", "Distinct stop_id count for route_id_b.", "stops", "Pair endpoints are ordered lexicographically by route_id."),
        ("jaccard_similarity", "route pair", "shared_stop_count / (route_a_unique_stop_count + route_b_unique_stop_count - shared_stop_count).", "ratio [0,1]", "Stop-set overlap only; not service substitutability, congestion, or demand."),
    ]
    records = [
        {"feature": name, "level": level, "calculation": calculation, "unit": unit, "limitations_and_missing_values": notes}
        for name, level, calculation, unit, notes in definitions
    ]
    raw_numeric = set(ROUTE_NUMERIC_TO_SCALE + STOP_NUMERIC_TO_SCALE + PAIR_NUMERIC_TO_SCALE)
    for name in sorted(raw_numeric):
        records.append({
            "feature": f"{name}_z", "level": "normalized feature",
            "calculation": f"StandardScaler z-score of {name} after median imputation fitted across all records at this feature level.",
            "unit": "standard deviations from fitted feature mean",
            "limitations_and_missing_values": "Zero-variance columns become zero. Scaling parameters belong to this feed snapshot and must be refit for a changed feed.",
        })
    return records


def _validate_phase1_and_eda(
    source: SourceSnapshot,
    source_features: dict[str, dict[str, Any]],
    gtfs_dir: Path,
    eda_dir: Path,
    route_features: pl.DataFrame,
    stop_features: pl.DataFrame,
    pair_features: pl.DataFrame,
) -> dict[str, Any]:
    """Cross-check source-derived features against Phase 1 and Phase 2 outputs."""
    phase1_report_path = gtfs_dir / "data_quality_report.json"
    phase2_report_path = eda_dir / "eda_report.json"
    if not phase1_report_path.is_file() or not phase2_report_path.is_file():
        raise FileNotFoundError("Verified Phase 1 and Phase 2 JSON reports are required for feature validation")
    phase1 = json.loads(phase1_report_path.read_text(encoding="utf-8"))
    phase2 = json.loads(phase2_report_path.read_text(encoding="utf-8"))
    if phase1.get("status") == "failed":
        raise ValueError("Phase 1 quality report status is failed")

    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, expected: Any, actual: Any, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "expected": expected, "actual": actual, "detail": detail})

    for filename, source_name in (("routes.txt", "route_records"), ("stops.txt", "stop_records"), ("trips.txt", "trip_records"), ("stop_times.txt", "stop_time_records"), ("calendar.txt", "calendar_service_rows")):
        reported = phase1.get("files", {}).get(filename, {}).get("rows")
        actual = source.row_counts[filename]
        add_check(f"phase1_source_rows_{filename}", reported == actual, actual, reported, "Phase 1 recorded row count matches the original ZIP.")
        phase1_parquet = gtfs_dir / filename.replace(".txt", ".parquet")
        if phase1_parquet.exists():
            parquet_rows = pl.scan_parquet(phase1_parquet).select(pl.len()).collect(engine="streaming").item()
            add_check(f"phase1_parquet_rows_{filename}", parquet_rows == actual, actual, parquet_rows, "Phase 1 Parquet row count matches the original ZIP.")

    for key, source_value in (
        ("route_records", source.row_counts["routes.txt"]),
        ("stop_records", source.row_counts["stops.txt"]),
        ("trip_records", source.row_counts["trips.txt"]),
        ("stop_time_records", source.row_counts["stop_times.txt"]),
    ):
        add_check(f"phase2_total_{key}", phase2.get("totals", {}).get(key) == source_value, source_value, phase2.get("totals", {}).get(key), "Phase 2 EDA total matches the source ZIP.")

    route_summary = pl.read_csv(eda_dir / "route_summary.csv", infer_schema=False).with_columns(pl.col("route_id").cast(pl.String))
    stop_summary = pl.read_csv(eda_dir / "stop_summary.csv", infer_schema=False).with_columns(pl.col("stop_id").cast(pl.String))
    expected_route_ids = set(source.routes)
    phase2_route_ids = set(route_summary["route_id"].to_list())
    add_check("route_feature_ids_match_source", set(route_features["route_id"].to_list()) == expected_route_ids, len(expected_route_ids), route_features.height, "Every original route has one feature row, including unused routes.")
    add_check("phase2_route_ids_match_source", phase2_route_ids == expected_route_ids, len(expected_route_ids), len(phase2_route_ids), "Phase 2 route summary identifiers match the original routes.txt.")
    route_expected_by_id = {row["route_id"]: row for row in route_features.iter_rows(named=True)}
    phase2_route_errors = 0
    for row in route_summary.iter_rows(named=True):
        expected = source_features[row["route_id"]]
        if int(row["trip_count"]) != expected["total_scheduled_trip_records"] or int(row["stop_count"]) != expected["unique_stop_count"]:
            phase2_route_errors += 1
            continue
        if row.get("first_service_time") != _format_time(expected["first_scheduled_departure_seconds"]):
            phase2_route_errors += 1
            continue
        last_arrival = source_features[row["route_id"]].get("_last_terminal_arrival_seconds")
        if row.get("last_service_time") != _format_time(last_arrival):
            phase2_route_errors += 1
    add_check("phase2_route_metrics_match_source", phase2_route_errors == 0, 0, phase2_route_errors, "Phase 2 route trip/stop counts and first/last service times match raw GTFS.")

    phase2_stop_errors = 0
    source_stop_routes = source.stop_routes
    source_stop_trips = source.stop_trips
    source_stop_ids = set(source.stops)
    phase2_stop_ids = set(stop_summary["stop_id"].to_list())
    add_check("stop_feature_ids_match_source", set(stop_features["stop_id"].to_list()) == source_stop_ids, len(source_stop_ids), stop_features.height, "Every original stop has one feature row, including unused stops.")
    add_check("phase2_stop_ids_match_source", phase2_stop_ids == source_stop_ids, len(source_stop_ids), len(phase2_stop_ids), "Phase 2 stop summary identifiers match the original stops.txt.")
    stop_feature_map = {row["stop_id"]: row for row in stop_features.iter_rows(named=True)}
    for row in stop_summary.iter_rows(named=True):
        stop_id = row["stop_id"]
        expected_routes = len(source_stop_routes.get(stop_id, set()))
        expected_trips = len(source_stop_trips.get(stop_id, set()))
        if int(row["route_count"]) != expected_routes or int(row["trip_count"]) != expected_trips:
            phase2_stop_errors += 1
        feature = stop_feature_map.get(stop_id, {})
        if feature.get("routes_serving_stop") != expected_routes or feature.get("scheduled_trip_records_serving_stop") != expected_trips:
            phase2_stop_errors += 1
    add_check("phase2_stop_metrics_match_source", phase2_stop_errors == 0, 0, phase2_stop_errors, "Phase 2 and Phase 3 stop route/trip counts match raw GTFS.")

    phase2_route_stop = pl.read_parquet(eda_dir / "route_stop_coverage.parquet")
    source_route_stop_pairs = {(route_id, stop_id) for route_id, stop_ids in source.route_stops.items() for stop_id in stop_ids}
    phase2_route_stop_pairs = set(zip(phase2_route_stop["route_id"].to_list(), phase2_route_stop["stop_id"].to_list()))
    add_check("route_stop_coverage_matches_source", phase2_route_stop_pairs == source_route_stop_pairs, len(source_route_stop_pairs), len(phase2_route_stop_pairs), "Phase 2 distinct route-stop coverage pairs exactly match the source ZIP.")
    route_stop_unique_rows = phase2_route_stop.height == len(phase2_route_stop_pairs)
    add_check("route_stop_coverage_has_unique_rows", route_stop_unique_rows, len(phase2_route_stop_pairs), phase2_route_stop.height, "The Phase 2 route-stop relation has no duplicate pairs.")

    phase2_headways = pl.read_csv(eda_dir / "route_service_headways.csv", infer_schema=False)
    raw_group_values: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for trip_id, (route_id, service_id, direction_id) in source.trip_meta.items():
        raw_group_values[(route_id, service_id, direction_id)].append(source.trip_endpoints[trip_id][1])
    expected_headways: dict[tuple[str, str, str], tuple[int, float | None]] = {}
    for key, starts in raw_group_values.items():
        gaps = sorted(starts)
        intervals = [b - a for a, b in zip(gaps, gaps[1:])]
        expected_headways[key] = (len(starts), sum(intervals) / len(intervals) if intervals else None)
    phase2_headway_errors = 0
    for row in phase2_headways.iter_rows(named=True):
        key = (row["route_id"], row["service_id"], row["direction_id"])
        expected = expected_headways.get(key)
        if expected is None or int(row["scheduled_trip_count"]) != expected[0]:
            phase2_headway_errors += 1
            continue
        observed_mean = row["mean_headway_seconds"]
        if expected[1] is None:
            if observed_mean not in (None, ""):
                phase2_headway_errors += 1
        elif observed_mean in (None, "") or not math.isclose(float(observed_mean), expected[1], rel_tol=0, abs_tol=1e-8):
            phase2_headway_errors += 1
    add_check("phase2_headways_match_source", phase2_headway_errors == 0 and phase2_headways.height == len(expected_headways), 0, phase2_headway_errors, "Phase 2 route/service/direction headway statistics match first-stop times in the original ZIP.")

    pair_source = pl.read_parquet(eda_dir / "route_pair_overlap.parquet")
    add_check("route_pair_feature_rows_match_phase2", pair_features.height == pair_source.height, pair_source.height, pair_features.height, "Feature route-pair coverage matches the full Phase 2 pair table.")
    pair_unique = pair_source.select("route_id_a", "route_id_b").is_duplicated().sum() == 0
    add_check("route_pair_ids_are_unique", pair_unique, 0, int(pair_source.select("route_id_a", "route_id_b").is_duplicated().sum()), "Each unordered route pair appears at most once.")
    pair_errors = 0
    route_stop_sets = source.route_stops
    for row in pair_source.iter_rows(named=True):
        route_a, route_b = row["route_id_a"], row["route_id_b"]
        a_set, b_set = route_stop_sets.get(route_a, set()), route_stop_sets.get(route_b, set())
        shared = len(a_set.intersection(b_set))
        denom = len(a_set) + len(b_set) - shared
        jaccard = shared / denom if denom else 0.0
        if shared != int(row["shared_stop_count"]) or not math.isclose(jaccard, float(row["jaccard_similarity"]), rel_tol=0, abs_tol=1e-12):
            pair_errors += 1
    add_check("route_pair_similarity_matches_source", pair_errors == 0, 0, pair_errors, "Every Phase 2 shared-stop count and Jaccard value matches stop sets derived from the original ZIP.")

    return {
        "status": "passed" if all(check["passed"] for check in checks) else "failed",
        "source_archive": None,
        "checks": checks,
        "check_count": len(checks),
        "passed_checks": sum(check["passed"] for check in checks),
        "failed_checks": [check for check in checks if not check["passed"]],
    }


def _write_dictionary(output_dir: Path, records: list[dict[str, str]]) -> None:
    frame = pl.DataFrame(records)
    frame.write_csv(output_dir / "feature_dictionary.csv")
    lines = [
        "# Feature dictionary", "",
        "Every feature is derived from scheduled GTFS fields. No ridership, passenger demand, occupancy, traffic, or actual vehicle performance fields are used.", "",
        "Normalization uses median imputation followed by `StandardScaler` z-scores, fit separately by feature level on the complete current feed. Raw feature datasets retain nulls and zero counts as appropriate. Normalized route features include missingness indicators for nullable fields; normalized outputs contain imputed values. Clock-time features are excluded from z-scoring, and ratios/Jaccard values already bounded to [0,1] remain on their original scale.", "",
        "| Feature | Level | Calculation | Unit | Limitations and missing values |",
        "|---|---|---|---|---|"]
    for row in records:
        cells = [row[key].replace("|", "&#124;").replace("\n", " ") for key in ("feature", "level", "calculation", "unit", "limitations_and_missing_values")]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    (output_dir / "feature_dictionary.md").write_text("\n".join(lines), encoding="utf-8")


def run_feature_engineering(
    archive_path: str | Path,
    gtfs_dir: str | Path,
    eda_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Generate and validate raw and normalized feature datasets.

    The original ZIP is streamed for independent validation. Phase 1 Parquets
    and Phase 2 EDA summaries/relation tables are required and cross-checked.
    No source file or earlier phase output is modified.
    """
    archive_path, gtfs_dir, eda_dir, output_dir = map(Path, (archive_path, gtfs_dir, eda_dir, output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    required_gtfs = ("routes.parquet", "stops.parquet", "trips.parquet", "stop_times.parquet", "calendar.parquet", "data_quality_report.json")
    missing_gtfs = [filename for filename in required_gtfs if not (gtfs_dir / filename).is_file()]
    required_eda = ("eda_report.json", "route_summary.csv", "stop_summary.csv", "route_service_headways.csv", "route_stop_coverage.parquet", "route_pair_overlap.parquet")
    missing_eda = [filename for filename in required_eda if not (eda_dir / filename).is_file()]
    if missing_gtfs or missing_eda:
        raise FileNotFoundError(f"Missing verified inputs: Phase 1={missing_gtfs}, Phase 2={missing_eda}")

    source = load_source_snapshot(str(archive_path.resolve()))
    source_route_metrics = derive_source_route_metrics(source)
    route_rows: list[dict[str, Any]] = []
    for route_id, metrics in source_route_metrics.items():
        metadata = source.routes[route_id]
        row = {"route_id": route_id, **metadata, **{key: value for key, value in metrics.items() if not key.startswith("_")}}
        row["first_scheduled_departure_time"] = _format_time(metrics["first_scheduled_departure_seconds"])
        row["last_scheduled_departure_time"] = _format_time(metrics["last_scheduled_departure_seconds"])
        row["headway_missing"] = int(metrics["average_first_stop_headway_seconds"] is None)
        row["service_span_missing"] = int(metrics["scheduled_service_span_seconds"] is None)
        row["shared_stop_ratio_missing"] = int(metrics["shared_stop_ratio"] is None)
        route_rows.append(row)
    route_schema = {
        "route_id": pl.String, "route_short_name": pl.String, "route_long_name": pl.String, "route_type": pl.String,
        "total_scheduled_trip_records": pl.Int64, "unique_stop_count": pl.Int64,
        "average_first_stop_headway_seconds": pl.Float64, "headway_interval_count": pl.Int64,
        "peak_scheduled_departures_per_template_week": pl.Int64, "off_peak_scheduled_departures_per_template_week": pl.Int64,
        "first_scheduled_departure_seconds": pl.Int64, "last_scheduled_departure_seconds": pl.Int64,
        "first_scheduled_departure_time": pl.String, "last_scheduled_departure_time": pl.String,
        "scheduled_service_span_seconds": pl.Int64, "shared_stop_count": pl.Int64, "shared_stop_ratio": pl.Float64,
        "headway_missing": pl.Int8, "service_span_missing": pl.Int8, "shared_stop_ratio_missing": pl.Int8,
    }
    route_features = pl.DataFrame(route_rows, schema=route_schema)

    stop_rows = [
        {
            "stop_id": stop_id,
            "stop_name": metadata["stop_name"],
            "routes_serving_stop": len(source.stop_routes.get(stop_id, set())),
            "scheduled_trip_records_serving_stop": len(source.stop_trips.get(stop_id, set())),
        }
        for stop_id, metadata in source.stops.items()
    ]
    stop_features = pl.DataFrame(stop_rows, schema={
        "stop_id": pl.String, "stop_name": pl.String, "routes_serving_stop": pl.Int64,
        "scheduled_trip_records_serving_stop": pl.Int64,
    })

    phase2_pairs = pl.read_parquet(eda_dir / "route_pair_overlap.parquet")
    pair_features = phase2_pairs.select(
        "route_id_a", "route_id_b", "shared_stop_count", "route_a_stop_count", "route_b_stop_count", "jaccard_similarity"
    ).rename({"route_a_stop_count": "route_a_unique_stop_count", "route_b_stop_count": "route_b_unique_stop_count"})

    route_normalized, route_norm_parameters = _normalize_frame(
        route_features,
        ("route_id",),
        ROUTE_NUMERIC_TO_SCALE,
        ("headway_missing", "service_span_missing", "shared_stop_ratio_missing", "shared_stop_ratio"),
    )
    stop_normalized, stop_norm_parameters = _normalize_frame(stop_features, ("stop_id",), STOP_NUMERIC_TO_SCALE)
    pair_normalized, pair_norm_parameters = _normalize_frame(
        pair_features,
        ("route_id_a", "route_id_b"),
        PAIR_NUMERIC_TO_SCALE,
        ("jaccard_similarity",),
    )

    route_features.write_parquet(output_dir / "route_features.parquet", compression="zstd")
    route_features.write_csv(output_dir / "route_features.csv")
    route_normalized.write_parquet(output_dir / "route_features_normalized.parquet", compression="zstd")
    route_normalized.write_csv(output_dir / "route_features_normalized.csv")
    stop_features.write_parquet(output_dir / "stop_features.parquet", compression="zstd")
    stop_features.write_csv(output_dir / "stop_features.csv")
    stop_normalized.write_parquet(output_dir / "stop_features_normalized.parquet", compression="zstd")
    stop_normalized.write_csv(output_dir / "stop_features_normalized.csv")
    pair_features.write_parquet(output_dir / "route_pair_features.parquet", compression="zstd")
    pair_features.write_csv(output_dir / "route_pair_features.csv")
    pair_normalized.write_parquet(output_dir / "route_pair_features_normalized.parquet", compression="zstd")
    pair_normalized.write_csv(output_dir / "route_pair_features_normalized.csv")
    normalization_parameters = {
        "method": "sklearn SimpleImputer(strategy='median') followed by sklearn StandardScaler",
        "route": route_norm_parameters,
        "stop": stop_norm_parameters,
        "route_pair": pair_norm_parameters,
        "notes": [
            "Parameters are fitted separately for each level on all rows in the current feed, including unused route/stop records.",
            "GTFS clock-time columns are not standardized; ratio and Jaccard columns already bounded to [0,1] remain unscaled.",
            "Refit these parameters when the feed or training population changes.",
        ],
    }
    (output_dir / "normalization_parameters.json").write_text(json.dumps(normalization_parameters, indent=2), encoding="utf-8")
    dictionary = _feature_dictionary()
    _write_dictionary(output_dir, dictionary)

    validation = _validate_phase1_and_eda(source, source_route_metrics, gtfs_dir, eda_dir, route_features, stop_features, pair_features)
    validation["source_archive"] = str(archive_path.resolve())
    normalized_tables = {
        "route_normalized": route_normalized,
        "stop_normalized": stop_normalized,
        "route_pair_normalized": pair_normalized,
    }
    for name, frame in normalized_tables.items():
        null_total = sum(frame[column].null_count() for column in frame.columns)
        validation["checks"].append({
            "check": f"{name}_contains_no_missing_values",
            "passed": null_total == 0,
            "expected": 0,
            "actual": null_total,
            "detail": "Median imputation is applied to normalized numeric columns; raw feature tables retain valid nulls.",
        })
        for column in frame.columns:
            if not column.endswith("_z"):
                continue
            values = frame[column].to_numpy()
            mean = float(np.mean(values)) if len(values) else 0.0
            std = float(np.std(values)) if len(values) else 0.0
            valid = abs(mean) < 1e-8 and (abs(std - 1.0) < 1e-8 or std == 0.0)
            validation["checks"].append({
                "check": f"{name}_{column}_z_score",
                "passed": valid,
                "expected": "mean 0 and population standard deviation 1 (or 0 for constant columns)",
                "actual": {"mean": mean, "population_std": std},
                "detail": "Check StandardScaler output.",
            })
    validation["check_count"] = len(validation["checks"])
    validation["passed_checks"] = sum(check["passed"] for check in validation["checks"])
    validation["failed_checks"] = [check for check in validation["checks"] if not check["passed"]]
    validation["status"] = "passed" if not validation["failed_checks"] else "failed"
    validation["source_row_counts"] = source.row_counts
    validation["feature_row_counts"] = {
        "route_features": route_features.height,
        "stop_features": stop_features.height,
        "route_pair_features": pair_features.height,
    }
    (output_dir / "feature_validation_report.json").write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
    validation_lines = [
        "# Feature validation report", "",
        f"- Status: **{validation['status']}**",
        f"- Checks passed: {validation['passed_checks']}/{validation['check_count']}",
        f"- Source ZIP counts: {json.dumps(validation['source_row_counts'], ensure_ascii=False)}", "",
        "## Checks", "", "| Check | Passed | Expected | Actual | Detail |", "|---|---:|---|---|---|"]
    for check in validation["checks"]:
        cells = [check[key] for key in ("check", "passed", "expected", "actual", "detail")]
        validation_lines.append("| " + " | ".join(str(value).replace("|", "&#124;") for value in cells) + " |")
    validation_lines.append("")
    (output_dir / "feature_validation_report.md").write_text("\n".join(validation_lines), encoding="utf-8")
    route_raw_nulls = {column: int(route_features[column].null_count()) for column in route_features.columns if route_features[column].null_count()}
    report = {
        "status": validation["status"],
        "source_archive": str(archive_path.resolve()),
        "output_directory": str(output_dir.resolve()),
        "route_feature_count": route_features.height,
        "stop_feature_count": stop_features.height,
        "route_pair_feature_count": pair_features.height,
        "route_feature_columns": len(route_features.columns) - 1,
        "stop_feature_columns": len(stop_features.columns) - 1,
        "route_pair_feature_columns": len(pair_features.columns) - 2,
        "route_feature_names": [column for column in route_features.columns if column not in {"route_id", "route_short_name", "route_long_name", "route_type"}],
        "stop_feature_names": [column for column in stop_features.columns if column not in {"stop_id", "stop_name"}],
        "route_pair_feature_names": [column for column in pair_features.columns if column not in {"route_id_a", "route_id_b"}],
        "feature_dictionary_count": len(dictionary),
        "raw_route_feature_nulls_by_column": route_raw_nulls,
        "validation_checks_passed": validation["passed_checks"],
        "validation_check_count": validation["check_count"],
        "outputs": [
            "route_features.parquet", "route_features.csv", "route_features_normalized.parquet", "route_features_normalized.csv",
            "stop_features.parquet", "stop_features.csv", "stop_features_normalized.parquet", "stop_features_normalized.csv",
            "route_pair_features.parquet", "route_pair_features.csv", "route_pair_features_normalized.parquet", "route_pair_features_normalized.csv",
            "feature_dictionary.csv", "feature_dictionary.md", "feature_validation_report.json", "feature_validation_report.md",
            "normalization_parameters.json",
            "feature_engineering_report.json", "feature_engineering_report.md",
        ],
    }
    (output_dir / "feature_engineering_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary_lines = [
        "# RouteRanker feature engineering report", "",
        f"- Validation: **{report['status']}** ({report['validation_checks_passed']}/{report['validation_check_count']} checks passed)",
        f"- Route feature rows: {report['route_feature_count']:,}",
        f"- Stop feature rows: {report['stop_feature_count']:,}",
        f"- Route-pair similarity rows: {report['route_pair_feature_count']:,}",
        f"- Feature dictionary entries: {report['feature_dictionary_count']}", "",
        "## Feature construction", "",
        f"- Peak windows: {PEAK_HOUR_RANGES[0][0]:02d}:00-{PEAK_HOUR_RANGES[0][1]:02d}:00 and {PEAK_HOUR_RANGES[1][0]:02d}:00-{PEAK_HOUR_RANGES[1][1]:02d}:00 at each trip's first stop.",
        "- Peak/off-peak counts repeat trip records on weekdays enabled by calendar.txt. Missing calendar_dates.txt means service exceptions are not applied.",
        "- Average headway is weighted by consecutive departure interval count across route/service/direction groups.",
        "- Scheduled service span runs from the earliest first-stop departure to the latest final-stop arrival.",
        "- Raw features preserve nulls for unavailable headway/time/span/ratio values; routes and stops with no service remain in the datasets with zero counts.",
        "- Normalized tables use median imputation and StandardScaler z-scores; normalization parameters are saved separately.", "",
        "## Data integrity", "",
        f"- Original GTFS source rows: `{json.dumps(source.row_counts, ensure_ascii=False)}`",
        f"- Route feature nulls by column (expected for routes with no estimable metric): `{json.dumps(route_raw_nulls, ensure_ascii=False)}`",
        "- Feature validation compares row counts, route/stop IDs, per-route and per-stop counts, route-stop pairs, headways, and all route-pair similarities against the original ZIP and verified Phase 1/2 outputs.",
        "- No passenger demand, ridership, occupancy, traffic, congestion, or actual travel-time features are used.", "",
        "## Limitations", "",
        "- calendar_dates.txt is absent, so date-specific service exceptions cannot be applied.",
        "- frequencies.txt is absent; headways are estimated from trip first-departure times.",
        "- shapes.txt is absent; stop-set features do not measure route geometry or geographic area.",
        "- Peak windows are fixed analytical definitions, not official MTC peak classifications.", "",
        "## Outputs", "",
    ]
    summary_lines += [f"- `{name}`" for name in report["outputs"]]
    summary_lines.append("")
    (output_dir / "feature_engineering_report.md").write_text("\n".join(summary_lines), encoding="utf-8")
    if validation["status"] != "passed":
        raise ValueError(f"Feature validation failed; see {output_dir / 'feature_validation_report.md'}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and validate route, stop, and route-pair features.")
    parser.add_argument("--archive", type=Path, default=Path("data/raw/mtc-gtfs.zip"), help="Original GTFS ZIP for independent validation")
    parser.add_argument("--gtfs", type=Path, default=Path("data/processed/gtfs"), help="Phase 1 Parquet directory")
    parser.add_argument("--eda", type=Path, default=Path("data/processed/eda"), help="Verified Phase 2 EDA directory")
    parser.add_argument("--output", type=Path, default=Path("data/processed/features"), help="Feature outputs directory")
    args = parser.parse_args()
    result = run_feature_engineering(args.archive, args.gtfs, args.eda, args.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

