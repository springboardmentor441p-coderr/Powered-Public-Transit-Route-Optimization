"""Stage 5 clustering rules on tiny hand-made tables (spec 9.7.2, 9.11.2, 9.11.3)."""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.impute import SimpleImputer

from analytics.groups.clustering import (NOT_IN_DEV, ServiceAwareMedianImputer, assign_group, choose_k, fit,
                                         membership, model_frame, predict)
from analytics.groups.profiles import (FEW_STATUS, NO_SERVICE_STATUS, OK_STATUS, route_profiles,
                                       schedule_with_daytype, select_features)

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads((ROOT / "analytics" / "config" / "groups.json").read_text(encoding="utf-8"))
START, END = "2026-01-01", "2026-06-30"


def days(route, n, daytype="W", rides=100.0, trips=10, hours=5.0, complete=True, start="2026-01-05", step=1):
    dates = pd.date_range(start, periods=n, freq=f"{step}D")
    r = rides if np.ndim(rides) else [rides] * n
    return pd.DataFrame({"route": route, "date": dates, "daytype": daytype, "rides": r,
                         "scheduled_trips": trips, "scheduled_service_hours": hours, "duration_complete": complete})


def build(matched, extra_schedule=None):
    matched = matched.reset_index(drop=True)
    sched = matched[["route", "date", "scheduled_trips"]]
    if extra_schedule is not None:
        sched = pd.concat([sched, extra_schedule])
    return route_profiles(matched, schedule_with_daytype(sched, matched), START, END, CFG).set_index("route")


def test_base_gate_leaves_the_route_ungrouped_with_a_reason():
    p = build(pd.concat([days("OK", 20), days("SHORT", 19, start="2026-03-01")]))
    assert p.loc["OK", "base_eligible"] and pd.isna(p.loc["OK", "ungrouped_reason"])
    assert not p.loc["SHORT", "base_eligible"]
    assert p.loc["SHORT", "ungrouped_reason"] == "fewer than 20 matched weekdays (19) in the profile period"


def test_weekend_statuses_structural_zero_unavailable_and_measured():
    sat_dates = days("X", 10, daytype="A", start="2026-04-04", step=7)  # 10 Saturdays
    matched = pd.concat([
        days("NOSAT", 25),                                               # never scheduled on Saturdays
        days("FEW", 25), days("FEW", 5, daytype="A", rides=50.0, start="2026-04-04", step=7),
        days("FULL", 25), days("FULL", 10, daytype="A", rides=40.0, start="2026-04-04", step=7),
    ])
    few_extra = pd.DataFrame({"route": "FEW", "date": sat_dates["date"].iloc[5:], "scheduled_trips": 4})
    p = build(matched, few_extra)
    assert p.loc["NOSAT", "saturday_service_status"] == NO_SERVICE_STATUS
    assert p.loc["NOSAT", "saturday_to_weekday_rides_ratio"] == 0.0  # structural zero: no buses ran
    assert p.loc["FEW", "saturday_service_status"] == FEW_STATUS
    assert p.loc["FEW", "saturday_observed_days"] == 5 and p.loc["FEW", "saturday_scheduled_days"] == 10
    assert np.isnan(p.loc["FEW", "saturday_to_weekday_rides_ratio"])  # service ran: missing, never 0
    assert p.loc["FULL", "saturday_service_status"] == OK_STATUS
    assert p.loc["FULL", "saturday_to_weekday_rides_ratio"] == pytest.approx(40 / 100)


def test_cv_is_undefined_when_mean_weekday_rides_is_zero():
    p = build(days("ZERO", 25, rides=0.0))
    assert np.isnan(p.loc["ZERO", "weekday_rides_cv"])
    assert p.loc["ZERO", "mean_weekday_rides"] == 0.0  # a recorded 0 stays 0


def test_duration_and_hours_ratio_need_complete_weekday_durations():
    ok = build(days("R", 25, trips=10, hours=5.0))
    assert ok.loc["R", "mean_weekday_trip_duration_minutes"] == pytest.approx(30.0)  # 60 * 125 h / 250 trips
    assert ok.loc["R", "weekday_rides_per_scheduled_hour"] == pytest.approx(2500 / 125)
    bad = build(pd.concat([days("R", 24), days("R", 1, complete=False, hours=np.nan, start="2026-03-01")]))
    assert np.isnan(bad.loc["R", "mean_weekday_trip_duration_minutes"])
    assert np.isnan(bad.loc["R", "weekday_rides_per_scheduled_hour"])
    assert bad.loc["R", "weekday_incomplete_duration_days"] == 1


