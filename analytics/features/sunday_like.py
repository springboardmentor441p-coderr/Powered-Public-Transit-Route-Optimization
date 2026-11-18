"""Schedule-based Sunday-like day flag (notebook steps 8e, 11, 12). Replaces the calendar/holiday predictor.

A date is Sunday-like when MORE THAN HALF of its scheduled bus trips belong to Sunday-only services. A Sunday-only
service is a calendar.txt row with sunday = 1 and monday..friday all 0 (calendar.txt only, a stated limit: a
service defined only in calendar_dates.txt cannot be classified, so such services are reported, not guessed).

The trips come from the FORECAST archive (latest captured strictly before the date), so the flag is known at the
issue time. It never reads the reported passenger daytype; that is used only to check the flag afterwards.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from analytics.reconstruction.gtfs_tables import bus_crosswalk, open_snapshot
from analytics.reconstruction.service_calendar import (WEEKDAYS, active_service_dates, load_calendar,
                                                       load_calendar_dates)

SUNDAY_LIKE_SHARE = 0.5  # strictly more than this share of the day's trips


def sunday_only_services(calendar: pd.DataFrame) -> set[str]:
    """Services that run on Sunday but on no day Monday-Friday (`calendar` as returned by load_calendar)."""
    if calendar.empty:
        return set()
    mask = calendar["sunday"].astype(bool) & ~calendar[WEEKDAYS[:5]].astype(bool).any(axis=1)
    return set(calendar.loc[mask, "service_id"])


def exception_only_services(con: duckdb.DuckDBPyConnection, calendar: pd.DataFrame) -> list[str]:
    """Bus trip services with no calendar.txt row (cannot be classified). Requires TEMP TABLE bus_cw."""
    used = {r[0] for r in con.execute(
        "SELECT DISTINCT t.service_id FROM trips t JOIN bus_cw cw ON cw.route_id = t.route_id").fetchall()}
    return sorted(used - set(calendar["service_id"]))


def trips_by_date(con: duckdb.DuckDBPyConnection, active: pd.DataFrame, sunday_only: set[str]) -> pd.DataFrame:
    """Per date: active bus trips and how many of them belong to Sunday-only services. Requires bus_cw."""
    act = active.assign(sunday_only=active["service_id"].isin(sunday_only))
    con.register("_act", act)
    try:
        out = con.execute("""
            SELECT a.date, count(*) AS scheduled_bus_trips,
                   count(*) FILTER (WHERE a.sunday_only) AS sunday_only_trips
            FROM _act a JOIN trips t ON t.service_id = a.service_id JOIN bus_cw cw ON cw.route_id = t.route_id
            GROUP BY a.date ORDER BY a.date""").df()
    finally:
        con.unregister("_act")
    out["date"] = pd.to_datetime(out["date"]).dt.date
    return out


def sunday_like_flag(trips: pd.Series, sunday_trips: pd.Series) -> pd.Series:
    return (sunday_trips / trips > SUNDAY_LIKE_SHARE).astype("int64")


def snapshot_sunday_like(extracted_dir: Path, snapshot_id: str, dates: list[date]) -> tuple[pd.DataFrame, list[str]]:
    con, _ = open_snapshot(extracted_dir)
    try:
        bus_crosswalk(con, snapshot_id)
        cal = load_calendar(con)
        active = active_service_dates(cal, load_calendar_dates(con), dates)
        table = trips_by_date(con, active, sunday_only_services(cal))
        exc = exception_only_services(con, cal)
    finally:
        con.close()
    table.insert(0, "schedule_saved", snapshot_id)
    table["sunday_like_day"] = sunday_like_flag(table["scheduled_bus_trips"], table["sunday_only_trips"])
    return table, exc


def sunday_like_days(pairs: pd.DataFrame, extracted_dirs: dict[str, Path]) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """One row per date with a forecast archive: trips, Sunday-only trips, flag. Plus exception-only services."""
    parts, exception_only = [], {}
    usable = pairs[pairs["forecast_snapshot"].notna()]
    for sid, g in usable.groupby("forecast_snapshot"):
        t, exc = snapshot_sunday_like(extracted_dirs[sid], sid, sorted(g["date"]))
        parts.append(t)
        exception_only[sid] = exc
    days = pd.concat(parts, ignore_index=True).sort_values("date").reset_index(drop=True)
    if days["date"].duplicated().any():
        raise ValueError("a date received a Sunday-like flag from more than one archive")
    return days, exception_only
