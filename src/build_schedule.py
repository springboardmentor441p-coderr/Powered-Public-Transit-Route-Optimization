"""
Steps 7, 8, and 9: Build scheduled trips per route per hour for Manhattan bus routes.

Step 7: Determine active services and trips for each date using calendar.txt + calendar_dates.txt.
Step 8: Select active GTFS snapshot per date using the latest version downloaded on or before
        the date that has full service. Perform overlap accuracy checks on switch-over dates.
Step 9: Convert GTFS times (including spillover >=24h times) to clock datetimes and count
        `trips_starting` and `trips_running` per (route, date, hour).

Outputs:
  data/processed/schedule_hourly.parquet
  reports/gtfs_overlap_comparison.csv
  reports/gtfs_switchover_schedule.csv

Usage:
    python src/build_schedule.py
"""

import zipfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GTFS_DIR = ROOT / "data" / "raw" / "gtfs" / "manhattan"
OUT_FILE = ROOT / "data" / "processed" / "schedule_hourly.parquet"
REPORTS_DIR = ROOT / "reports"

START_DATE = "2026-01-03"
END_DATE = "2026-09-30"

USABLE_SNAPSHOTS = [
    "2025-12-30",
    "2026-03-27",
    "2026-04-09",
    "2026-06-24",
    "2026-09-03",
]


def parse_time_to_seconds(time_str: str) -> int:
    h, m, s = [int(p) for p in time_str.split(":")]
    return h * 3600 + m * 60 + s


class GTFSFeed:
    """Encapsulates calendar, calendar_dates, trips, and precomputed trip spans for one snapshot."""

    def __init__(self, snapshot_date: str):
        self.snapshot_date = snapshot_date
        zip_path = GTFS_DIR / snapshot_date / "original.zip"
        with zipfile.ZipFile(zip_path) as z:
            self.calendar = pd.read_csv(z.open("calendar.txt"), dtype=str)
            self.calendar_dates = (
                pd.read_csv(z.open("calendar_dates.txt"), dtype=str)
                if "calendar_dates.txt" in z.namelist()
                else pd.DataFrame(columns=["service_id", "date", "exception_type"])
            )
            self.trips = pd.read_csv(
                z.open("trips.txt"),
                usecols=["route_id", "service_id", "trip_id"],
                dtype=str,
            )
            st = pd.read_csv(
                z.open("stop_times.txt"),
                usecols=["trip_id", "stop_sequence", "arrival_time", "departure_time"],
                dtype=str,
            )

        st["seq"] = st["stop_sequence"].astype(int)
        st_sorted = st.sort_values(["trip_id", "seq"])
        first_st = st_sorted.groupby("trip_id", as_index=False).first()
        last_st = st_sorted.groupby("trip_id", as_index=False).last()

        first_st["dep_sec"] = first_st["departure_time"].apply(parse_time_to_seconds)
        last_st["arr_sec"] = last_st["arrival_time"].apply(parse_time_to_seconds)

        self.trip_spans = pd.DataFrame(
            {
                "trip_id": first_st["trip_id"],
                "dep_sec": first_st["dep_sec"],
                "arr_sec": last_st["arr_sec"],
            }
        ).merge(self.trips, on="trip_id")

        # Map service_id -> list of trips: [(route_id, dep_sec, arr_sec), ...]
        self.service_trips = defaultdict(list)
        for _, row in self.trip_spans.iterrows():
            self.service_trips[row["service_id"]].append(
                (row["route_id"], row["dep_sec"], row["arr_sec"])
            )

        self.routes = sorted(self.trips["route_id"].unique())

    def get_active_services(self, dt: datetime) -> set[str]:
        """Step 7: find services active on a given date using calendar + calendar_dates."""
        day_col = dt.strftime("%A").lower()
        d_compact = dt.strftime("%Y%m%d")

        active_cal = self.calendar[
            (self.calendar["start_date"] <= d_compact)
            & (self.calendar["end_date"] >= d_compact)
            & (self.calendar[day_col] == "1")
        ]["service_id"].tolist()
        active_set = set(active_cal)

        day_cd = self.calendar_dates[self.calendar_dates["date"] == d_compact]
        if not day_cd.empty:
            removals = set(day_cd[day_cd["exception_type"] == "2"]["service_id"])
            additions = set(day_cd[day_cd["exception_type"] == "1"]["service_id"])
            active_set = (active_set - removals) | additions

        return active_set

    def get_trip_count(self, dt: datetime, include_boundary_markers: bool = True) -> int:
        active_services = self.get_active_services(dt)
        if not include_boundary_markers:
            active_services = {s for s in active_services if not s.endswith("-BM")}
        cnt = sum(len(self.service_trips[s]) for s in active_services)
        return cnt

    def get_routes_on_date(self, dt: datetime, include_boundary_markers: bool = True) -> set[str]:
        active_services = self.get_active_services(dt)
        if not include_boundary_markers:
            active_services = {s for s in active_services if not s.endswith("-BM")}
        return {r for s in active_services for r, _, _ in self.service_trips[s]}


