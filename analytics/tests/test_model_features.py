"""Stage 4a alignment: the notebook's build_features rules and the schedule-based Sunday-like flag."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from analytics.features.model_features import attach_actuals, build_features
from analytics.features.naming import NO_ACTUAL_REASON
from analytics.features.sunday_like import snapshot_sunday_like

MON = date(2026, 3, 9)
SUN = date(2026, 3, 8)


def targets(*routes_dates, trips=10.0, hours=5.0):
    return pd.DataFrame([{"route": r, "date": pd.Timestamp(d), "scheduled_trips": trips, "scheduled_hours": hours,
                          "sunday_like_day": 0} for r, d in routes_dates])


def history(rows):
    return pd.DataFrame(rows, columns=["route", "date", "daytype", "rides"]).assign(
        date=lambda d: pd.to_datetime(d["date"]), rides=lambda d: d["rides"].astype("Int64"))


def lag(k, rides, route="A", d=MON):
    return (route, d - timedelta(days=k), "W", rides)


def test_real_zero_stays_zero_and_missing_stays_missing():
    h = history([lag(1, 0), lag(7, 70), lag(14, 0), lag(21, 210), ("A", MON, "W", 0)])  # 28-day date absent
    f = attach_actuals(build_features(targets(("A", MON)), h), h).iloc[0]
    assert f["boardings_1d_ago"] == 0 and f["boardings_14d_ago"] == 0  # recorded zeros are real history
    assert np.isnan(f["boardings_28d_ago"])  # an absent date stays missing, never 0
    assert f["boardings_28d_available"] == 0
    assert f["boardings_28d_filled"] == (70 + 0 + 210) / 3  # Option 2 fill from the AVAILABLE donors
    assert f["seasonal_count"] == 3 and f["seasonal_mean"] == (70 + 0 + 210) / 3
    assert f["rides"] == 0 and f["eligible"]  # a recorded zero target is scoreable


def test_missing_required_field_is_named_and_missing_actual_withheld():
    h = history([lag(7, 70), lag(14, 140), lag(21, 210), lag(28, 280)])  # no 1-day lag, no target record
    f = attach_actuals(build_features(targets(("A", MON)), h), h).iloc[0]
    assert np.isnan(f["boardings_1d_ago"]) and f["excluded_reason"] == "boardings_1d_ago"
    assert not f["eligible"] and not f["forecastable"]
    h2 = history([lag(k, 10 * k) for k in (1, 7, 14, 21, 28)])  # full history, but the day was never recorded
    g = attach_actuals(build_features(targets(("A", MON)), h2), h2).iloc[0]
    assert g["forecastable"] and not g["eligible"] and g["excluded_reason"] == NO_ACTUAL_REASON
    assert np.isnan(g["rides"])  # missing stays missing, it is not a zero


def test_missing_schedule_hours_withhold_every_method():
    h = history([lag(k, 10 * k) for k in (1, 7, 14, 21, 28)] + [("A", MON, "W", 5)])
    f = attach_actuals(build_features(targets(("A", MON), hours=np.nan), h), h).iloc[0]
    assert not f["eligible"] and f["excluded_reason"] == "scheduled_hours"


def test_lags_are_exact_dates_and_respect_reporting_delay():
    fri = MON - timedelta(days=3)
    h = history([("A", fri, "W", 500)] + [lag(k, 10 * k) for k in (7, 14, 21, 28)])
    f = build_features(targets(("A", MON)), h).iloc[0]
    assert np.isnan(f["boardings_1d_ago"])  # Friday's 500 is not "the previous row"
    h2 = history([lag(k, 10 * k) for k in (1, 7, 14, 21, 28)])
    g = build_features(targets(("A", MON)), h2, reporting_delay_days=2).iloc[0]
    assert np.isnan(g["boardings_1d_ago"]) and g["boardings_7d_ago"] == 70


def test_target_value_never_changes_its_own_features():
    rows = [lag(k, 10 * k) for k in (1, 7, 14, 21, 28)]
    a = build_features(targets(("A", MON)), history(rows + [("A", MON, "W", 999)])).iloc[0]
    b = build_features(targets(("A", MON)), history(rows + [("A", MON, "W", 1)])).iloc[0]
    assert a.equals(b)


def test_sunday_like_flag_from_schedule_and_exception_only_reported(feed):
    folder = feed(
        trips="R1,SUN,t1\nR1,SUN,t2\nR1,ALL,t3\nR1,WK,t4\nR9,XO,t5\n",
        stop_times="".join(f"{t},08:00:00,08:00:00,S1,1\n{t},08:30:00,08:30:00,S2,2\n" for t in ["t1", "t2", "t3", "t4", "t5"]),
        calendar="SUN,0,0,0,0,0,1,1,20260101,20261231\n"  # Saturday too: still Sunday-only (no Mon-Fri)
                 "ALL,1,1,1,1,1,1,1,20260101,20261231\nWK,1,1,1,1,1,0,0,20260101,20261231\n",
        calendar_dates="XO,20260309,1\n")
    table, exc = snapshot_sunday_like(folder, "snap", [SUN, MON])
    t = table.set_index("date")
    assert t.loc[SUN, "scheduled_bus_trips"] == 3 and t.loc[SUN, "sunday_only_trips"] == 2
    assert t.loc[SUN, "sunday_like_day"] == 1  # 2 of 3 > half
    assert t.loc[MON, "sunday_like_day"] == 0  # t3, t4, t5: no Sunday-only trips
    assert exc == ["XO"]  # cannot be classified from calendar.txt: reported, not guessed
