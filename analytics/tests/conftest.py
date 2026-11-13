"""Shared helpers: write a tiny hand-made GTFS feed and run the REAL Stage 2 functions on it."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from analytics.reconstruction.daily_service import build_trip_durations, daily_service
from analytics.reconstruction.gtfs_tables import bus_crosswalk, open_snapshot
from analytics.reconstruction.service_calendar import active_service_dates, load_calendar, load_calendar_dates

ROUTES = ("route_id,route_short_name,route_long_name,route_type\n"
          "R1,1,Bronzeville,3\nR9,X9,Ashland Express,3\nRED,,Red Line,1\n")
CAL_HEADER = "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
CD_HEADER = "service_id,date,exception_type\n"
ST_HEADER = "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"


def stop_rows(trip_id: str, start: str, end: str) -> str:
    """A 2-stop trip from `start` to `end` (times may exceed 24:00:00)."""
    return f"{trip_id},{start},{start},S1,1\n{trip_id},{end},{end},S2,2\n"


def write_feed(folder: Path, trips: str, stop_times: str, calendar: str | None = "",
               calendar_dates: str | None = "", routes: str = ROUTES) -> Path:
    """Write GTFS text files. Pass calendar=None / calendar_dates=None to omit that file entirely."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "routes.txt").write_text(routes, encoding="utf-8")
    (folder / "trips.txt").write_text("route_id,service_id,trip_id\n" + trips, encoding="utf-8")
    (folder / "stop_times.txt").write_text(ST_HEADER + stop_times, encoding="utf-8")
    if calendar is not None:
        (folder / "calendar.txt").write_text(CAL_HEADER + calendar, encoding="utf-8")
    if calendar_dates is not None:
        (folder / "calendar_dates.txt").write_text(CD_HEADER + calendar_dates, encoding="utf-8")
    return folder


def run_feed(folder: Path, dates: list[date], snapshot_id: str = "test-snap"):
    """Full per-snapshot pipeline: crosswalk -> durations -> active services -> route/date service."""
    con, _ = open_snapshot(folder)
    bus_crosswalk(con, snapshot_id)
    build_trip_durations(con)
    active = active_service_dates(load_calendar(con), load_calendar_dates(con), dates)
    out = daily_service(con, snapshot_id, active)
    con.close()
    return out


def row(df, route: str, d: date):
    sel = df[(df["route"] == route) & (df["date"] == d)]
    assert len(sel) <= 1, "route/date must be unique"
    return None if sel.empty else sel.iloc[0]


@pytest.fixture
def feed(tmp_path):
    counter = {"n": 0}

    def make(**kwargs) -> Path:
        counter["n"] += 1
        return write_feed(tmp_path / f"feed{counter['n']}", **kwargs)
    return make