def test_step_7_holiday(feed_0409: GTFSFeed):
    """Test Step 7 on normal Monday (2026-05-18) vs Memorial Day (2026-05-25)."""
    print("\n--- Running Step 7 Holiday Unit Test (Memorial Day) ---")
    d_normal = datetime(2026, 5, 18)
    d_holiday = datetime(2026, 5, 25)

    s_normal = feed_0409.get_active_services(d_normal)
    s_holiday = feed_0409.get_active_services(d_holiday)

    cnt_normal = feed_0409.get_trip_count(d_normal)
    cnt_holiday = feed_0409.get_trip_count(d_holiday)

    print(f"  Normal Monday 2026-05-18: {cnt_normal:,} trips (services: {sorted(s_normal)})")
    print(f"  Memorial Day  2026-05-25: {cnt_holiday:,} trips (services: {sorted(s_holiday)})")

    # Assert regular weekday services were removed and Sunday services were added
    assert any("Weekday" in s for s in s_normal), "Normal Monday should have Weekday service"
    assert any("Sunday" in s for s in s_holiday), "Memorial Day should have Sunday service"
    assert "MQ_B6-Weekday-SDon" not in s_holiday, "Primary school weekday service must be absent on Memorial Day"
    assert cnt_holiday < cnt_normal, "Holiday trip count should reflect reduced Sunday schedule"
    print("  Step 7 Holiday Test: PASSED")


def run_overlap_comparisons(feeds: dict[str, GTFSFeed]):
    """Step 8: Cross-version accuracy checks on overlapping dates and switch-overs."""
    print("\n--- Running Step 8 Cross-Version Overlap Comparisons ---")
    comparisons = [
        ("2026-01-05", "2025-12-30", "2026-03-27", "Normal Winter Monday"),
        ("2026-01-19", "2025-12-30", "2026-03-27", "MLK Day (Holiday Schedule)"),
        ("2026-02-16", "2025-12-30", "2026-03-27", "Presidents' Day (Holiday Schedule)"),
        ("2026-03-04", "2025-12-30", "2026-03-27", "Early March Wednesday"),
        ("2026-03-07", "2025-12-30", "2026-03-27", "Early March Saturday"),
        ("2026-03-27", "2025-12-30", "2026-03-27", "Download switch-over date (Friday)"),
        ("2026-03-28", "2025-12-30", "2026-03-27", "Saturday before seasonal transition"),
        ("2026-04-11", "2026-03-27", "2026-04-09", "Saturday before Spring Sunday pick"),
        ("2026-06-27", "2026-04-09", "2026-06-24", "Saturday before Summer Sunday pick"),
        ("2026-09-05", "2026-06-24", "2026-09-03", "Saturday before Fall Sunday pick"),
    ]

    records = []
    for d_str, snap1, snap2, desc in comparisons:
        dt = datetime.strptime(d_str, "%Y-%m-%d")
        c1 = feeds[snap1].get_trip_count(dt)
        c2 = feeds[snap2].get_trip_count(dt)
        diff = c2 - c1
        pct = (diff / c1 * 100) if c1 else 0
        records.append({
            "date": d_str,
            "description": desc,
            "version_A": snap1,
            "trips_A": c1,
            "version_B": snap2,
            "trips_B": c2,
            "diff": diff,
            "pct_diff": round(pct, 2),
        })
        print(f"  {d_str} ({desc}): {snap1}={c1:,} vs {snap2}={c2:,} (diff={diff:+d})")

    df_comp = pd.DataFrame(records)
    out_comp = REPORTS_DIR / "gtfs_overlap_comparison.csv"
    df_comp.to_csv(out_comp, index=False)
    print(f"  Saved comparison table -> {out_comp.relative_to(ROOT)}")


