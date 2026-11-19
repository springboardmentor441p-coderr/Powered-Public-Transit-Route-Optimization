import json
import os
import duckdb
import pandas as pd

MANIFEST_PATH = "data/raw/source_manifest.json"
OUT_DIR = "data/processed/v1"

def validate_ridership(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype={"route": str, "date": str, "daytype": str, "rides": str})
    df["route"] = df["route"].str.strip()
    df["daytype"] = df["daytype"].str.strip()
    df["service_date"] = pd.to_datetime(df["date"], format="%m/%d/%Y").dt.date
    df["rides"] = df["rides"].str.replace(",", "", regex=False).astype(int)

    # Validate constraints
    assert (df["rides"] >= 0).all(), "Negative rides detected!"
    assert df["daytype"].isin(["W", "A", "U"]).all(), "Invalid daytype detected!"

    # Remove exact duplicates, quarantine conflicting duplicates
    df = df.drop_duplicates(subset=["route", "service_date", "daytype", "rides"])
    dups = df[df.duplicated(subset=["route", "service_date"], keep=False)]
    if not dups.empty:
        dups.to_csv(os.path.join(OUT_DIR, "quarantined_ridership_conflicts.csv"), index=False)
        df = df.drop_duplicates(subset=["route", "service_date"], keep=False)

    return df[["route", "service_date", "daytype", "rides"]].sort_values(["route", "service_date"])

def expand_gtfs_snapshot(extracted_dir: str, snapshot_id: str, capture_date: str) -> pd.DataFrame:
    con = duckdb.connect()
    # Convert GTFS HH:MM:SS (including >24:00:00) into elapsed seconds
    query = f"""
    WITH routes AS (
        SELECT TRIM(CAST(route_id AS VARCHAR)) AS route_id,
               TRIM(CAST(route_short_name AS VARCHAR)) AS route,
               CAST(route_type AS INTEGER) AS route_type
        FROM read_csv_auto('{extracted_dir}/routes.txt', all_varchar=true)
        WHERE CAST(route_type AS INTEGER) = 3
    ),
    trips AS (
        SELECT TRIM(CAST(trip_id AS VARCHAR)) AS trip_id,
               TRIM(CAST(route_id AS VARCHAR)) AS route_id,
               TRIM(CAST(service_id AS VARCHAR)) AS service_id
        FROM read_csv_auto('{extracted_dir}/trips.txt', all_varchar=true)
    ),
    trip_durations AS (
        SELECT
            TRIM(CAST(trip_id AS VARCHAR)) AS trip_id,
            MIN(
                CAST(split_part(departure_time, ':', 1) AS INTEGER) * 3600 +
                CAST(split_part(departure_time, ':', 2) AS INTEGER) * 60 +
                CAST(split_part(departure_time, ':', 3) AS INTEGER)
            ) AS first_dep_sec,
            MAX(
                CAST(split_part(arrival_time, ':', 1) AS INTEGER) * 3600 +
                CAST(split_part(arrival_time, ':', 2) AS INTEGER) * 60 +
                CAST(split_part(arrival_time, ':', 3) AS INTEGER)
            ) AS last_arr_sec
        FROM read_csv_auto('{extracted_dir}/stop_times.txt', all_varchar=true)
        WHERE arrival_time IS NOT NULL AND departure_time IS NOT NULL
        GROUP BY 1
    ),
    cal_bounds AS (
        SELECT MIN(strptime(start_date, '%Y%m%d')::DATE) AS min_d,
               MAX(strptime(end_date, '%Y%m%d')::DATE) AS max_d
        FROM read_csv_auto('{extracted_dir}/calendar.txt', all_varchar=true)
    ),
    date_spine AS (
        SELECT unnest(generate_series(min_d, max_d, INTERVAL 1 DAY))::DATE AS service_date
        FROM cal_bounds
    ),
    base_cal AS (
        SELECT d.service_date, TRIM(CAST(c.service_id AS VARCHAR)) AS service_id
        FROM date_spine d
        JOIN read_csv_auto('{extracted_dir}/calendar.txt', all_varchar=true) c
          ON d.service_date BETWEEN strptime(c.start_date, '%Y%m%d')::DATE AND strptime(c.end_date, '%Y%m%d')::DATE
        WHERE (isodow(d.service_date) = 1 AND c.monday = '1')
           OR (isodow(d.service_date) = 2 AND c.tuesday = '1')
           OR (isodow(d.service_date) = 3 AND c.wednesday = '1')
           OR (isodow(d.service_date) = 4 AND c.thursday = '1')
           OR (isodow(d.service_date) = 5 AND c.friday = '1')
           OR (isodow(d.service_date) = 6 AND c.saturday = '1')
           OR (isodow(d.service_date) = 7 AND c.sunday = '1')
    ),
    cal_dates AS (
        SELECT strptime(date, '%Y%m%d')::DATE AS service_date,
               TRIM(CAST(service_id AS VARCHAR)) AS service_id,
               CAST(exception_type AS INTEGER) AS exception_type
        FROM read_csv_auto('{extracted_dir}/calendar_dates.txt', all_varchar=true)
    ),
    active_services AS (
        SELECT service_date, service_id FROM base_cal
        EXCEPT
        SELECT service_date, service_id FROM cal_dates WHERE exception_type = 2
        UNION
        SELECT service_date, service_id FROM cal_dates WHERE exception_type = 1
    )
    SELECT
        r.route,
        a.service_date,
        COUNT(DISTINCT t.trip_id) AS scheduled_trips,
        CASE
            WHEN COUNT(td.trip_id) = COUNT(DISTINCT t.trip_id)
                 AND MIN(td.last_arr_sec - td.first_dep_sec) >= 0
            THEN SUM(td.last_arr_sec - td.first_dep_sec) / 3600.0
            ELSE NULL
        END AS scheduled_service_hours,
        (COUNT(td.trip_id) = COUNT(DISTINCT t.trip_id)) AS duration_complete,
        '{snapshot_id}' AS source_snapshot,
        DATE '{capture_date}' AS archive_available_from
    FROM active_services a
    JOIN trips t ON a.service_id = t.service_id
    JOIN routes r ON t.route_id = r.route_id
    LEFT JOIN trip_durations td ON t.trip_id = td.trip_id
    GROUP BY r.route, a.service_date
    """
    df = con.execute(query).df()
    df["service_date"] = pd.to_datetime(df["service_date"]).dt.date
    return df

