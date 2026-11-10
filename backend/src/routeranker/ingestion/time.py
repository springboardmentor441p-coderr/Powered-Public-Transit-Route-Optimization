"""Utilities for GTFS schedule times."""

from __future__ import annotations

import re

_TIME_PATTERN = re.compile(r"^(\d{1,3}):(\d{2}):(\d{2})$")


def parse_gtfs_time(value: str) -> int:
    """Convert a GTFS ``HH:MM:SS`` value to seconds after service-day start.

    GTFS permits hours greater than 24 to represent after-midnight service.
    The original string is retained in the processed table; this value is an
    additional numeric representation suitable for analysis.

    Raises:
        ValueError: if the value is blank or is not a valid GTFS time.
    """
    match = _TIME_PATTERN.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid GTFS time: {value!r}")
    hours, minutes, seconds = map(int, match.groups())
    if minutes > 59 or seconds > 59:
        raise ValueError(f"Invalid GTFS time: {value!r}")
    return hours * 3600 + minutes * 60 + seconds

