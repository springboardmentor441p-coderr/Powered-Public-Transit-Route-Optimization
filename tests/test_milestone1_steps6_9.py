"""
Tests for Milestone 1 Steps 6-9.

Unit tests (synthetic data, fast):
  - after-midnight trips roll over to the next calendar date
  - a trip arriving exactly on the hour is not running in that hour
  - a trip crossing midnight is running on both dates
  - clock dates outside the window are dropped

Real-data tests (need data/raw/gtfs and data/processed):
  - Step 6 integrity on one version
  - Step 7 holiday: Memorial Day drops weekday service
  - Step 8 switch-over dates map to the expected version
  - Step 9 output shape and invariants

Run:  python -m pytest tests -v
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.build_schedule import (
    USABLE_SNAPSHOTS,
    GTFSFeed,
    count_trip_hours,
    select_snapshot_schedule,
)
from src.check_gtfs_integrity import check_snapshot_integrity

ROOT = Path(__file__).resolve().parents[1]
H = 3600


def _grid(service_date, trips, start="2026-01-01", end="2026-12-31"):
    g = defaultdict(lambda: [0, 0])
    count_trip_hours(service_date, trips, g, start, end)
    return dict(g)


# ---------- Step 9 unit tests (synthetic) ----------

def test_after_midnight_trip_counts_on_next_date():
    # 25:10 -> 25:50 on service date 3 Mar = 01:10-01:50 on 4 Mar
    g = _grid(datetime(2026, 3, 3), [("M1", 25 * H + 600, 25 * H + 3000)])
    assert g == {("M1", "2026-03-04", 1): [1, 1]}


def test_trip_crossing_midnight_runs_on_both_dates():
    # 23:50 -> 24:20 on 3 Mar
    g = _grid(datetime(2026, 3, 3), [("M1", 23 * H + 3000, 24 * H + 1200)])
    assert g[("M1", "2026-03-03", 23)] == [1, 1]
    assert g[("M1", "2026-03-04", 0)] == [0, 1]
    assert len(g) == 2


def test_trip_ending_exactly_on_hour_not_running_next_hour():
    # 08:30 -> 09:00:00 runs in hour 8 only
    g = _grid(datetime(2026, 5, 18), [("M1", 8 * H + 1800, 9 * H)])
    assert g == {("M1", "2026-05-18", 8): [1, 1]}


def test_long_trip_runs_in_every_hour_it_touches():
    # 14:54 -> 17:13 runs in hours 14, 15, 16, 17
    g = _grid(datetime(2026, 5, 18), [("M3", 14 * H + 3240, 17 * H + 780)])
    assert sorted(k[2] for k in g) == [14, 15, 16, 17]
    assert sum(v[0] for v in g.values()) == 1


def test_clock_dates_outside_window_dropped():
    # Service day 30 Sep, trip at 24:30 lands on 1 Oct, outside window ending 30 Sep
    g = _grid(datetime(2026, 9, 30), [("M1", 24 * H + 1800, 24 * H + 2400)],
              start="2026-01-03", end="2026-09-30")
    assert g == {}


# ---------- Real-data tests ----------

@pytest.fixture(scope="module")
def feeds():
    return {s: GTFSFeed(s) for s in USABLE_SNAPSHOTS}


@pytest.fixture(scope="module")
def date_info(feeds):
    return select_snapshot_schedule(feeds, "2026-01-03", "2026-09-30")


def test_step_6_gtfs_referential_integrity():
    res = check_snapshot_integrity("2026-03-27")
    assert res["referential_integrity_passed"] is True
    assert res["times_ge_24h"] > 0, "Feed should contain after-midnight times >= 24:00"


def test_step_7_memorial_day_drops_weekday_service(feeds):
    feed = feeds["2026-04-09"]
    normal = feed.get_active_services(datetime(2026, 5, 18))
    holiday = feed.get_active_services(datetime(2026, 5, 25))
    main_weekday = {s for s in normal if s.endswith("Weekday-SDon")}
    assert main_weekday, "Normal Monday should run the main weekday services"
    assert not (main_weekday & holiday), "Main weekday services must be removed on Memorial Day"
    assert any(s.endswith("-Sunday") for s in holiday), "Sunday services should be added"
    # Memorial Day runs the same number of trips as a normal Sunday
    assert feed.get_trip_count(datetime(2026, 5, 25)) == feed.get_trip_count(datetime(2026, 5, 24))


@pytest.mark.parametrize("date,expected", [
    ("2026-03-26", "2025-12-30"),
    ("2026-03-27", "2026-03-27"),
    ("2026-04-10", "2026-03-27"),
    ("2026-04-11", "2026-03-27"),  # 9 Apr version has only 2 trips on this Saturday
    ("2026-04-12", "2026-04-09"),
    ("2026-06-26", "2026-04-09"),
    ("2026-06-27", "2026-04-09"),  # 24 Jun version has only 2 trips on this Saturday
    ("2026-06-28", "2026-06-24"),
    ("2026-09-04", "2026-06-24"),
    ("2026-09-05", "2026-06-24"),  # 3 Sep version has only 2 trips on this Saturday
    ("2026-09-06", "2026-09-03"),
])
def test_step_8_switchover_dates(date_info, date, expected):
    assert date_info[date]["snapshot_id"] == expected
    assert date_info[date]["full_service"]


def test_step_8_every_date_assigned_and_only_3_jan_partial(date_info):
    assert len(date_info) == 271
    assert all(v["snapshot_id"] in USABLE_SNAPSHOTS for v in date_info.values())
    partial = [d for d, v in date_info.items() if not v["full_service"]]
    assert partial == ["2026-01-03"]


def test_step_9_schedule_hourly_output():
    path = ROOT / "data" / "processed" / "schedule_hourly.parquet"
    df = pd.read_parquet(path)
    assert list(df.columns) == ["route", "date", "hour", "trips_starting", "trips_running", "snapshot_id"]
    assert len(df) == 41 * 24 * 271
    assert not df.duplicated(["route", "date", "hour"]).any()
    assert (df.trips_starting >= 0).all() and (df.trips_running >= df.trips_starting).all()
    # after-midnight carry-over: early hours of a normal Tuesday have trips running
    tue = df[(df.date == "2026-05-19") & (df.hour.isin([0, 1]))]
    assert tue.trips_running.sum() > 0


def test_dst_night_8_march_hour_2_has_zero_trips():
    path = ROOT / "data" / "processed" / "schedule_hourly.parquet"
    df = pd.read_parquet(path)
    dst_h2 = df[(df.date == "2026-03-08") & (df.hour == 2)]
    assert len(dst_h2) == 41
    assert (dst_h2.trips_starting == 0).all(), "DST hour 2 must have 0 trips starting"
    assert (dst_h2.trips_running == 0).all(), "DST hour 2 must have 0 trips running"


def test_memorial_day_exact_sunday_equivalence(feeds):
    feed = feeds["2026-04-09"]
    d_mem = datetime(2026, 5, 25)
    d_sun24 = datetime(2026, 5, 24)
    d_sun31 = datetime(2026, 5, 31)

    c_mem = feed.get_trip_count(d_mem)
    c_sun24 = feed.get_trip_count(d_sun24)
    c_sun31 = feed.get_trip_count(d_sun31)

    assert c_mem == c_sun24 == c_sun31 == 6231, "Memorial Day must match Sunday trip count exactly"


def test_boundary_saturdays_audit(date_info):
    def latest_downloaded(d):
        return [s for s in USABLE_SNAPSHOTS if s <= d][-1]

    mismatches = [
        d for d, v in date_info.items()
        if v["snapshot_id"] != latest_downloaded(d)
    ]
    # Exactly 10 dates: 3 boundary Saturdays + 7 advance publication weekdays
    assert len(mismatches) == 10
    boundary_sats = [d for d in mismatches if pd.to_datetime(d).day_name() == "Saturday"]
    assert sorted(boundary_sats) == ["2026-04-11", "2026-06-27", "2026-09-05"]

    # Verify 0 Sundays and 0 holidays misfired
    for d, v in date_info.items():
        dt = pd.to_datetime(d)
        if dt.day_name() == "Sunday" or d in ["2026-01-19", "2026-02-16", "2026-05-25", "2026-06-19", "2026-07-03", "2026-07-04", "2026-09-07"]:
            assert v["snapshot_id"] == latest_downloaded(d), f"Sunday/holiday {d} must pick active version"


# ---------- Steps 10, 11, 12, 13 tests ----------

def test_step_10_route_crosswalk():
    path = ROOT / "reports" / "route_crosswalk.csv"
    assert path.exists(), "route_crosswalk.csv must exist"
    df = pd.read_csv(path)
    assert len(df) == 46, "Should evaluate exactly 46 route codes"
    matched = df[df["match_status"] == "matched"]
    assert len(matched) == 41, "Exactly 41 routes must match between ridership and GTFS"
    unmatched_r = df[df["match_status"] == "ridership_only_unmatched"]
    assert sorted(unmatched_r["route_code"]) == ["M100", "M14A", "M14D", "M90", "M99"]
    unmatched_g = df[df["match_status"] == "gtfs_only_unmatched"]
    assert len(unmatched_g) == 0, "Zero GTFS routes should be unmatched"
    # Select Bus Service (+) naming convention check
    sbs = df[df["service_type"] == "Select Bus Service (+)"]
    assert len(sbs) == 9
    assert all("+" in c for c in sbs["route_code"])


def test_step_11_12_matched_hourly_output():
    path = ROOT / "data" / "processed" / "matched_hourly.parquet"
    df = pd.read_parquet(path)
    expected_cols = [
        "route", "date", "hour", "month", "day_of_week", "is_weekend",
        "is_public_holiday", "holiday_schedule", "is_storm", "is_outlier", "time_band",
        "ridership", "transfers", "trips_starting", "trips_running",
        "riders_per_trip", "snapshot_id"
    ]
    assert list(df.columns) == expected_cols
    # Step 11: hours with neither dropped + artifact exclusions (4 Jan 0-4, 9 Jan 22-23, 28 Mar 1-4, 16 Aug 21-22) -> 233,227 rows
    assert len(df) == 233227
    assert not df.duplicated(["route", "date", "hour"]).any()
    # Step 11: verify artifact blocks are completely excluded
    jan4_early = df[(df["date"] == "2026-01-04") & (df["hour"] < 5)]
    assert len(jan4_early) == 0, "4 Jan hours 0-4 must be excluded"
    jan9_drop = df[(df["date"] == "2026-01-09") & (df["hour"].isin([22, 23]))]
    assert len(jan9_drop) == 0, "9 Jan hours 22-23 must be excluded"
    mar28_outage = df[(df["date"] == "2026-03-28") & (df["hour"].isin([1, 2, 3, 4]))]
    assert len(mar28_outage) == 0, "28 Mar hours 1-4 must be excluded"
    aug16_outage = df[(df["date"] == "2026-08-16") & (df["hour"].isin([21, 22]))]
    assert len(aug16_outage) == 0, "16 Aug hours 21-22 must be excluded"
    # Step 11: no rows where both trips_running == 0 and ridership == 0
    neither = (df["trips_running"] == 0) & (df["ridership"] == 0)
    assert not neither.any(), "Hours with neither must be dropped"
    # Step 11: riders_per_trip = ridership / trips_running only where trips_running > 0
    with_trips = df[df["trips_running"] > 0]
    expected_rpt = (with_trips["ridership"] / with_trips["trips_running"]).round(4)
    assert np.allclose(with_trips["riders_per_trip"], expected_rpt, equal_nan=True)
    # Maximum riders per trip should be ~64.86 on M35 (not the artificial 104.0 on M15)
    max_row = df.loc[df["riders_per_trip"].idxmax()]
    assert max_row["route"] == "M35"
    assert round(max_row["riders_per_trip"], 2) == 64.86
    # Verify M35 19 Sept surge is flagged with is_outlier across full 6-hour window (14:00 to 19:00)
    m35_surge = df[(df["route"] == "M35") & (df["date"] == "2026-09-19") & (df["hour"].isin([14, 15, 16, 17, 18, 19]))]
    assert (m35_surge["is_outlier"] == True).all()
    assert df["is_outlier"].sum() == 6
    # Step 12: all 5 time bands exist
    expected_bands = {"early_morning", "morning_peak", "midday", "evening_peak", "night"}
    assert set(df["time_band"].unique()) == expected_bands


def test_step_13_route_profiles_output():
    path = ROOT / "data" / "processed" / "route_profiles.parquet"
    df = pd.read_parquet(path)
    assert len(df) == 41
    required_cols = [
        "route_id", "route_short_name", "route_long_name", "service_type",
        "stop_count", "route_length_km", "route_length_mi",
        "trips_per_weekday", "trips_per_saturday", "trips_per_sunday",
        "first_departure", "last_departure", "morning_peak_avg_gap_min",
        "avg_trip_duration_min", "avg_scheduled_speed_kmh",
        "avg_daily_riders", "peak_riders_per_trip"
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required column {col} in route profiles"

    assert (df.route_length_km > 0).all()
    assert (df.stop_count > 0).all()
    assert (df.trips_per_weekday > 0).all()
    assert (df.avg_daily_riders > 0).all()
    assert (df.avg_scheduled_speed_kmh > 0).all()

    # M98 should have 0 Saturday and Sunday trips
    m98 = df[df.route_id == "M98"].iloc[0]
    assert m98["trips_per_saturday"] == 0
    assert m98["trips_per_sunday"] == 0
    assert m98["trips_per_weekday"] > 0


