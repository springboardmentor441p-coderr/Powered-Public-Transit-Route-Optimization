"""Spec 9.19.1 correctness cases for the schedule side (calendar, times, regimes, snapshot selection, durations)."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from analytics.reconstruction.daily_service import parse_gtfs_time
from analytics.reconstruction.gtfs_tables import CrosswalkError, bus_crosswalk, open_snapshot
from analytics.reconstruction.snapshot_select import select_snapshot, selection_table

from .conftest import row, run_feed, stop_rows

MON, TUE, WED, SAT, SUN = date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4), date(2026, 3, 7), date(2026, 3, 8)
WEEKDAY_MARCH = "WK,1,1,1,1,1,0,0,20260301,20260331\n"


# 9.19.1: "A weekly service removed by exception type 2 is absent on that date."
def test_exception_type_2_removes_weekly_service(feed):
    f = feed(trips="R1,WK,T1\n", stop_times=stop_rows("T1", "08:00:00", "09:00:00"),
             calendar=WEEKDAY_MARCH, calendar_dates="WK,20260304,2\n")
    out = run_feed(f, [TUE, WED])
    assert row(out, "1", TUE)["scheduled_trips"] == 1
    assert row(out, "1", WED) is None  # removed that Wednesday only


# 9.19.1: "An added service appears once, including when the weekly mask also includes it."
def test_exception_type_1_adds_once_even_if_weekly_includes_it(feed):
    f = feed(trips="R1,WK,T1\nR1,HOL,T2\n",
             stop_times=stop_rows("T1", "08:00:00", "09:00:00") + stop_rows("T2", "10:00:00", "11:00:00"),
             calendar=WEEKDAY_MARCH,
             calendar_dates="WK,20260303,1\nHOL,20260308,1\n")  # WK already runs Tuesday; HOL only by exception
    out = run_feed(f, [TUE, SUN])
    assert row(out, "1", TUE)["scheduled_trips"] == 1  # not 2
    assert row(out, "1", SUN)["scheduled_trips"] == 1  # exception-added service on a Sunday


# 9.19.1: "A time of 25:10 stays in its original service date."
def test_time_after_midnight_stays_on_service_date(feed):
    assert parse_gtfs_time("25:10:00") == 90_600
    assert parse_gtfs_time(" 7:05:09 ") == 7 * 3600 + 5 * 60 + 9
    assert parse_gtfs_time("") is None and parse_gtfs_time("25:61:00") is None
    f = feed(trips="R1,TUE_ONLY,T1\n", stop_times=stop_rows("T1", "24:30:00", "25:10:00"),
             calendar="TUE_ONLY,0,1,0,0,0,0,0,20260301,20260331\n")
    out = run_feed(f, [TUE, WED])
    r = row(out, "1", TUE)
    assert r["scheduled_trips"] == 1
    assert r["scheduled_service_hours"] == pytest.approx(40 / 60)  # 40 minutes, not negative, not ~23 hours
    assert row(out, "1", WED) is None  # the after-midnight trip does not move to the next calendar date


# 9.19.1: "Outgoing and incoming timetable regimes are counted only on active dates."
def test_outgoing_and_incoming_regimes_counted_only_on_their_dates(feed):
    f = feed(trips="R1,OUT,T1\nR1,IN,T2\nR1,IN,T3\n",
             stop_times="".join(stop_rows(t, "08:00:00", "09:00:00") for t in ["T1", "T2", "T3"]),
             calendar="OUT,1,1,1,1,1,1,1,20260301,20260314\nIN,1,1,1,1,1,1,1,20260315,20260331\n")
    out = run_feed(f, [date(2026, 3, 14), date(2026, 3, 15)])
    assert row(out, "1", date(2026, 3, 14))["scheduled_trips"] == 1  # outgoing only
    assert row(out, "1", date(2026, 3, 15))["scheduled_trips"] == 2  # incoming only, never 3


# 9.19.1: "Each route/date has one selected snapshot; withdrawn routes do not fall back individually."
def test_one_snapshot_per_date_and_no_per_route_fallback(feed):
    older = feed(trips="R1,ALL,T1\nR9,ALL,T9\n",
                 stop_times=stop_rows("T1", "08:00:00", "09:00:00") + stop_rows("T9", "08:00:00", "09:00:00"),
                 calendar="ALL,1,1,1,1,1,1,1,20260301,20260430\n")
    newer = feed(trips="R1,ALL,T1\n", stop_times=stop_rows("T1", "08:00:00", "09:00:00"),  # X9 withdrawn
                 calendar="ALL,1,1,1,1,1,1,1,20260315,20260430\n",
                 routes="route_id,route_short_name,route_type\nR1,1,3\n")
    archives = [{"snapshot_id": "older", "captured": date(2026, 3, 1)},
                {"snapshot_id": "newer", "captured": date(2026, 3, 15)}]
    assert select_snapshot(date(2026, 2, 28), archives) is None  # gap: nothing captured yet
    assert select_snapshot(date(2026, 3, 14), archives) == "older"
    assert select_snapshot(date(2026, 3, 15), archives) == "newer"  # capture date itself uses the new one

    sel = selection_table(date(2026, 3, 13), date(2026, 3, 16), archives)
    assert sel["date"].is_unique  # exactly one snapshot per date
    paths = {"older": older, "newer": newer}
    parts = [run_feed(paths[sid], list(g["date"]), sid) for sid, g in sel.groupby("snapshot_id")]
    sched = pd.concat(parts)
    assert not sched.duplicated(["route", "date"]).any()
    assert row(sched, "X9", date(2026, 3, 14)) is not None  # still in the older selected snapshot
    assert row(sched, "X9", date(2026, 3, 15)) is None  # withdrawn: NOT resurrected from the older archive
    assert row(sched, "1", date(2026, 3, 15))["snapshot_id"] == "newer"


def test_invalid_duration_keeps_trip_but_hours_missing(feed):
    f = feed(trips="R1,WK,T1\nR1,WK,T2\nR1,WK,T3\nR9,WK,T9\n",
             stop_times=(stop_rows("T1", "08:00:00", "09:00:00")
                         + "T2,08:00:00,08:00:00,S1,1\nT2,,,S2,2\n"  # last stop has no arrival time
                         + stop_rows("T9", "08:00:00", "08:30:00")),  # T3 has no stop_times at all
             calendar=WEEKDAY_MARCH)
    out = run_feed(f, [TUE])
    r = row(out, "1", TUE)
    assert r["scheduled_trips"] == 3  # all active trips counted
    assert r["trips_missing_duration"] == 2
    assert not r["duration_complete"]
    assert pd.isna(r["scheduled_service_hours"])  # missing, not the partial sum 1.0
    ok = row(out, "X9", TUE)
    assert ok["duration_complete"] and ok["scheduled_service_hours"] == pytest.approx(0.5)


def test_first_and_last_stop_chosen_by_stop_sequence(feed):
    # rows deliberately out of order in the file; duration must come from sequence 1 -> 3
    st = "T1,09:30:00,09:30:00,S3,3\nT1,08:00:00,08:00:00,S1,1\nT1,08:45:00,08:46:00,S2,2\n"
    f = feed(trips="R1,WK,T1\n", stop_times=st, calendar=WEEKDAY_MARCH)
    assert row(run_feed(f, [TUE]), "1", TUE)["scheduled_service_hours"] == pytest.approx(1.5)


def test_calendar_defined_only_by_exceptions(feed):
    f = feed(trips="R1,EXC,T1\n", stop_times=stop_rows("T1", "08:00:00", "09:00:00"),
             calendar=None, calendar_dates="EXC,20260307,1\n")
    out = run_feed(f, [date(2026, 3, 6), SAT])
    assert row(out, "1", SAT)["scheduled_trips"] == 1
    assert row(out, "1", date(2026, 3, 6)) is None


def test_bus_filter_excludes_rail(feed):
    f = feed(trips="R1,WK,T1\nRED,WK,TR\n",
             stop_times=stop_rows("T1", "08:00:00", "09:00:00") + stop_rows("TR", "08:00:00", "09:00:00"),
             calendar=WEEKDAY_MARCH)
    out = run_feed(f, [TUE])
    assert set(out["route"]) == {"1"}


def test_non_unique_crosswalk_fails(feed):
    f = feed(trips="A,WK,T1\n", stop_times=stop_rows("T1", "08:00:00", "09:00:00"), calendar=WEEKDAY_MARCH,
             routes="route_id,route_short_name,route_type\nA,22,3\nB, 22 ,3\n")  # same public name after trim
    con, _ = open_snapshot(f)
    with pytest.raises(CrosswalkError):
        bus_crosswalk(con, "dup")
    con.close()