def run():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    # 1. Validate Ridership
    rides_df = validate_ridership(manifest["ridership"]["local_path"])
    rides_df.to_csv(os.path.join(OUT_DIR, "validated_daily_ridership.csv"), index=False)

    # 2. Expand all GTFS snapshots
    all_schedules = []
    for item in manifest["gtfs"]:
        print(f"Expanding schedule snapshot {item['snapshot_id']}...")
        sched_df = expand_gtfs_snapshot(item["extracted_dir"], item["snapshot_id"], item["capture_date"])
        all_schedules.append(sched_df)
    combined_sched = pd.concat(all_schedules, ignore_index=True)

    # 3. Select latest snapshot captured on or before service_date D (Section 9.6.3)
    combined_sched = combined_sched[combined_sched["archive_available_from"] <= combined_sched["service_date"]]
    latest_snap_per_date = (
        combined_sched[["service_date", "archive_available_from", "source_snapshot"]]
        .drop_duplicates()
        .sort_values(["service_date", "archive_available_from"])
        .groupby("service_date", as_index=False)
        .last()
    )
    selected_sched = combined_sched.merge(
        latest_snap_per_date, on=["service_date", "archive_available_from", "source_snapshot"], how="inner"
    )
    selected_sched.to_csv(os.path.join(OUT_DIR, "expanded_scheduled_route_day_service.csv"), index=False)

    # 4. Exact-Date Reconciliation over the matched window (2025-11-23 to 2026-07-31)
    min_sched_d = selected_sched["service_date"].min()
    max_rides_d = rides_df["service_date"].max()
    window_rides = rides_df[(rides_df["service_date"] >= min_sched_d) & (rides_df["service_date"] <= max_rides_d)]
    window_sched = selected_sched[(selected_sched["service_date"] >= min_sched_d) & (selected_sched["service_date"] <= max_rides_d)]

    merged = pd.merge(window_rides, window_sched, on=["route", "service_date"], how="outer", indicator=True)

    matched = merged[merged["_merge"] == "both"].drop(columns=["_merge"]).copy()
    matched["rides_per_scheduled_trip"] = matched["rides"] / matched["scheduled_trips"]
    matched["rides_per_scheduled_hour"] = matched["rides"] / matched["scheduled_service_hours"]
    matched.to_csv(os.path.join(OUT_DIR, "expanded_matched_utilization.csv"), index=False)

    rides_no_sched = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])
    rides_no_sched.to_csv(os.path.join(OUT_DIR, "expanded_ridership_without_schedule.csv"), index=False)

    sched_no_rides = merged[merged["_merge"] == "right_only"].drop(columns=["_merge"])
    sched_no_rides.to_csv(os.path.join(OUT_DIR, "expanded_schedule_without_ridership.csv"), index=False)

    print(f"Reconciliation complete: Matched={len(matched)}, Rides without schedule={len(rides_no_sched)}, Schedule without rides={len(sched_no_rides)}")

if __name__ == "__main__":
    run()