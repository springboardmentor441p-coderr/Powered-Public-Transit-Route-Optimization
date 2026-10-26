"""
Milestone 1 — Steps 11 & 12: Join, Filter, Calculate Riders Per Trip & Add Time Features

Step 11:
  - Joins ridership and schedule on [route, date, hour] for the study window (2026-01-04 to 2026-09-30, excluding 10-15 Jan).
  - riders_per_trip = ridership / trips_running, only where trips_running > 0
  - Hours with riders but no scheduled trips (trips_running == 0 & ridership > 0): counted and kept.
  - Hours with trips but zero riders (trips_running > 0 & ridership == 0): real, kept.
  - Hours with neither (trips_running == 0 & ridership == 0): no service, DROPPED.
  This table is the "passengers per route per hour" the brief asks for.

Step 12:
  - Adds time features:
    * hour (0-23)
    * month (1 to 9)
    * day_of_week (Monday to Sunday)
    * is_weekend (True for Saturday and Sunday)
    * is_public_holiday (True for legal public holidays)
    * holiday_schedule (True when timetable ran a special holiday exception schedule)
    * is_storm (True on days of severe snowstorm/blizzard disruptions)
    * time_band (early_morning, morning_peak, midday, evening_peak, night)
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RIDERSHIP_PATH = ROOT / "data" / "processed" / "ridership_hourly_clean.parquet"
SCHEDULE_PATH = ROOT / "data" / "processed" / "schedule_hourly.parquet"
OUT_PATH = ROOT / "data" / "processed" / "matched_hourly.parquet"

WINDOW_START = "2026-01-04"
WINDOW_END = "2026-09-30"

MISSING_RIDERSHIP_DATES = {
    f"2026-01-{d:02d}" for d in range(10, 16)
}

# Legal public holidays in 2026 study window
PUBLIC_HOLIDAYS = {
    "2026-01-19": "Martin Luther King Jr. Day",
    "2026-02-16": "Presidents' Day",
    "2026-05-25": "Memorial Day",
    "2026-06-19": "Juneteenth",
    "2026-07-03": "Independence Day (Observed)",
    "2026-07-04": "Independence Day",
    "2026-09-07": "Labor Day",
}

# Dates where GTFS timetable operated a special holiday/reduced schedule
# Note: On Juneteenth (19 Jun) and Saturday 4 Jul, the MTA ran normal weekday/Saturday schedules.
HOLIDAY_SCHEDULE_DATES = {
    "2026-01-19": "MLK Day (Modified Weekday H6)",
    "2026-02-16": "Presidents' Day (Saturday Schedule on Monday)",
    "2026-05-25": "Memorial Day (Sunday Schedule on Monday)",
    "2026-07-03": "Independence Day Observed (Saturday Schedule on Friday)",
    "2026-09-07": "Labor Day (Sunday Schedule on Monday)",
}

STORM_DATES = {
    "2026-01-25": "Snowstorm",
    "2026-01-26": "Snowstorm recovery",
    "2026-02-22": "Blizzard",
    "2026-02-23": "Blizzard",
    "2026-02-24": "Blizzard recovery",
}


def assign_time_band(hour: int) -> str:
    """Step 12: Categorize hour into 5 standard transit time bands."""
    if 4 <= hour <= 6:
        return "early_morning"
    elif 7 <= hour <= 9:
        return "morning_peak"
    elif 10 <= hour <= 15:
        return "midday"
    elif 16 <= hour <= 18:
        return "evening_peak"
    else:  # 19-23 and 0-3
        return "night"


def find_outage_hours_relative(joined_df: pd.DataFrame, threshold: float = 0.20) -> list:
    """
    Step 11 Outage Detection Rule:
    For each hour, compare network total ridership with the median for the same weekday
    and hour over the surrounding 3 weeks (+/- 21 days).
    Excludes documented weather storm days and public holidays to avoid flagging valid low-ridership conditions.
    Flags hours where network ridership is below the threshold share of the baseline median.
    """
    hourly_net = joined_df.groupby(["date", "hour"])["ridership"].sum().reset_index()
    hourly_trips = joined_df.groupby(["date", "hour"])["trips_running"].sum().reset_index()
    net = pd.merge(hourly_net, hourly_trips, on=["date", "hour"])
    net["dt"] = pd.to_datetime(net["date"])
    net["dow"] = net["dt"].dt.day_name()
    net["is_storm"] = net["date"].isin(STORM_DATES)
    net["is_holiday"] = net["date"].isin(PUBLIC_HOLIDAYS)

    baseline_pool = net[~net["is_storm"] & ~net["is_holiday"]].copy()

    flagged = []
    for idx, row in net.iterrows():
        if row["is_storm"] or row["is_holiday"] or row["trips_running"] == 0:
            continue
        surrounding = baseline_pool[
            (baseline_pool["dow"] == row["dow"])
            & (baseline_pool["hour"] == row["hour"])
            & (baseline_pool["dt"] >= row["dt"] - pd.Timedelta(days=21))
            & (baseline_pool["dt"] <= row["dt"] + pd.Timedelta(days=21))
            & (baseline_pool["date"] != row["date"])
        ]
        if len(surrounding) > 0:
            med = surrounding["ridership"].median()
            if med > 0:
                ratio = row["ridership"] / med
                if ratio < threshold:
                    flagged.append((row["date"], row["hour"], row["dow"], row["ridership"], med, ratio))
    return flagged


def build_matched_hourly():
    print("--- Milestone 1 Steps 11 & 12: Building Matched Hourly Table ---")
    print(f"Reading ridership: {RIDERSHIP_PATH.relative_to(ROOT)}")
    r_df = pd.read_parquet(RIDERSHIP_PATH)
    r_df["date"] = r_df["date"].astype(str)

    print(f"Reading schedule: {SCHEDULE_PATH.relative_to(ROOT)}")
    s_df = pd.read_parquet(SCHEDULE_PATH)
    s_df["date"] = s_df["date"].astype(str)

    # Filter both to study window [2026-01-04, 2026-09-30] excluding 10-15 Jan
    all_dates = sorted(s_df["date"].unique())
    study_dates = [
        d for d in all_dates
        if WINDOW_START <= d <= WINDOW_END and d not in MISSING_RIDERSHIP_DATES
    ]
    print(f"Study window dates count: {len(study_dates)} days ({WINDOW_START} to {WINDOW_END}, 6 missing days excluded)")

    r_sub = r_df[r_df["date"].isin(study_dates)]
    s_sub = s_df[s_df["date"].isin(study_dates)]

    # Join on route, date, hour
    print(f"Joining {len(r_sub):,} ridership rows with {len(s_sub):,} schedule rows...")
    joined = pd.merge(r_sub, s_sub, on=["route", "date", "hour"], how="inner")
    print(f"Total raw joined rows: {len(joined):,}")

    # Run the relative drop rule to identify feed outage hours
    flagged_outages = find_outage_hours_relative(joined, threshold=0.20)
    print(f"\n[Outage Detection Rule] Evaluated against 3-week median (< 20% threshold): flagged {len(flagged_outages)} hours:")
    for f in flagged_outages:
        print(f"  - {f[0]} Hour {f[1]:02d} ({f[2]}): {f[3]:,} riders vs {f[4]:.1f} median ({f[5]*100:.1f}%)")

    # Exclude known archive boundary artifacts and detected collection outages:
    # 1. 2026-01-04 00:00-04:59: Saturday 3 Jan carry-over trips past midnight missing from GTFS archive
    # 2. 2026-01-09 22:00-23:59: Feed collapse preceding 10-15 Jan blackout (< 10% of median)
    # 3. 2026-03-28 01:00-04:59: Automated collection outage (2.8% to 6.9% of median)
    # 4. 2026-08-16 21:00-22:59: Automated collection outage (0.99% to 16.8% of median)
    excluded_blocks = [
        ("2026-01-04", [0, 1, 2, 3, 4], "Missing Saturday 3 Jan GTFS carry-over trips"),
        ("2026-01-09", [22, 23], "Feed collapse preceding 10-15 Jan blackout"),
        ("2026-03-28", [1, 2, 3, 4], "Automated ridership collection outage"),
        ("2026-08-16", [21, 22], "Automated ridership collection outage"),
    ]
    for ex_date, ex_hours, reason in excluded_blocks:
        ex_mask = (joined["date"] == ex_date) & (joined["hour"].isin(ex_hours))
        ex_count = ex_mask.sum()
        joined = joined[~ex_mask].copy()
        print(f"Excluded {ex_date} hours {ex_hours} ({reason}): dropped {ex_count} route-hours")

    print(f"Total joined rows after artifact & outage exclusions: {len(joined):,}")

    # Count service states before dropping
    neither_mask = (joined["trips_running"] == 0) & (joined["ridership"] == 0)
    trips_zero_riders_mask = (joined["trips_running"] > 0) & (joined["ridership"] == 0)
    riders_no_trips_mask = (joined["trips_running"] == 0) & (joined["ridership"] > 0)
    normal_service_mask = (joined["trips_running"] > 0) & (joined["ridership"] > 0)

    count_neither = neither_mask.sum()
    count_trips_zero_riders = trips_zero_riders_mask.sum()
    count_riders_no_trips = riders_no_trips_mask.sum()
    count_normal = normal_service_mask.sum()

    print("\n--- Step 11 Analysis: Service State Counts ---")
    print(f"  1. Hours with trips and riders:                   {count_normal:>7,} ({count_normal/len(joined)*100:5.2f}%) -> KEPT")
    print(f"  2. Hours with trips but zero riders:             {count_trips_zero_riders:>7,} ({count_trips_zero_riders/len(joined)*100:5.2f}%) -> KEPT (real)")
    print(f"  3. Hours with riders but no scheduled trips:     {count_riders_no_trips:>7,} ({count_riders_no_trips/len(joined)*100:5.2f}%) -> KEPT (late-night timing edges)")
    print(f"  4. Hours with neither (no service, no riders):   {count_neither:>7,} ({count_neither/len(joined)*100:5.2f}%) -> DROPPED (no service)")

    # Step 11 Rule: Drop hours with neither
    matched = joined[~neither_mask].copy()
    print(f"\nRows after dropping 'neither' (no service): {len(matched):,}")

    # Calculate riders_per_trip = ridership / trips_running, only where trips_running > 0
    matched["riders_per_trip"] = np.where(
        matched["trips_running"] > 0,
        (matched["ridership"] / matched["trips_running"]).round(4),
        np.nan,
    )

    # Step 12: Add time features
    dt_series = pd.to_datetime(matched["date"])
    matched["hour"] = matched["hour"].astype("int8")
    matched["month"] = dt_series.dt.month.astype("int8")
    matched["day_of_week"] = dt_series.dt.day_name()
    matched["is_weekend"] = matched["day_of_week"].isin(["Saturday", "Sunday"])
    matched["is_public_holiday"] = matched["date"].isin(PUBLIC_HOLIDAYS)
    matched["holiday_schedule"] = matched["date"].isin(HOLIDAY_SCHEDULE_DATES)
    matched["is_storm"] = matched["date"].isin(STORM_DATES)
    # Tag M35 afternoon surge on Saturday 19 September (multi-hour operational surge from 14:00 to 19:00)
    matched["is_outlier"] = (
        (matched["route"] == "M35")
        & (matched["date"] == "2026-09-19")
        & (matched["hour"].isin([14, 15, 16, 17, 18, 19]))
    )
    matched["time_band"] = matched["hour"].apply(assign_time_band)

    # Reorder columns cleanly
    col_order = [
        "route",
        "date",
        "hour",
        "month",
        "day_of_week",
        "is_weekend",
        "is_public_holiday",
        "holiday_schedule",
        "is_storm",
        "is_outlier",
        "time_band",
        "ridership",
        "transfers",
        "trips_starting",
        "trips_running",
        "riders_per_trip",
        "snapshot_id",
    ]
    matched = matched[col_order]

    # Save to parquet
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    matched.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved Step 11 & 12 matched hourly table -> {OUT_PATH.relative_to(ROOT)} ({OUT_PATH.stat().st_size:,} bytes)")

    return matched


if __name__ == "__main__":
    build_matched_hourly()
