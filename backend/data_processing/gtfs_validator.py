"""GTFS Validator and Sanitizer Module for RouteRanker.

Validates schema constraints, referential integrity, coordinates, and times.
Sanitizes XSS injections and trailing whitespaces according to transit data quality rules.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Bounding box for Chennai Metropolitan Area and Greater MTC Region
MTC_CH_LAT_MIN = 12.0
MTC_CH_LAT_MAX = 13.8
MTC_CH_LON_MIN = 79.4
MTC_CH_LON_MAX = 80.6

# XSS / HTML Tag pattern
HTML_TAG_REGEX = re.compile(r"<[^>]*?>|javascript:|alert\(|\'/\>|/\>", re.IGNORECASE)
TIME_REGEX = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})$")


@dataclass
class SanitizationEvent:
    """Record of a data quality sanitization fix applied."""
    table: str
    column: str
    original_value: str
    sanitized_value: str
    issue_type: str
    row_identifier: Optional[str] = None


@dataclass
class ValidationIssue:
    """Record of a data validation issue or warning."""
    table: str
    severity: str  # "ERROR", "WARNING", "INFO"
    message: str
    affected_rows: int = 1


@dataclass
class DataQualityReport:
    """Comprehensive data quality audit report for the GTFS feed."""
    agency_count: int = 0
    route_count: int = 0
    stop_count: int = 0
    trip_count: int = 0
    stop_times_count: int = 0
    calendar_count: int = 0
    missing_files: List[str] = field(default_factory=list)
    sanitization_events: List[SanitizationEvent] = field(default_factory=list)
    validation_issues: List[ValidationIssue] = field(default_factory=list)
    times_exceeding_24h_count: int = 0
    orphan_trips_count: int = 0
    orphan_stop_times_count: int = 0
    invalid_coordinates_count: int = 0
    out_of_bounds_stops_count: int = 0
    quality_score: float = 100.0
    passed_validation: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for API responses."""
        res = asdict(self)
        res["sanitization_count"] = len(self.sanitization_events)
        res["issues_count"] = len(self.validation_issues)
        return res


def sanitize_text(val: Any) -> Tuple[str, bool]:
    """Sanitize string from HTML tags, XSS payloads, and trailing/leading whitespace.

    Returns (sanitized_string, was_modified).
    """
    if val is None or pd.isna(val):
        return "", False

    raw_str = str(val)
    # Check trailing / leading whitespace
    stripped = raw_str.strip()
    # Check XSS / HTML injections
    has_xss = bool(HTML_TAG_REGEX.search(stripped))
    if has_xss:
        # Strip dangerous tags and escape
        clean_str = HTML_TAG_REGEX.sub("", stripped).strip()
        if not clean_str:
            clean_str = "sanitized_identifier"
        clean_str = html.escape(clean_str)
        return clean_str, True

    if stripped != raw_str:
        return stripped, True

    return raw_str, False


def parse_gtfs_time_seconds(time_str: str) -> Tuple[int, str, int, bool]:
    """Parse GTFS time string which can exceed 24:00:00 (e.g. 25:15:00).

    Returns:
        (total_seconds, normalized_hh_mm_ss, day_offset, exceeds_24h)
    """
    if not isinstance(time_str, str):
        return 0, "00:00:00", 0, False

    match = TIME_REGEX.match(time_str.strip())
    if not match:
        return 0, "00:00:00", 0, False

    h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
    total_seconds = h * 3600 + m * 60 + s
    day_offset = h // 24
    exceeds_24h = h >= 24

    normalized_hour = h % 24
    normalized_str = f"{normalized_hour:02d}:{m:02d}:{s:02d}"

    return total_seconds, normalized_str, day_offset, exceeds_24h


