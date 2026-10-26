"""
Milestone 1 — Step 13: Build Route Profiles (route_profiles.parquet / route_profiles.csv)

Constructs comprehensive route profiles for all 41 Manhattan bus routes using a typical weekday
(Wednesday 13 May 2026 under the Spring GTFS snapshot 2026-04-09):
  - Number of stops (unique stops served on typical weekday)
  - Route length in km (sum of Haversine distances along shapes.txt, using the most common shape per direction)
  - Trips per weekday and per weekend day (typical weekday, Saturday, and Sunday)
  - First and last departure times (earliest and latest terminal departures across the 24-hour cycle)
  - Average gap between buses in the morning peak (7 to 9 AM), worked out separately for each direction and starting point
  - Average scheduled trip time (duration from first stop departure to final stop arrival) and scheduled speed (km/h)
  - Average daily riders (weekday) and riders per trip at peak (morning peak 7 to 9 AM)
"""

import sys
from pathlib import Path
import zipfile
from datetime import datetime
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.build_schedule import GTFSFeed

GTFS_PATH = ROOT / "data" / "raw" / "gtfs" / "manhattan" / "2026-04-09" / "original.zip"
MATCHED_PATH = ROOT / "data" / "processed" / "matched_hourly.parquet"
OUT_PARQUET = ROOT / "data" / "processed" / "route_profiles.parquet"
OUT_CSV = ROOT / "reports" / "route_profiles.csv"

TYPICAL_WEEKDAY = datetime(2026, 5, 13)   # Wednesday
TYPICAL_SATURDAY = datetime(2026, 5, 16)  # Saturday
TYPICAL_SUNDAY = datetime(2026, 5, 17)    # Sunday


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0  # Earth radius in km
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2.0) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def parse_time_to_seconds(time_str: str) -> int:
    h, m, s = [int(p) for p in time_str.split(":")]
    return h * 3600 + m * 60 + s


def format_seconds_to_hhmm(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h:02d}:{m:02d}"


