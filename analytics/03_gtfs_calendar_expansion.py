"""
Step 3 & 4: GTFS validation, after-midnight time parsing (>24:00:00),
calendar expansion (weekly masks + exception_type 1/2), and global snapshot selection.
"""
import os
from datetime import date, timedelta
import duckdb
import pandas as pd

PROCESSED_DIR = "data/processed"

def parse_gtfs_seconds(t_str: str):
    if pd.isna(t_str) or not str(t_str).strip():
        return None
    parts = str(t_str).strip().split(":")
    if len(parts) != 3:
        return None
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

def expand_snapshot(snapshot_id: str, retrieved_date: date, zip_path: str) -> pd.DataFrame:
    ext_dir = os.path.join(os.path.dirname(zip_path), "extracted")
    routes = pd.read_csv(os.path.join(ext_dir, "routes.txt"), dtype=str)
    bus_routes = routes[routes["route_type"].str.strip() == "3"][["route_id", "route_short_name"]].copy()
    bus_routes["route_short_name"] = bus_routes["route_short_name"].str.strip()

    trips = pd.read_csv(os.path.join(ext_dir, "trips.txt"), dtype=str)
    bus_trips = trips.merge(bus_routes, on="route_id", how="inner")

    # Use DuckDB to aggregate stop_times endpoints efficiently within bounded memory
    stop_times_path = os.path.join(ext_dir, "stop_times.txt")
    con = duckdb.connect()
    con.execute("SET memory_limit='512MB'")
    endpoints = con.execute(f"""
        SELECT
            trip_id,
            FIRST(departure_time ORDER BY CAST(stop_sequence AS INTEGER)) AS first_dep,
            LAST(arrival_time ORDER BY CAST(stop_sequence AS INTEGER)) AS last_arr
        FROM read_csv_auto('{stop_times_path}', all_varchar=True)
        GROUP BY trip_id
    """).df()
    con.close()

    endpoints["dep_sec"] = endpoints["first_dep"].map(parse_gtfs_seconds)
    endpoints["arr_sec"] = endpoints["last_arr"].map(parse_gtfs_seconds)
    endpoints["duration_sec"] = endpoints["arr_sec"] - endpoints["dep_sec"]
    endpoints.loc[endpoints["duration_sec"] < 0, "duration_sec"] = None

    bus_trips = bus_trips.merge(endpoints[["trip_id", "duration_sec"]], on="trip_id", how="left")

    cal_path = os.path.join(ext_dir, "calendar.txt")
    cal_df = pd.read_csv(cal_path, dtype=str) if os.path.exists(cal_path) else pd.DataFrame()
    exc_path = os.path.join(ext_dir, "calendar_dates.txt")
    exc_df = pd.read_csv(exc_path, dtype=str) if os.path.exists(exc_path) else pd.DataFrame()

    # Determine date bounds from calendar and exceptions
    all_starts, all_ends = [], []
    if not cal_df.empty:
        all_starts.append(pd.to_datetime(cal_df["start_date"], format="%Y%m%d").min().date())
        all_ends.append(pd.to_datetime(cal_df["end_date"], format="%Y%m%d").max().date())
    if not exc_df.empty:
        all_starts.append(pd.to_datetime(exc_df["date"], format="%Y%m%d").min().date())
        all_ends.append(pd.to_datetime(exc_df["date"], format="%Y%m%d").max().date())

    min_d, max_d = min(all_starts), max(all_ends)
    weekday_cols = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    if not cal_df.empty:
        cal_df["start_dt"] = pd.to_datetime(cal_df["start_date"], format="%Y%m%d").dt.date
        cal_df["end_dt"] = pd.to_datetime(cal_df["end_date"], format="%Y%m%d").dt.date
    if not exc_df.empty:
        exc_df["exc_dt"] = pd.to_datetime(exc_df["date"], format="%Y%m%d").dt.date

    daily_records = []
    cur = min_d
    while cur <= max_d:
        wd_col = weekday_cols[cur.weekday()]
        active_svcs = set()
        if not cal_df.empty:
            mask = (cal_df["start_dt"] <= cur) & (cal_df["end_dt"] >= cur) & (cal_df[wd_col].str.strip() == "1")
            active_svcs.update(cal_df.loc[mask, "service_id"].str.strip())
        if not exc_df.empty:
            day_exc = exc_df[exc_df["exc_dt"] == cur]
            removed = set(day_exc.loc[day_exc["exception_type"].str.strip() == "2", "service_id"].str.strip())
            added = set(day_exc.loc[day_exc["exception_type"].str.strip() == "1", "service_id"].str.strip())
            active_svcs = (active_svcs - removed) | added

        if active_svcs:
            day_trips = bus_trips[bus_trips["service_id"].str.strip().isin(active_svcs)]
            if not day_trips.empty:
                grp = day_trips.groupby("route_short_name", as_index=False).agg(
                    scheduled_trips=("trip_id", "nunique"),
                    total_sec=("duration_sec", "sum"),
                    valid_durations=("duration_sec", lambda s: int(s.notna().sum())),
                )
                grp["duration_complete"] = grp["valid_durations"] == grp["scheduled_trips"]
                grp["scheduled_service_hours"] = grp.apply(
                    lambda r: round(r["total_sec"] / 3600.0, 4) if r["duration_complete"] else None,
                    axis=1,
                )
                grp["service_date"] = cur
                grp["source_snapshot"] = snapshot_id
                grp["archive_available_from"] = retrieved_date
                grp.rename(columns={"route_short_name": "route"}, inplace=True)
                daily_records.append(
                    grp[["route", "service_date", "scheduled_trips", "scheduled_service_hours", "duration_complete", "source_snapshot", "archive_available_from"]]
                )
        cur += timedelta(days=1)

    return pd.concat(daily_records, ignore_index=True) if daily_records else pd.DataFrame()

def run():
    reg = pd.read_parquet(os.path.join(PROCESSED_DIR, "source_register.parquet"))
    gtfs_sources = reg[reg["dataset_id"] == "cta_gtfs_schedule"].sort_values("catalog_retrieved_date")

    expanded_list = []
    for _, row in gtfs_sources.iterrows():
        ret_date = date.fromisoformat(str(row["catalog_retrieved_date"]))
        df_snap = expand_snapshot(row["snapshot_id"], ret_date, row["file_path"])
        expanded_list.append(df_snap)

    all_expanded = pd.concat(expanded_list, ignore_index=True)

    # Global per-date snapshot selection: pick latest snapshot retrieved on or before service_date
    eligible = all_expanded[all_expanded["archive_available_from"] <= all_expanded["service_date"]].copy()
    latest_snap_per_date = (
        eligible.groupby("service_date", as_index=False)["archive_available_from"].max()
    )
    selected = eligible.merge(latest_snap_per_date, on=["service_date", "archive_available_from"], how="inner")
    selected = selected.drop_duplicates(subset=["route", "service_date"]).sort_values(["service_date", "route"]).reset_index(drop=True)

    out_path = os.path.join(PROCESSED_DIR, "selected_schedule.parquet")
    selected.to_parquet(out_path, index=False)
    print(f"[03_gtfs_calendar_expansion] Selected {len(selected)} route/date schedule records across {selected['service_date'].nunique()} dates.")

if __name__ == "__main__":
    run()
