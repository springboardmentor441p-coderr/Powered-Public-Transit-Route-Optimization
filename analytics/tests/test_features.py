"""Stage 3 correctness cases (spec 9.9.3-9.9.4, 9.10.2-9.10.4, 9.14.3, 9.19.1) on tiny hand-made histories."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from analytics.features.lags import (DuplicateObservationError, add_calendar, add_exact_lags, add_seasonal,
                                     observed_date, observed_holidays, sunday_holiday_service_day, to_history)
from analytics.features.naming import (DEMAND_FEATURES, NEVER_PREDICTORS, SERVICE_FEATURES, SPEC_DEMAND_FEATURES,
                                       predictor_columns)
from analytics.features.preprocess import prepare
from analytics.features.splits import SplitError, assign_split, date_overlap, parse_ranges
from analytics.reconstruction.snapshot_select import (archive_available_from, select_forecast_snapshot,
                                                      select_snapshot)

LAGS, SEASONAL = [1, 7, 14, 21, 28], [7, 14, 21, 28]
MON = date(2026, 3, 9)  # a Monday
HOLIDAYS = {date(2026, 5, 25)}


def hist(rows):
    return pd.DataFrame(rows, columns=["route", "date", "daytype", "rides"])


def build(h, delay=1):
    return add_calendar(add_seasonal(add_exact_lags(to_history(h), LAGS, delay), SEASONAL, 2))


def at(df, route, d):
    r = df[(df["route"] == route) & (df["date"] == pd.Timestamp(d))]
    assert len(r) == 1
    return r.iloc[0]


def lagged(d, k, rides, route="A"):
    return (route, d - timedelta(days=k), "W", rides)


# 9.9.4 example: "Friday and Monday records but no weekend observations -> Monday's one-day lag is missing."
def test_friday_to_monday_one_day_lag_is_missing():
    fri = MON - timedelta(days=3)
    f = build(hist([("A", fri, "W", 500), ("A", MON, "W", 520)]))
    m = at(f, "A", MON)
    assert pd.isna(m["lag_1d_boardings"])  # NOT Friday's 500 ("the previous row")
    assert m["day_of_week"] == 0


# 9.19.1: "Exact-date lags stay missing when that date is absent; genuine zero rides stay zero."
def test_real_zero_stays_zero_and_counts_as_observation():
    f = build(hist([lagged(MON, 7, 0), lagged(MON, 14, 300), ("A", MON, "W", 310)]))
    m = at(f, "A", MON)
    assert m["lag_7d_boardings"] == 0 and not pd.isna(m["lag_7d_boardings"])
    assert pd.isna(m["lag_21d_boardings"]) and pd.isna(m["lag_28d_boardings"])  # absent dates stay missing
    assert m["seasonal_lag_observations"] == 2
    assert m["past_four_same_weekdays_mean"] == pytest.approx(150)  # (0 + 300) / 2: the zero is real history


# 9.19.1: "A single available seasonal lag does not become the four-week mean."
def test_single_seasonal_lag_does_not_become_the_mean():
    f = build(hist([lagged(MON, 14, 400), ("A", MON, "W", 410)]))
    m = at(f, "A", MON)
    assert m["seasonal_lag_observations"] == 1
    assert pd.isna(m["past_four_same_weekdays_mean"])  # not 400


def test_worked_example_arithmetic_synthetic():
    d = date(2024, 8, 1)
    rows = [lagged(d, 1, 1111, "1"), lagged(d, 7, 1219, "1"), lagged(d, 14, 1134, "1"), lagged(d, 21, 1040, "1"),
            ("1", d, "W", 990)]
    m = at(build(hist(rows)), "1", d)
    assert m["day_of_week"] == 3 and pd.isna(m["lag_28d_boardings"]) and m["seasonal_lag_observations"] == 3
    assert m["past_four_same_weekdays_mean"] == pytest.approx(1131)


# "The same row's target must never be part of its input features" (9.9.1)
def test_target_never_in_its_own_features():
    rows = [lagged(MON, k, 100 + k) for k in LAGS] + [("A", MON, "W", 999)]
    a = at(build(hist(rows)), "A", MON)
    rows[-1] = ("A", MON, "W", 5)  # change ONLY the target
    b = at(build(hist(rows)), "A", MON)
    feature_cols = [c for c in a.index if c not in ("rides",)]
    assert a[feature_cols].equals(b[feature_cols])
    for cols in [DEMAND_FEATURES, SERVICE_FEATURES, predictor_columns(True, "option_2")]:
        assert not set(cols) & set(NEVER_PREDICTORS)
    # the reported daytype is not a predictor; the calendar version replaces it
    assert "is_sunday_holiday_daytype" in SPEC_DEMAND_FEATURES and "is_sunday_holiday_daytype" not in DEMAND_FEATURES


# 9.10.4 / 9.19.1: a lag inside the reporting delay is not available at issue time
def test_reporting_delay_hides_short_lags():
    rows = [lagged(MON, k, 100 + k) for k in LAGS] + [("A", MON, "W", 999)]
    m1, m2 = at(build(hist(rows), delay=1), "A", MON), at(build(hist(rows), delay=2), "A", MON)
    assert m1["lag_1d_boardings"] == 101
    assert pd.isna(m2["lag_1d_boardings"]) and m2["lag_7d_boardings"] == 107


def test_duplicate_route_date_rejected_before_lags():
    with pytest.raises(DuplicateObservationError):
        to_history(hist([("A", MON, "W", 1), ("A", MON, "W", 2)]))


def test_splits_have_no_date_overlap():
    ranges = parse_ranges({"train": ["2026-01-01", "2026-01-31"], "validation": ["2026-02-01", "2026-02-28"],
                           "test": ["2026-03-01", "2026-03-31"]})
    dates = pd.Series(pd.date_range("2026-01-01", "2026-03-31"))
    df = pd.DataFrame({"date": dates, "split": assign_split(dates, ranges)})
    assert date_overlap(df) == {"train&validation": 0, "train&test": 0, "validation&test": 0}
    assert df.loc[df["date"] == "2026-01-31", "split"].item() == "train"
    assert df.loc[df["date"] == "2026-02-01", "split"].item() == "validation"
    with pytest.raises(SplitError):  # overlapping configuration is rejected
        parse_ranges({"train": ["2026-01-01", "2026-02-01"], "validation": ["2026-02-01", "2026-02-28"],
                      "test": ["2026-03-01", "2026-03-31"]})
    with pytest.raises(SplitError):  # a date outside every range is rejected, never silently dropped
        assign_split(pd.Series(pd.to_datetime(["2026-04-01"])), ranges)


# ----------------------------------------------------------------------------- Option 2 / Option 1
def frame(**lags):
    row = {"route": "A", "date": pd.Timestamp(MON), "daytype": "W", "rides": 50, "split": "train",
           "seasonal_lag_observations": 0, "past_four_same_weekdays_mean": pd.NA,
           "scheduled_trips": 10, "scheduled_service_hours": 5.0}
    for k in LAGS:
        row[f"lag_{k}d_boardings"] = lags.get(f"l{k}", pd.NA)
    df = pd.DataFrame([row])
    for k in LAGS:
        df[f"lag_{k}d_boardings"] = df[f"lag_{k}d_boardings"].astype("Int64")
    return df


def test_option_2_fills_only_28_day_lag_with_flag():
    df = frame(l1=10, l7=70, l14=140, l21=210)
    df["seasonal_lag_observations"] = 3
    p2 = prepare(df, "option_2", HOLIDAYS, with_schedule=False).iloc[0]
    assert p2["rides_28_days_before"] == pytest.approx(140)  # (70 + 140 + 210) / 3
    assert p2["rides_28_days_before_available"] == 0 and p2["eligible"]
    assert p2["available_same_weekday_observations"] == 3  # counted BEFORE filling, unchanged
    assert p2["rides_7_days_before"] == 70  # existing values preserved
    p1 = prepare(df, "option_1", HOLIDAYS, with_schedule=False).iloc[0]
    assert not p1["eligible"] and p1["withheld_reason"] == "missing_rides_28_days_before"
    assert pd.isna(p1["rides_28_days_before"])  # option 1 never fills


def test_option_2_keeps_original_28_day_value_and_withholds_missing_required_lag():
    p = prepare(frame(l1=1, l7=7, l14=14, l21=21, l28=28), "option_2", HOLIDAYS, False).iloc[0]
    assert p["rides_28_days_before"] == 28 and p["rides_28_days_before_available"] == 1 and p["eligible"]
    q = prepare(frame(l1=1, l14=14, l21=21), "option_2", HOLIDAYS, False).iloc[0]  # 7-day missing
    assert not q["eligible"] and "missing_rides_7_days_before" in q["withheld_reason"]
    r = prepare(frame(l1=1), "option_2", HOLIDAYS, False).iloc[0]  # no donor at all
    assert "no_donor_for_rides_28_days_before" in r["withheld_reason"]
    assert r["rides"] == 50  # the target is never changed


def test_schedule_model_requires_valid_schedule_inputs():
    df = frame(l1=1, l7=7, l14=14, l21=21, l28=28)
    df["scheduled_service_hours"] = pd.array([pd.NA], dtype="Float64")
    p = prepare(df, "option_2", HOLIDAYS, with_schedule=True).iloc[0]
    assert not p["eligible"] and p["withheld_reason"] == "invalid_schedule_inputs"
    assert prepare(df, "option_2", HOLIDAYS, with_schedule=False).iloc[0]["eligible"]  # demand-only unaffected


def test_holiday_predictor_uses_calendar_not_reported_daytype():
    dates = pd.Series(pd.to_datetime(["2026-05-24", "2026-05-25", "2026-05-27"]))  # Sun, Memorial Day, Wed
    assert sunday_holiday_service_day(dates, HOLIDAYS).tolist() == [1, 1, 0]
    df = frame(l1=1, l7=7, l14=14, l21=21, l28=28)
    df["daytype"] = "U"  # the reported category says Sunday/holiday on an ordinary Monday
    p = prepare(df, "option_2", HOLIDAYS, False).iloc[0]
    assert p["is_sunday_holiday_service_day"] == 0  # the issue-time predictor ignores the target row


def test_us_federal_observed_holiday_rule():
    jul4_sat, xmas_sun, wed = date(2026, 7, 4), date(2022, 12, 25), date(2025, 12, 25)
    assert observed_date(jul4_sat, "us_federal_observed") == date(2026, 7, 3)  # Saturday -> Friday before
    assert observed_date(xmas_sun, "us_federal_observed") == date(2022, 12, 26)  # Sunday -> Monday after
    assert observed_date(wed, "us_federal_observed") == wed  # weekday holiday unchanged
    assert observed_date(jul4_sat, "actual_date") == jul4_sat
    obs = observed_holidays({jul4_sat: "Independence Day"}, "us_federal_observed")
    flags = sunday_holiday_service_day(pd.Series(pd.to_datetime(["2026-07-03", "2026-07-04"])), set(obs))
    assert flags.tolist() == [1, 0]  # the observed Friday is a Sunday-service day; the Saturday itself is not


# ----------------------------------------------------------------------------- 9.14.3 forecast schedule
def test_archive_captured_on_target_date_is_rejected_for_forecasting():
    archives = [{"snapshot_id": "may30", "captured": date(2026, 5, 30)},
                {"snapshot_id": "jul11", "captured": date(2026, 7, 11)}]
    jul11 = date(2026, 7, 11)
    assert select_snapshot(jul11, archives) == "jul11"  # descriptive selection unchanged
    assert select_forecast_snapshot(jul11, archives) == "may30"  # same-day capture not yet usable
    assert select_forecast_snapshot(date(2026, 7, 12), archives) == "jul11"
    assert select_forecast_snapshot(date(2026, 5, 30), archives) is None  # nothing captured before
    assert archive_available_from(jul11) == date(2026, 7, 12)