def build_route_profiles():
    print("--- Milestone 1 Step 13: Building Route Profiles ---")
    print(f"Reading GTFS snapshot: {GTFS_PATH.relative_to(ROOT)}")
    zf = zipfile.ZipFile(GTFS_PATH)

    routes = pd.read_csv(zf.open("routes.txt"), dtype=str)
    trips = pd.read_csv(zf.open("trips.txt"), dtype=str)
    shapes = pd.read_csv(
        zf.open("shapes.txt"),
        dtype={"shape_pt_lat": float, "shape_pt_lon": float, "shape_pt_sequence": int},
    )
    st = pd.read_csv(
        zf.open("stop_times.txt"),
        dtype={"trip_id": str, "stop_id": str, "departure_time": str, "arrival_time": str, "stop_sequence": int},
    )

    # Filter to Manhattan routes
    m_routes = set(routes[routes["route_id"].str.startswith("M")]["route_id"])
    trips = trips[trips["route_id"].isin(m_routes)].copy()

    # 1. Compute shape lengths
    print("Computing shape lengths along shapes.txt using Haversine formula...")
    shapes = shapes.sort_values(["shape_id", "shape_pt_sequence"])
    shapes["lat_prev"] = shapes.groupby("shape_id")["shape_pt_lat"].shift(1)
    shapes["lon_prev"] = shapes.groupby("shape_id")["shape_pt_lon"].shift(1)
    shapes["dist_km"] = haversine(
        shapes["lat_prev"], shapes["lon_prev"], shapes["shape_pt_lat"], shapes["shape_pt_lon"]
    ).fillna(0)
    shape_len = shapes.groupby("shape_id")["dist_km"].sum().to_dict()

    # 2. Extract active services on typical weekday, Saturday, and Sunday
    feed = GTFSFeed("2026-04-09")
    wk_services = feed.get_active_services(TYPICAL_WEEKDAY)
    sat_services = feed.get_active_services(TYPICAL_SATURDAY)
    sun_services = feed.get_active_services(TYPICAL_SUNDAY)

    wk_trips = trips[trips["service_id"].isin(wk_services)].copy()
    sat_trips = trips[trips["service_id"].isin(sat_services)].copy()
    sun_trips = trips[trips["service_id"].isin(sun_services)].copy()

    print(f"Typical weekday trips: {len(wk_trips):,} across {wk_trips['route_id'].nunique()} routes")
    print(f"Typical Saturday trips: {len(sat_trips):,} across {sat_trips['route_id'].nunique()} routes")
    print(f"Typical Sunday trips:   {len(sun_trips):,} across {sun_trips['route_id'].nunique()} routes")

    # 3. Span and terminal stop info for typical weekday
    st = st.sort_values(["trip_id", "stop_sequence"])
    st_first = st.groupby("trip_id").first().reset_index()
    st_last = st.groupby("trip_id").last().reset_index()

    st_spans = pd.merge(
        st_first[["trip_id", "departure_time", "stop_id"]].rename(
            columns={"departure_time": "first_dep", "stop_id": "start_stop"}
        ),
        st_last[["trip_id", "arrival_time", "stop_id"]].rename(
            columns={"arrival_time": "last_arr", "stop_id": "end_stop"}
        ),
        on="trip_id",
    )
    wk_trips = pd.merge(wk_trips, st_spans, on="trip_id")
    wk_trips["dep_sec"] = wk_trips["first_dep"].apply(parse_time_to_seconds)
    wk_trips["arr_sec"] = wk_trips["last_arr"].apply(parse_time_to_seconds)
    wk_trips["duration_min"] = (wk_trips["arr_sec"] - wk_trips["dep_sec"]) / 60.0
    wk_trips["shape_len_km"] = wk_trips["shape_id"].map(shape_len)

    # Unique stops on typical weekday per route
    wk_trip_ids = set(wk_trips["trip_id"])
    st_wk = st[st["trip_id"].isin(wk_trip_ids)]
    wk_route_stops = pd.merge(
        wk_trips[["trip_id", "route_id"]], st_wk[["trip_id", "stop_id"]], on="trip_id"
    ).groupby("route_id")["stop_id"].nunique().to_dict()

    # 4. Load matched ridership table for empirical ridership metrics
    print(f"Loading matched table: {MATCHED_PATH.relative_to(ROOT)}")
    m_df = pd.read_parquet(MATCHED_PATH)

    # Normal weekdays in matched data (exclude storms and holidays)
    m_normal_wk = m_df[(~m_df["is_weekend"]) & (~m_df["is_public_holiday"]) & (~m_df["holiday_schedule"]) & (~m_df["is_storm"])]
    num_normal_wk_dates = m_normal_wk["date"].nunique()

    # Average weekday daily ridership per route
    avg_wk_riders = (m_normal_wk.groupby("route")["ridership"].sum() / num_normal_wk_dates).to_dict()

    # Morning peak riders per trip (07:00-09:59) on normal weekdays
    m_peak_wk = m_normal_wk[m_normal_wk["time_band"] == "morning_peak"]
    peak_runs = m_peak_wk[m_peak_wk["trips_running"] > 0]
    peak_rpt = peak_runs.groupby("route")["riders_per_trip"].mean().to_dict()

    # Route names metadata
    routes_dict = routes.set_index("route_id").to_dict(orient="index")

    # 5. Build profile row for each route
    all_routes = sorted(wk_trips["route_id"].unique())
    records = []

    for r in all_routes:
        r_trips = wk_trips[wk_trips["route_id"] == r]
        r_sat = sat_trips[sat_trips["route_id"] == r]
        r_sun = sun_trips[sun_trips["route_id"] == r]

        r_meta = routes_dict.get(r, {})
        short_name = r_meta.get("route_short_name", r)
        long_name = r_meta.get("route_long_name", "")
        service_type = "Select Bus Service (+)" if "+" in r else "Local"

        # Unique stops
        stops_count = wk_route_stops.get(r, 0)

        # Most common shape per direction and route length
        dir_shapes = {}
        dir_lengths = {}
        for d in [0, 1]:
            d_t = r_trips[r_trips["direction_id"] == str(d)]
            if not d_t.empty and not d_t["shape_id"].isna().all():
                top_shape = d_t["shape_id"].value_counts().index[0]
                dir_shapes[d] = top_shape
                dir_lengths[d] = shape_len.get(top_shape, np.nan)

        len_dir0 = dir_lengths.get(0, np.nan)
        len_dir1 = dir_lengths.get(1, np.nan)
        available_lens = [l for l in [len_dir0, len_dir1] if pd.notna(l)]
        avg_route_len_km = np.mean(available_lens) if available_lens else np.nan
        avg_route_len_mi = avg_route_len_km * 0.621371 if pd.notna(avg_route_len_km) else np.nan

        # Trips count
        trips_weekday = len(r_trips)
        trips_saturday = len(r_sat)
        trips_sunday = len(r_sun)

        # First and last departure
        min_dep_sec = r_trips["dep_sec"].min()
        max_dep_sec = r_trips["dep_sec"].max()
        dep_hours = set(r_trips["first_dep"].apply(lambda t: int(t.split(":")[0]) % 24))
        is_24h = (len(dep_hours) == 24) or (min_dep_sec <= 3600 and max_dep_sec >= 24 * 3600)

        if is_24h:
            first_dep_str = "24 hours"
            last_dep_str = "24 hours"
        else:
            first_dep_str = format_seconds_to_hhmm(min_dep_sec)
            last_dep_str = format_seconds_to_hhmm(max_dep_sec)

        # Morning peak (7 to 9 AM) gaps worked out separately for each direction and starting point
        peak_t = r_trips[(r_trips["dep_sec"] >= 7 * 3600) & (r_trips["dep_sec"] <= 9 * 3600)]
        gap_details = []
        all_peak_gaps = []

        for (d_id, start_s), g in peak_t.groupby(["direction_id", "start_stop"]):
            deps = sorted(g["dep_sec"])
            if len(deps) > 1:
                gaps = [(deps[i] - deps[i - 1]) / 60.0 for i in range(1, len(deps))]
                all_peak_gaps.extend(gaps)
                gap_details.append(f"Dir {d_id} (stop {start_s}): {np.mean(gaps):.1f}m ({len(deps)} trips)")
            elif len(deps) == 1:
                gap_details.append(f"Dir {d_id} (stop {start_s}): 1 trip")

        peak_gaps_detail_str = "; ".join(gap_details) if gap_details else "No trips 7-9 AM"
        avg_peak_gap = np.mean(all_peak_gaps) if all_peak_gaps else np.nan

        # Scheduled trip duration and speed
        avg_duration = r_trips["duration_min"].mean()
        # Speed: route length / (duration in hours)
        avg_speed_kmh = (avg_route_len_km / (avg_duration / 60.0)) if avg_duration > 0 and pd.notna(avg_route_len_km) else np.nan

        # Ridership metrics
        daily_riders = avg_wk_riders.get(r, np.nan)
        peak_riders_pt = peak_rpt.get(r, np.nan)

        records.append({
            "route_id": r,
            "route_short_name": short_name,
            "route_long_name": long_name,
            "service_type": service_type,
            "stop_count": stops_count,
            "length_dir0_km": round(len_dir0, 2) if pd.notna(len_dir0) else np.nan,
            "length_dir1_km": round(len_dir1, 2) if pd.notna(len_dir1) else np.nan,
            "route_length_km": round(avg_route_len_km, 2) if pd.notna(avg_route_len_km) else np.nan,
            "route_length_mi": round(avg_route_len_mi, 2) if pd.notna(avg_route_len_mi) else np.nan,
            "trips_per_weekday": trips_weekday,
            "trips_per_saturday": trips_saturday,
            "trips_per_sunday": trips_sunday,
            "first_departure": first_dep_str,
            "last_departure": last_dep_str,
            "morning_peak_avg_gap_min": round(avg_peak_gap, 1) if pd.notna(avg_peak_gap) else np.nan,
            "morning_peak_gaps_detail": peak_gaps_detail_str,
            "avg_trip_duration_min": round(avg_duration, 1),
            "avg_scheduled_speed_kmh": round(avg_speed_kmh, 1) if pd.notna(avg_speed_kmh) else np.nan,
            "avg_daily_riders": int(round(daily_riders)) if pd.notna(daily_riders) else 0,
            "peak_riders_per_trip": round(peak_riders_pt, 2) if pd.notna(peak_riders_pt) else np.nan,
        })

    df_profiles = pd.DataFrame(records)

    # Save to parquet and CSV
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df_profiles.to_parquet(OUT_PARQUET, index=False)
    df_profiles.to_csv(OUT_CSV, index=False)

    print(f"\nSaved Route Profiles -> {OUT_PARQUET.relative_to(ROOT)}")
    print(f"Saved Route Profiles CSV -> {OUT_CSV.relative_to(ROOT)}")

    # Print summary highlights
    print("\nSample Profiles (Top 5 Busiest Routes):")
    sample_cols = [
        "route_id", "route_length_km", "stop_count", "trips_per_weekday",
        "first_departure", "last_departure", "morning_peak_avg_gap_min",
        "avg_scheduled_speed_kmh", "avg_daily_riders", "peak_riders_per_trip"
    ]
    top5 = df_profiles.sort_values("avg_daily_riders", ascending=False).head(5)
    print(top5[sample_cols].to_string(index=False))

    return df_profiles


if __name__ == "__main__":
    build_route_profiles()
