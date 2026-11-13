"""Forecast-input schedule selection (spec 9.14.3), kept separate from the descriptive Stage 2 selection.

Descriptive: latest archive captured on/before D (describes what was scheduled on D).
Forecast:    latest archive captured strictly before D (what a forecaster could have known at the start of D).
They differ only on capture dates ("boundary dates"). On those dates the forecast schedule is REBUILT from the
earlier archive with the Stage 2 pipeline; elsewhere both selections choose the same archive, so the Stage 2
values for that same archive and date are the forecast inputs.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from analytics.reconstruction.daily_service import build_trip_durations, daily_service
from analytics.reconstruction.gtfs_tables import bus_crosswalk, open_snapshot
from analytics.reconstruction.service_calendar import active_service_dates, load_calendar, load_calendar_dates
from analytics.reconstruction.snapshot_select import (archive_available_from, date_range, select_forecast_snapshot,
                                                      select_snapshot)

FORECAST_COLS = ["forecast_snapshot", "forecast_archive_available_from", "forecast_scheduled_trips",
                 "forecast_scheduled_service_hours", "forecast_duration_complete", "forecast_schedule_status"]


def selection_pairs(start: date, end: date, archives: list[dict]) -> pd.DataFrame:
    rows = [{"date": d, "descriptive_snapshot": select_snapshot(d, archives),
             "forecast_snapshot": select_forecast_snapshot(d, archives)} for d in date_range(start, end)]
    df = pd.DataFrame(rows)
    df["boundary"] = df["descriptive_snapshot"] != df["forecast_snapshot"]
    return df


def rebuild_boundary_service(pairs: pd.DataFrame, extracted_dirs: dict[str, Path]) -> pd.DataFrame:
    """Daily service from the FORECAST archive on boundary dates (where it differs from the descriptive one)."""
    parts = []
    b = pairs[pairs["boundary"] & pairs["forecast_snapshot"].notna()]
    for sid, g in b.groupby("forecast_snapshot"):
        con, _ = open_snapshot(extracted_dirs[sid])
        bus_crosswalk(con, sid)
        build_trip_durations(con)
        dates = sorted(g["date"])
        parts.append(daily_service(con, sid, active_service_dates(load_calendar(con), load_calendar_dates(con), dates)))
        con.close()
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["snapshot_id", "route", "date", "route_id", "scheduled_trips", "scheduled_service_hours",
                 "duration_complete", "trips_missing_duration"])


def forecast_inputs(targets: pd.DataFrame, schedule: pd.DataFrame, boundary_service: pd.DataFrame,
                    pairs: pd.DataFrame, captured: dict[str, date]) -> pd.DataFrame:
    """One row per target (route, date): the schedule inputs a forecast issued at the start of `date` may use."""
    pmap = pairs.set_index("date")
    t = targets[["route", "date"]].copy()
    t["forecast_snapshot"] = t["date"].map(pmap["forecast_snapshot"])
    t["boundary"] = t["date"].map(pmap["boundary"]).astype(bool)
    src = pd.concat([schedule, boundary_service], ignore_index=True)
    src = src.rename(columns={"snapshot_id": "forecast_snapshot", "scheduled_trips": "forecast_scheduled_trips",
                              "scheduled_service_hours": "forecast_scheduled_service_hours",
                              "duration_complete": "forecast_duration_complete"})
    src = src.drop_duplicates(["forecast_snapshot", "route", "date"])  # same archive+date -> identical values
    out = t.merge(src[["forecast_snapshot", "route", "date", "forecast_scheduled_trips",
                       "forecast_scheduled_service_hours", "forecast_duration_complete"]],
                  on=["forecast_snapshot", "route", "date"], how="left", validate="one_to_one")
    out["forecast_archive_available_from"] = out["forecast_snapshot"].map(
        lambda s: archive_available_from(captured[s]) if isinstance(s, str) else None)
    snap_dates = set(zip(src["forecast_snapshot"], src["date"]))  # archive defines bus service on that date
    status = []
    for s, d, trips in zip(out["forecast_snapshot"], out["date"], out["forecast_scheduled_trips"]):
        if not isinstance(s, str):
            status.append("no_archive_available_before_issue")
        elif (s, d) not in snap_dates:
            status.append("forecast_archive_defines_no_service_on_date")
        elif pd.isna(trips):
            status.append("route_not_scheduled_in_forecast_archive")
        else:
            status.append("available")
    out["forecast_schedule_status"] = status
    return out