def test_profile_period_ignores_later_rows():
    early = days("R", 25)
    late = days("R", 30, rides=1e6, start="2026-08-01")
    p = build(pd.concat([early, late]))
    assert p.loc["R", "weekday_observed_days"] == 25 and p.loc["R", "mean_weekday_rides"] == 100.0


def synthetic_profiles(n=40, seed=0):
    rng = np.random.default_rng(seed)
    rides = rng.uniform(200, 20000, n)
    return pd.DataFrame({
        "route": [f"R{i}" for i in range(n)], "base_eligible": True,
        "mean_weekday_rides": rides,
        "weekday_rides_cv": rng.uniform(0.05, 0.4, n),
        "saturday_to_weekday_rides_ratio": rng.uniform(0, 0.9, n),
        "sunday_holiday_to_weekday_rides_ratio": np.where(np.arange(n) < 6, np.nan, rng.uniform(0, 0.8, n)),
        "mean_weekday_scheduled_trips": rides / 25 * rng.uniform(0.97, 1.03, n),  # nearly a copy of rides
        "weekday_rides_per_scheduled_hour": rng.uniform(10, 60, n),
        "mean_weekday_trip_duration_minutes": rng.uniform(20, 90, n)})


def test_feature_selection_drops_unavailable_and_lower_priority_correlated_features():
    sel = select_features(synthetic_profiles(), CFG)
    d = sel["decisions"].set_index("feature")
    assert not d.loc["sunday_holiday_to_weekday_rides_ratio", "kept"]  # 6 of 40 missing = 85% < 90%
    assert "85.0%" in d.loc["sunday_holiday_to_weekday_rides_ratio", "reason"]
    assert not d.loc["mean_weekday_scheduled_trips", "kept"]  # correlated with rides, lower priority
    assert "`mean_weekday_rides`" in d.loc["mean_weekday_scheduled_trips", "reason"]
    assert sel["selected"][0] == "mean_weekday_rides"
    assert "mean_weekday_trip_duration_minutes" in sel["selected"]


def test_feature_selection_uses_base_eligible_routes_only():
    p = synthetic_profiles()
    q = p.copy()
    extra = q.iloc[:5].assign(route=lambda d: d["route"] + "_x", base_eligible=False,
                              sunday_holiday_to_weekday_rides_ratio=np.nan)
    q = pd.concat([q, extra])
    cfg = copy.deepcopy(CFG)
    a, b = select_features(p, cfg), select_features(q, cfg)
    assert a["selected"] == b["selected"] and a["base_routes"] == b["base_routes"] == 40


# ----------------------------------------------------------------------------- Step 48: imputer and KMeans
SUN = "sunday_holiday_to_weekday_rides_ratio"
SUN_STATUS = "sunday_holiday_service_status"


def imputer_frame(available, n_zero, n_missing=1):
    vals = list(available) + [0.0] * n_zero + [np.nan] * n_missing
    status = [OK_STATUS] * len(available) + [NO_SERVICE_STATUS] * n_zero + [FEW_STATUS] * n_missing
    return pd.DataFrame({SUN: vals, SUN_STATUS: status})


def test_structural_zeros_do_not_affect_the_filled_median():
    few_zeros, many_zeros = imputer_frame([0.2, 0.3, 0.4, 0.5, 0.6], 3), imputer_frame([0.2, 0.3, 0.4, 0.5, 0.6], 30)
    a = ServiceAwareMedianImputer([SUN]).fit(few_zeros)
    b = ServiceAwareMedianImputer([SUN]).fit(many_zeros)
    assert a.medians_[SUN] == b.medians_[SUN] == 0.4  # median of the 5 'available' routes only
    assert a.transform(few_zeros)[-1, 0] == b.transform(many_zeros)[-1, 0] == 0.4  # the missing route's fill
    plain = SimpleImputer(strategy="median").fit(many_zeros[[SUN]])
    assert plain.statistics_[0] == 0.0  # the naive imputer WOULD have been dragged to 0 by the structural zeros
    c = ServiceAwareMedianImputer([SUN]).fit(imputer_frame([0.2, 0.3, 0.4, 0.5, 0.6, 5.0], 3))
    assert c.medians_[SUN] == pytest.approx(0.45)  # an extra 'available' route does move it: the test is sensitive