class GTFSValidator:
    """Validates and sanitizes GTFS datasets."""

    def __init__(self) -> None:
        self.report = DataQualityReport()

    def sanitize_calendar(self, calendar_df: pd.DataFrame) -> pd.DataFrame:
        """Sanitize calendar.txt: remove XSS injections and strip whitespace from service_id."""
        df = calendar_df.copy()
        if "service_id" not in df.columns:
            return df

        service_id_map: Dict[str, str] = {}
        for idx, orig_val in df["service_id"].items():
            clean_val, modified = sanitize_text(orig_val)
            if modified:
                service_id_map[orig_val] = clean_val
                self.report.sanitization_events.append(
                    SanitizationEvent(
                        table="calendar",
                        column="service_id",
                        original_value=str(orig_val),
                        sanitized_value=clean_val,
                        issue_type="XSS / Whitespace Sanitization",
                        row_identifier=f"row_{idx}",
                    )
                )

        df["service_id"] = df["service_id"].replace(service_id_map)
        # Ensure day columns are integer 0 or 1
        day_cols = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for col in day_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        return df

    def sanitize_routes(self, routes_df: pd.DataFrame) -> pd.DataFrame:
        """Sanitize routes.txt: trim whitespace and sanitize strings."""
        df = routes_df.copy()
        for col in ["route_id", "agency_id", "route_short_name", "route_long_name"]:
            if col in df.columns:
                cleaned_series = []
                for val in df[col]:
                    clean_val, modified = sanitize_text(val)
                    if modified and (clean_val != val):
                        self.report.sanitization_events.append(
                            SanitizationEvent(
                                table="routes",
                                column=col,
                                original_value=str(val),
                                sanitized_value=clean_val,
                                issue_type="String Sanitization",
                            )
                        )
                    cleaned_series.append(clean_val)
                df[col] = cleaned_series

        return df

    def sanitize_stops(self, stops_df: pd.DataFrame) -> pd.DataFrame:
        """Sanitize stops.txt: trim stop_id and validate coordinates."""
        df = stops_df.copy()
        if "stop_id" in df.columns:
            df["stop_id"] = df["stop_id"].astype(str).str.strip()

        if "stop_name" in df.columns:
            df["stop_name"] = df["stop_name"].astype(str).str.strip()

        # Coordinate validation
        if "stop_lat" in df.columns and "stop_lon" in df.columns:
            df["stop_lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
            df["stop_lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")

            invalid_coords = df["stop_lat"].isna() | df["stop_lon"].isna() | \
                             (df["stop_lat"] < -90) | (df["stop_lat"] > 90) | \
                             (df["stop_lon"] < -180) | (df["stop_lon"] > 180)
            self.report.invalid_coordinates_count = int(invalid_coords.sum())

            # Check bounds for Chennai region
            out_of_bounds = (~invalid_coords) & (
                (df["stop_lat"] < MTC_CH_LAT_MIN) | (df["stop_lat"] > MTC_CH_LAT_MAX) |
                (df["stop_lon"] < MTC_CH_LON_MIN) | (df["stop_lon"] > MTC_CH_LON_MAX)
            )
            self.report.out_of_bounds_stops_count = int(out_of_bounds.sum())

            if self.report.out_of_bounds_stops_count > 0:
                self.report.validation_issues.append(
                    ValidationIssue(
                        table="stops",
                        severity="WARNING",
                        message=f"{self.report.out_of_bounds_stops_count} stops outside standard Chennai MTC bounding box",
                        affected_rows=self.report.out_of_bounds_stops_count,
                    )
                )

        return df

    def sanitize_trips(self, trips_df: pd.DataFrame, valid_route_ids: Set[str], valid_service_ids: Set[str]) -> pd.DataFrame:
        """Sanitize trips.txt and check referential integrity with routes and calendar."""
        df = trips_df.copy()
        for col in ["trip_id", "route_id", "service_id"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        # Referential checks
        if "route_id" in df.columns:
            orphan_routes = ~df["route_id"].isin(valid_route_ids)
            orphan_count = int(orphan_routes.sum())
            if orphan_count > 0:
                self.report.orphan_trips_count += orphan_count
                self.report.validation_issues.append(
                    ValidationIssue(
                        table="trips",
                        severity="WARNING",
                        message=f"{orphan_count} trips reference non-existent route_id",
                        affected_rows=orphan_count,
                    )
                )

        if "service_id" in df.columns:
            orphan_services = ~df["service_id"].isin(valid_service_ids)
            orphan_service_count = int(orphan_services.sum())
            if orphan_service_count > 0:
                self.report.validation_issues.append(
                    ValidationIssue(
                        table="trips",
                        severity="WARNING",
                        message=f"{orphan_service_count} trips reference non-existent service_id in calendar.txt",
                        affected_rows=orphan_service_count,
                    )
                )

        return df

    def validate_and_sanitize_all(
        self,
        tables: Dict[str, pd.DataFrame],
    ) -> Tuple[Dict[str, pd.DataFrame], DataQualityReport]:
        """Run full validation, referential integrity check, and sanitization across all tables."""
        sanitized_tables: Dict[str, pd.DataFrame] = {}

        # 1. Agency
        if "agency" in tables:
            agency_df = tables["agency"].copy()
            if "agency_name" in agency_df.columns:
                agency_df["agency_name"] = agency_df["agency_name"].astype(str).str.strip()
            sanitized_tables["agency"] = agency_df
            self.report.agency_count = len(agency_df)
        else:
            self.report.missing_files.append("agency.txt")

        # 2. Calendar (Sanitize XSS & whitespace)
        if "calendar" in tables:
            cal_df = self.sanitize_calendar(tables["calendar"])
            sanitized_tables["calendar"] = cal_df
            self.report.calendar_count = len(cal_df)
            valid_service_ids = set(cal_df["service_id"].astype(str))
        else:
            self.report.missing_files.append("calendar.txt")
            valid_service_ids = set()

        # 3. Routes
        if "routes" in tables:
            routes_df = self.sanitize_routes(tables["routes"])
            sanitized_tables["routes"] = routes_df
            self.report.route_count = len(routes_df)
            valid_route_ids = set(routes_df["route_id"].astype(str))
        else:
            self.report.missing_files.append("routes.txt")
            valid_route_ids = set()

        # 4. Stops
        if "stops" in tables:
            stops_df = self.sanitize_stops(tables["stops"])
            sanitized_tables["stops"] = stops_df
            self.report.stop_count = len(stops_df)
        else:
            self.report.missing_files.append("stops.txt")

        # 5. Trips
        if "trips" in tables:
            trips_df = self.sanitize_trips(tables["trips"], valid_route_ids, valid_service_ids)
            sanitized_tables["trips"] = trips_df
            self.report.trip_count = len(trips_df)
        else:
            self.report.missing_files.append("trips.txt")

        # 6. Feed Info (if present)
        if "feed_info" in tables:
            feed_df = tables["feed_info"].copy()
            for col in feed_df.columns:
                feed_df[col] = feed_df[col].astype(str).str.strip()
            sanitized_tables["feed_info"] = feed_df

        # Quality score computation
        score = 100.0
        if self.report.missing_files:
            score -= len(self.report.missing_files) * 15.0
        if self.report.invalid_coordinates_count > 0:
            score -= min(10.0, self.report.invalid_coordinates_count * 0.5)
        if self.report.orphan_trips_count > 0:
            score -= min(15.0, self.report.orphan_trips_count * 0.1)

        self.report.quality_score = max(0.0, min(100.0, round(score, 2)))
        self.report.passed_validation = len(self.report.missing_files) == 0

        logger.info(
            f"Validation complete: Score={self.report.quality_score}%, "
            f"Sanitizations={len(self.report.sanitization_events)}, "
            f"Issues={len(self.report.validation_issues)}"
        )

        return sanitized_tables, self.report