def select_snapshot_schedule(feeds: dict[str, GTFSFeed], start_d: str, end_d: str) -> dict[str, dict]:
    """Step 8: assign one snapshot_id per date.

    Rule: among usable versions downloaded on or before the date, take the latest one
    that has regular scheduled service on that date (ignoring boundary-marker trips ending in -BM).
    This cleanly avoids arbitrary thresholds while correctly assigning boundary Saturdays
    (which only contain -BM boundary trips in incoming feeds) to the outgoing feed.
    """
    out = {}
    curr = datetime.strptime(start_d, "%Y-%m-%d")
    end = datetime.strptime(end_d, "%Y-%m-%d")

    while curr <= end:
        d_str = curr.strftime("%Y-%m-%d")
        candidates = [s for s in USABLE_SNAPSHOTS if s <= d_str]
        checked = []
        chosen = None
        for s in reversed(candidates):
            reg_trips = feeds[s].get_trip_count(curr, include_boundary_markers=False)
            routes = feeds[s].get_routes_on_date(curr)
            checked.append(f"{s}:{reg_trips} reg_trips/{len(routes)} routes")
            if reg_trips > 0:
                chosen = s
                break
        full = chosen is not None
        if not full:
            # If no version has regular service (e.g. 2026-01-03 before winter pick starts),
            # fall back to the available version with any trips and mark partial.
            with_trips = [s for s in reversed(candidates) if feeds[s].get_trip_count(curr) > 0]
            chosen = with_trips[0] if with_trips else candidates[-1]
        out[d_str] = {
            "date": d_str,
            "snapshot_id": chosen,
            "trips": feeds[chosen].get_trip_count(curr),
            "routes_with_trips": len(feeds[chosen].get_routes_on_date(curr)),
            "full_service": full,
            "versions_checked": "; ".join(checked),
        }
        curr += timedelta(days=1)

    return out


