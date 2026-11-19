"""Stage 5 ranking rules on tiny hand-made matched tables (spec 9.7.1, 9.7.2, 9.12, 9.19.1)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analytics.groups.profiles import (DAYTYPES, NO_DAYS, NO_SERVICE, VIEWS, schedule_with_daytype,
                                       utilization_profiles)

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads((ROOT / "analytics" / "config" / "groups.json").read_text(encoding="utf-8"))
START, END = "2026-01-01", "2026-12-31"


def days(route, n, daytype="W", rides=100, trips=10, hours=5.0, complete=True, start="2026-01-05"):
    dates = pd.date_range(start, periods=n, freq="D")
    return pd.DataFrame({"route": route, "date": dates, "daytype": daytype, "rides": rides,
                         "scheduled_trips": trips, "scheduled_service_hours": hours, "duration_complete": complete})


def profile(df, cfg=CFG):
    p = utilization_profiles(df.reset_index(drop=True), "test", START, END, cfg)
    return p.set_index(["route", "daytype"])


def test_ratios_are_ratios_of_sums_not_means_of_daily_ratios():
    a = days("R", 10, rides=100, trips=10)
    b = days("R", 10, rides=300, trips=10, start="2026-02-01")
    c = days("R", 5, rides=10, trips=1, start="2026-03-01")
    p = profile(pd.concat([a, b, c])).loc[("R", "W")]
    assert p["rides_per_scheduled_trip"] == (1000 + 3000 + 50) / (100 + 100 + 5)  # not the mean of 10, 30, 10
    assert p["observed_days"] == 25 and p["mean_daily_rides"] == 4050 / 25


def test_incomplete_hours_make_only_the_hours_metric_unavailable():
    df = pd.concat([days("R", 24), days("R", 1, complete=False, hours=np.nan, start="2026-03-01")])
    p = profile(df).loc[("R", "W")]
    assert np.isnan(p["rides_per_scheduled_hour"]) and np.isnan(p["scheduled_hours_sum"])
    assert not p["service_productivity_metric_rank_eligible"]
    assert p["service_productivity_metric_rank_reason"] == "scheduled hours incomplete on 1 day"
    assert p["rides_per_trip_rank_eligible"] and p["rides_per_trip_rank"] == 1
    df3 = pd.concat([days("R", 22), days("R", 3, complete=False, hours=np.nan, start="2026-03-01")])
    assert profile(df3).loc[("R", "W"), "service_productivity_metric_rank_reason"] == \
        "scheduled hours incomplete on 3 days"


def test_zero_denominator_is_unavailable_not_infinite():
    p = profile(days("R", 25, trips=0, hours=0.0)).loc[("R", "W")]
    assert np.isnan(p["rides_per_scheduled_trip"]) and np.isnan(p["rides_per_scheduled_hour"])
    assert p["rides_per_trip_rank_reason"] == "no positive denominator"
    assert pd.isna(p["rides_per_trip_rank"])


def test_ties_share_the_lowest_rank():
    df = pd.concat([days("A1", 25, rides=500), days("B2", 25, rides=500), days("C3", 25, rides=100),
                    days("D4", 25, rides=900)])
    r = profile(df)["observed_daily_demand_rank"].xs("W", level="daytype")
    assert r.to_dict() == {"A1": 2, "B2": 2, "C3": 4, "D4": 1}


def test_ineligible_rows_stay_unranked_with_their_count():
    df = pd.concat([days("BIG", 25), days("SMALL", 19, rides=10_000)])
    p = profile(df)
    small = p.loc[("SMALL", "W")]
    for v in VIEWS:
        assert pd.isna(small[v]) and not small[f"{v}_eligible"]
        assert small[f"{v}_reason"] == "fewer than 20 observed days (19)"
    assert p.loc[("BIG", "W"), "observed_daily_demand_rank"] == 1  # SMALL's higher demand cannot outrank it
    assert small["observed_days"] == 19


def test_weekday_only_route_gets_saturday_and_sunday_rows_with_zero_days_and_missing_sums():
    p = profile(days("WKDAY", 25))
    assert set(p.loc["WKDAY"].index) == set(DAYTYPES)
    for dt in ["A", "U"]:
        r = p.loc[("WKDAY", dt)]
        assert r["observed_days"] == 0  # a real count
        for c in ["rides_sum", "scheduled_trips_sum", "scheduled_hours_sum", "mean_daily_rides",
                  "rides_per_scheduled_trip", "rides_per_scheduled_hour"]:
            assert pd.isna(r[c]), c  # no observations: missing, never 0
        for v in VIEWS:
            assert pd.isna(r[v]) and not r[f"{v}_eligible"] and r[f"{v}_reason"] == NO_DAYS


def test_zero_day_reason_separates_no_scheduled_service_from_no_ridership_record():
    """WKDAY never runs Saturdays; GHOST has Saturday trips scheduled but no ridership record on them."""
    wk = days("WKDAY", 25)
    gh = days("GHOST", 25)
    other_sat = days("OTHER", 3, daytype="A", start="2026-03-07")  # gives the Saturday dates their day type
    matched = pd.concat([wk, gh, other_sat, days("OTHER", 25, start="2026-04-01")]).reset_index(drop=True)
    sched = pd.concat([
        matched[["route", "date", "scheduled_trips"]],
        pd.DataFrame({"route": "GHOST", "date": other_sat["date"], "scheduled_trips": 4}),  # scheduled, no rides
        pd.DataFrame({"route": "WKDAY", "date": other_sat["date"], "scheduled_trips": 0}),  # explicit zero trips
    ])
    s = schedule_with_daytype(sched, matched)
    p = utilization_profiles(matched, "test", START, END, CFG, s).set_index(["route", "daytype"])
    assert p.loc[("WKDAY", "A"), "scheduled_service_days"] == 0
    assert p.loc[("WKDAY", "A"), "observed_daily_demand_rank_reason"] == NO_SERVICE
    assert p.loc[("GHOST", "A"), "scheduled_service_days"] == 3 and p.loc[("GHOST", "A"), "observed_days"] == 0
    assert p.loc[("GHOST", "A"), "observed_daily_demand_rank_reason"] == NO_DAYS
    assert p.loc[("OTHER", "A"), "observed_days"] == 3  # a matched day type keeps its count-based reason
    assert p.loc[("OTHER", "A"), "observed_daily_demand_rank_reason"] == "fewer than 20 observed days (3)"


def test_clustering_weekend_gate_passing_does_not_make_the_route_rankable():
    """Spec 9.19.1: 10 Saturdays pass the clustering weekend gate (8) but fail the ranking gate (20)."""
    sat = days("R", 10, daytype="A", start="2026-03-01")  # dates distinct from the weekday rows
    assert 10 >= CFG["gates"]["cluster_min_weekend_days"]
    p = profile(pd.concat([days("R", 25), sat])).loc[("R", "A")]
    assert p["observed_days"] == 10
    assert not p["observed_daily_demand_rank_eligible"] and pd.isna(p["observed_daily_demand_rank"])


def test_gate_value_comes_from_config():
    cfg = copy.deepcopy(CFG)
    cfg["gates"]["ranking_min_observed_days"] = 5
    p = profile(days("R", 6), cfg).loc[("R", "W")]
    assert p["observed_daily_demand_rank"] == 1 and p["ranking_min_observed_days"] == 5


def test_rows_outside_the_period_are_not_counted():
    df = pd.concat([days("R", 25), days("R", 30, rides=10**6, start="2027-01-01")])
    p = profile(df).loc[("R", "W")]
    assert p["observed_days"] == 25 and p["rides_sum"] == 2500
