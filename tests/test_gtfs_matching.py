"""
tests/test_gtfs_matching.py
Unit tests for GTFS bus route filtering, route ID compatibility, and corridor overlap.
"""

import pytest
import pandas as pd
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = WORKSPACE_ROOT / "data" / "processed"

@pytest.fixture(scope="module")
def gtfs_routes():
    path = PROCESSED_DIR / "gtfs_routes_clean.parquet"
    assert path.exists()
    return pd.read_parquet(path)

@pytest.fixture(scope="module")
def overlap_df():
    path = PROCESSED_DIR / "route_overlap.parquet"
    assert path.exists()
    return pd.read_parquet(path)

def test_bus_route_count(gtfs_routes):
    # CTA GTFS contains exactly 124 bus routes (route_type = 3), rail routes excluded
    assert len(gtfs_routes) == 124, f"Expected 124 bus routes, got {len(gtfs_routes)}"

def test_scheduled_trips_positive(gtfs_routes):
    # Weekday scheduled trips must be non-negative
    assert (gtfs_routes["weekday_scheduled_trips"] < 0).sum() == 0
    # Over 90% of bus routes should have active weekday service
    active_routes = (gtfs_routes["weekday_scheduled_trips"] > 0).sum()
    assert active_routes >= 120

def test_jaccard_overlap_bounds(overlap_df):
    assert len(overlap_df) > 500, f"Expected >500 overlapping corridor pairs, got {len(overlap_df)}"
    # Jaccard similarity must be in [0, 1]
    assert overlap_df["jaccard_similarity"].min() >= 0.0
    assert overlap_df["jaccard_similarity"].max() <= 1.0
    # Smaller-route containment must be in [0, 1]
    assert overlap_df["smaller_route_containment"].min() >= 0.0
    assert overlap_df["smaller_route_containment"].max() <= 1.0

def test_known_high_overlap_pairs(overlap_df):
    # Route 49 Local and X49 Express share Western Ave corridor
    match = overlap_df[
        ((overlap_df["route_a"] == "49") & (overlap_df["route_b"] == "X49")) |
        ((overlap_df["route_a"] == "X49") & (overlap_df["route_b"] == "49"))
    ]
    assert not match.empty, "Corridor overlap between 49 and X49 not detected"
    row = match.iloc[0]
    assert row["smaller_route_containment"] >= 0.95, f"X49 should be ~100% contained within 49, got {row['smaller_route_containment']}"

def test_post_midnight_gtfs_time_handling():
    from src.data.gtfs_utils import parse_gtfs_time

    # Standard daytime run
    res_day = parse_gtfs_time("14:30:00")
    assert res_day["elapsed_seconds"] == 14 * 3600 + 30 * 60
    assert not res_day["is_post_midnight"]
    assert res_day["clock_time"] == "14:30:00"
    assert res_day["service_date_offset_days"] == 0

    # Post-midnight late night run: 25:10:00 (1:10 AM next calendar day)
    res_night = parse_gtfs_time("25:10:00")
    assert res_night["elapsed_seconds"] == 25 * 3600 + 10 * 60
    assert res_night["is_post_midnight"]
    assert res_night["clock_time"] == "01:10:00"
    # Crucial: Service date offset remains 0 (belongs to previous evening's service date)
    assert res_night["service_date_offset_days"] == 0

    # Extreme post-midnight run: 26:45:30 (2:45 AM)
    res_late = parse_gtfs_time("26:45:30")
    assert res_late["is_post_midnight"]
    assert res_late["clock_time"] == "02:45:30"
