"""
src/data/gtfs_utils.py
Utilities for General Transit Feed Specification (GTFS) time and schedule parsing.
"""

from typing import Tuple, Dict, Any

def parse_gtfs_time(time_str: str) -> Dict[str, Any]:
    """
    Parses a GTFS departure or arrival time string (HH:MM:SS), correctly handling
    post-midnight timestamps where hours >= 24 (e.g. '25:10:00').

    GTFS Standard Specification:
    Times past midnight (hours >= 24) belong to the trip's published SERVICE DATE,
    not the subsequent calendar date.

    Args:
        time_str: GTFS formatted time string (e.g. '08:30:00', '24:15:00', '25:10:00')

    Returns:
        Dictionary containing elapsed seconds, post-midnight flag, normalized clock time,
        and service date offset.
    """
    parts = time_str.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid GTFS time string: '{time_str}'. Expected 'HH:MM:SS'")

    hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
    total_seconds = hours * 3600 + minutes * 60 + seconds

    is_post_midnight = hours >= 24
    normalized_hours = hours % 24
    clock_time = f"{normalized_hours:02d}:{minutes:02d}:{seconds:02d}"

    return {
        "raw_time": time_str,
        "elapsed_seconds": total_seconds,
        "elapsed_hours": round(total_seconds / 3600.0, 3),
        "is_post_midnight": is_post_midnight,
        "clock_time": clock_time,
        "service_date_offset_days": 0  # Trip strictly belongs to service date
    }
