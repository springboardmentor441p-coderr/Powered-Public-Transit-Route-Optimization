"""Stage 3 checks on the real feature outputs (skipped until build_stage3.py has been run).

The worked example (spec 9.9.3) is asserted exactly because it is a definition of the calculation, not a count
that could legitimately change with a newer export. Reference COUNTS are compared only in the quality report.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from analytics.features.naming import LAG_EXPORT
from analytics.features.schema import D, M, export_columns
from analytics.features.splits import date_overlap

ROOT = Path(__file__).resolve().parents[2]
DIRS = sorted((ROOT / "data" / "processed").glob("cta_ref__*/features__delay*d/features_manifest.json"))
pytestmark = pytest.mark.skipif(not DIRS, reason="no Stage 3 feature version built yet")


@pytest.fixture(scope="module")
def out():
    vdir = DIRS[-1].parent
    read = lambda n: pd.read_csv(vdir / n, dtype={"route": str}, parse_dates=["date"])  # noqa: E731
    return {"daily": read(D), "matched": read(M), "fi": read("forecast_schedule_inputs.csv"),
            "elig": read("policy_eligibility_matched.csv"),
            "manifest": json.loads((vdir / "features_manifest.json").read_text(encoding="utf-8"))}


def test_spec_worked_example_route_1_2024_08_01(out):
    r = out["daily"][(out["daily"]["route"] == "1") & (out["daily"]["date"] == "2024-08-01")]
    assert len(r) == 1
    r = r.iloc[0]
    assert (r["rides"], r["day_of_week"]) == (990, 3)
    assert [r[LAG_EXPORT[k]] for k in (1, 7, 14, 21)] == [1111, 1219, 1134, 1040]
    assert pd.isna(r["lag_28d_boardings"])
    assert r["seasonal_lag_observations"] == 3
    assert r["past_four_same_weekdays_mean"] == pytest.approx((1219 + 1134 + 1040) / 3) == pytest.approx(1131)


def test_exact_columns(out):
    assert list(out["daily"].columns) == export_columns(D) and len(out["daily"].columns) == 16
    assert list(out["matched"].columns) == export_columns(M) and len(out["matched"].columns) == 22


def test_real_splits_have_no_date_overlap(out):
    for t in ["daily", "matched"]:
        assert sum(date_overlap(out[t]).values()) == 0


def test_lags_are_exact_date_lookups(out):
    d = out["daily"].set_index(["route", "date"])["rides"]
    sample = out["daily"].sample(2000, random_state=0)
    for k, c in LAG_EXPORT.items():
        expect = [d.get((r, t - pd.Timedelta(days=k))) for r, t in zip(sample["route"], sample["date"])]
        for got, exp, t in zip(sample[c], expect, sample["date"]):
            if t - pd.Timedelta(days=k) < pd.Timestamp("2024-08-01"):
                continue  # earlier history is outside this table; checked by the synthetic tests
            assert (pd.isna(got) and exp is None) or got == exp


def test_forecast_inputs_never_use_same_day_archive(out):
    fi = out["fi"].dropna(subset=["forecast_snapshot"])
    avail = pd.to_datetime(fi["forecast_archive_available_from"])
    assert (avail <= fi["date"]).all()


def test_option_2_never_less_coverage_than_option_1(out):
    e = out["elig"]
    assert not (e["eligible_option_1"] & ~e["eligible_option_2"]).any()