def count_trip_hours(service_date: datetime, trips, grid: dict, start: str, end: str) -> None:
    """Add one service day's trips to grid[(route, clock_date, clock_hour)] = [starting, running].

    trips: iterable of (route_id, dep_sec, arr_sec), seconds from the service day's midnight.
    Times >= 24:00:00 roll over to the next calendar date (25:10 on 3 Mar -> 01:10 on 4 Mar).
    DST adjustment: On 8 March 2026, clocks sprang forward 01:59:59 -> 03:00:00, so hour 2 did not
    exist in wall-clock time; trips falling in nominal hour 2 are shifted to hour 3.
    """
    for route_id, dep_sec, arr_sec in trips:
        start_dt = service_date + timedelta(days=dep_sec // 86400)
        start_str = start_dt.strftime("%Y-%m-%d")
        start_hour = (dep_sec % 86400) // 3600

        # Daylight Saving Night: hour 2 AM does not exist on 8 March 2026
        if start_str == "2026-03-08" and start_hour == 2:
            start_hour = 3

        if start <= start_str <= end:
            grid[(route_id, start_str, start_hour)][0] += 1

        h_start = dep_sec // 3600
        h_end = (arr_sec - 1) // 3600 if arr_sec > dep_sec else h_start
        for h in range(h_start, h_end + 1):
            run_dt = service_date + timedelta(days=h // 24)
            run_str = run_dt.strftime("%Y-%m-%d")
            run_hour = h % 24

            # Daylight Saving Night: hour 2 AM does not exist on 8 March 2026
            if run_str == "2026-03-08" and run_hour == 2:
                run_hour = 3

            if start <= run_str <= end:
                grid[(route_id, run_str, run_hour)][1] += 1


def build_hourly_schedule(feeds: dict[str, GTFSFeed], date_to_snap: dict[str, str]) -> pd.DataFrame:
    """Step 9: Accumulate trips_starting and trips_running across real clock hours."""
    print("\n--- Running Step 9: Aggregating Hourly Scheduled Trips ---")
    # All routes present in feeds
    all_routes = sorted(list({r for f in feeds.values() for r in f.routes}))
    start_dt = datetime.strptime(START_DATE, "%Y-%m-%d")
    end_dt = datetime.strptime(END_DATE, "%Y-%m-%d")

    # Map: (route, date_str, hour) -> [trips_starting, trips_running]
    grid = defaultdict(lambda: [0, 0])

    curr = start_dt
    while curr <= end_dt:
        d_str = curr.strftime("%Y-%m-%d")
        feed = feeds[date_to_snap[d_str]]
        for s in feed.get_active_services(curr):
            count_trip_hours(curr, feed.service_trips[s], grid, START_DATE, END_DATE)
        curr += timedelta(days=1)

    # Convert to complete DataFrame for all 41 routes * 24 hours * days in window
    rows = []
    curr = start_dt
    while curr <= end_dt:
        d_str = curr.strftime("%Y-%m-%d")
        snap = date_to_snap[d_str]
        for route in all_routes:
            for hour in range(24):
                counts = grid.get((route, d_str, hour), [0, 0])
                rows.append({
                    "route": route,
                    "date": d_str,
                    "hour": hour,
                    "trips_starting": counts[0],
                    "trips_running": counts[1],
                    "snapshot_id": snap,
                })
        curr += timedelta(days=1)

    df_out = pd.DataFrame(rows)
    df_out["hour"] = df_out["hour"].astype("int8")
    df_out["trips_starting"] = df_out["trips_starting"].astype("int32")
    df_out["trips_running"] = df_out["trips_running"].astype("int32")

    return df_out


def main():
    print(f"Loading {len(USABLE_SNAPSHOTS)} usable GTFS feeds...")
    feeds = {}
    for snap in USABLE_SNAPSHOTS:
        t0 = datetime.now()
        feeds[snap] = GTFSFeed(snap)
        print(f"  Loaded {snap}: {len(feeds[snap].trips):,} trips, "
              f"{len(feeds[snap].routes)} routes ({datetime.now() - t0})")

    # Step 7 unit test
    test_step_7_holiday(feeds["2026-04-09"])

    # Step 8 overlap comparisons
    run_overlap_comparisons(feeds)

    # Step 8 snapshot schedule mapping
    date_info = select_snapshot_schedule(feeds, START_DATE, END_DATE)
    date_to_snap = {d: v["snapshot_id"] for d, v in date_info.items()}
    df_dates = pd.DataFrame(date_info.values())
    df_dates.to_csv(REPORTS_DIR / "schedule_dates.csv", index=False)
    partial = df_dates[~df_dates.full_service]
    print(f"\nDates without full service in any version: {partial.date.tolist() or 'none'}")

    # Save switchover summary
    snap_blocks = []
    curr_snap = None
    b_start = None
    prev_d = None
    for d, s in sorted(date_to_snap.items()):
        if s != curr_snap:
            if curr_snap is not None:
                snap_blocks.append({"snapshot_id": curr_snap, "start_date": b_start, "end_date": prev_d})
            curr_snap = s
            b_start = d
        prev_d = d
    if curr_snap is not None:
        snap_blocks.append({"snapshot_id": curr_snap, "start_date": b_start, "end_date": prev_d})

    df_blocks = pd.DataFrame(snap_blocks)
    df_blocks["days"] = (pd.to_datetime(df_blocks.end_date) - pd.to_datetime(df_blocks.start_date)).dt.days + 1
    print("\nSnapshot Schedule Blocks:")
    print(df_blocks.to_string(index=False))
    df_blocks.to_csv(REPORTS_DIR / "gtfs_switchover_schedule.csv", index=False)

    # Step 9 build hourly table
    df_sched = build_hourly_schedule(feeds, date_to_snap)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df_sched.to_parquet(OUT_FILE, index=False)
    print(f"\nWrote {len(df_sched):,} rows -> {OUT_FILE.relative_to(ROOT)}")
    print(f"Dates: {df_sched['date'].min()} to {df_sched['date'].max()} "
          f"({df_sched['date'].nunique()} days)")
    print(f"Routes: {df_sched['route'].nunique()}")
    print("Summary statistics:")
    print(df_sched[["trips_starting", "trips_running"]].describe())


if __name__ == "__main__":
    main()