def test_structural_zeros_stay_zero_and_only_missing_values_are_filled():
    f = imputer_frame([0.2, 0.4], 2, 1)
    out = ServiceAwareMedianImputer([SUN]).fit(f).transform(f)[:, 0]
    assert out.tolist() == [0.2, 0.4, 0.0, 0.0, pytest.approx(0.3)]


def real_like_profiles(n=60, seed=3):
    p = synthetic_profiles(n, seed)
    p[SUN] = np.where(np.arange(n) < 15, 0.0, p[SUN].fillna(0.3))   # 15 routes with no Sunday service
    p[SUN_STATUS] = pd.Series(np.where(np.arange(n) < 15, NO_SERVICE_STATUS, OK_STATUS), dtype=object)
    few = n // 3  # an existing row (writing past the end would silently add a new one)
    p.loc[few, SUN], p.loc[few, SUN_STATUS] = np.nan, FEW_STATUS
    p["saturday_service_status"] = OK_STATUS
    p["ungrouped_reason"] = pd.Series([np.nan] * n, dtype=object)
    return p


FEATS = ["mean_weekday_rides", "weekday_rides_cv", SUN, "weekday_rides_per_scheduled_hour",
         "mean_weekday_trip_duration_minutes"]


def test_kmeans_refit_is_bit_identical_and_reload_assigns_identical_groups(tmp_path):
    p = real_like_profiles()
    frame = model_frame(p, FEATS, CFG)
    a, b = fit(frame, FEATS, 3, 42, CFG), fit(frame, FEATS, 3, 42, CFG)
    assert np.array_equal(a.named_steps["kmeans"].cluster_centers_, b.named_steps["kmeans"].cluster_centers_)
    path = tmp_path / "groups.joblib"
    joblib.dump(a, path, compress=3)
    assert np.array_equal(predict(joblib.load(path), frame), predict(a, frame))
    buf1, buf2 = io.BytesIO(), io.BytesIO()
    joblib.dump(a, buf1, compress=3), joblib.dump(b, buf2, compress=3)
    assert buf1.getvalue() == buf2.getvalue()  # byte-identical files from two fits


def test_pipeline_state_comes_from_development_profiles_only():
    p = real_like_profiles()
    pipe = fit(model_frame(p, FEATS, CFG), FEATS, 3, 42, CFG)
    later = p.assign(mean_weekday_rides=p["mean_weekday_rides"] * 100)  # a later period, very different
    before = pipe.named_steps["scale"].mean_.copy()
    assign_group(pipe, later, FEATS, CFG)  # assigning never refits
    assert np.array_equal(pipe.named_steps["scale"].mean_, before)


def test_choose_k_rule():
    t = pd.DataFrame({"k": [2, 3, 4, 5], "silhouette": [0.40, 0.45, 0.46, 0.50],
                      "passes_size_gate": [True, True, True, False]})
    assert choose_k(t, CFG) == 3  # best passing 0.46; smallest k within 0.02 is 3; k=5 fails the size gate
    assert choose_k(t.assign(passes_size_gate=False), CFG) is None


def test_every_route_gets_one_membership_row_with_a_reason():
    p = real_like_profiles(20)
    p.loc[0, "base_eligible"], p.loc[0, "ungrouped_reason"] = False, "fewer than 20 matched weekdays (5) in the profile period"
    labels = pd.Series(range(19), index=p["route"].iloc[1:]) % 3
    m = membership(p, labels, list(p["route"]) + ["130", "1001"], {"1001"}).set_index("route")
    assert len(m) == 22 and m.index.is_unique
    assert m.loc["R0", "group"] == "ungrouped" and "fewer than 20" in m.loc["R0", "reason"]
    assert m.loc["130", "reason"] == NOT_IN_DEV and m.loc["1001", "group"] == "ungrouped"
    assert (m.drop(["R0", "130", "1001"])["reason"] == "grouped").all()
