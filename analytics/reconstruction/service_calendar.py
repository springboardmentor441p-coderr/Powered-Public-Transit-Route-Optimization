"""Step 12: active service IDs per date from calendar.txt + calendar_dates.txt (spec 9.6.3, GTFS reference).

Rule for date D:
  1. weekly service: D within [start_date, end_date] (inclusive) AND D's weekday flag is 1
  2. exception_type 2 on D removes the service
  3. exception_type 1 on D adds the service
Results are SETS, so a service added by an exception that the weekly mask already includes appears once.
A calendar defined only by exceptions (empty calendar.txt) works because step 3 alone can add services.
"""
from __future__ import annotations

from datetime import date, datetime

import duckdb
import pandas as pd

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]  # date.weekday() order


class CalendarError(ValueError):
    pass


def _ymd(s: str) -> date:
    return datetime.strptime(s, "%Y%m%d").date()


def load_calendar(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    cal = con.execute("SELECT * FROM calendar").df()
    if cal.empty:
        return pd.DataFrame(columns=["service_id", *WEEKDAYS, "start_date", "end_date"])
    bad = cal[~cal[WEEKDAYS].isin(["0", "1"]).all(axis=1)]
    if not bad.empty:
        raise CalendarError(f"calendar.txt weekday flags must be 0/1: {bad['service_id'].tolist()[:5]}")
    if cal["service_id"].duplicated().any():
        raise CalendarError("calendar.txt has duplicate service_id rows")
    cal["start_date"] = cal["start_date"].map(_ymd)
    cal["end_date"] = cal["end_date"].map(_ymd)
    for d in WEEKDAYS:
        cal[d] = cal[d] == "1"
    return cal[["service_id", *WEEKDAYS, "start_date", "end_date"]]


def load_calendar_dates(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    cd = con.execute("SELECT service_id, date, exception_type FROM calendar_dates").df()
    if cd.empty:
        return pd.DataFrame(columns=["service_id", "date", "exception_type"])
    if not cd["exception_type"].isin(["1", "2"]).all():
        raise CalendarError("calendar_dates.txt exception_type must be 1 or 2")
    if cd.duplicated(["service_id", "date"]).any():
        raise CalendarError("calendar_dates.txt has duplicate (service_id, date) pairs")
    cd["date"] = cd["date"].map(_ymd)
    cd["exception_type"] = cd["exception_type"].astype(int)
    return cd


def active_services(calendar: pd.DataFrame, calendar_dates: pd.DataFrame, d: date) -> set[str]:
    flag = WEEKDAYS[d.weekday()]
    weekly = calendar[(calendar["start_date"] <= d) & (calendar["end_date"] >= d) & calendar[flag]]
    active = set(weekly["service_id"])
    today = calendar_dates[calendar_dates["date"] == d]
    active -= set(today.loc[today["exception_type"] == 2, "service_id"])
    active |= set(today.loc[today["exception_type"] == 1, "service_id"])
    return active


def active_service_dates(calendar: pd.DataFrame, calendar_dates: pd.DataFrame, dates: list[date]) -> pd.DataFrame:
    """Long table (date, service_id) of every active service on every requested date."""
    rows = [(d, s) for d in dates for s in sorted(active_services(calendar, calendar_dates, d))]
    return pd.DataFrame(rows, columns=["date", "service_id"])
