"""Integration checks on the real Stage 2 outputs (skipped until build_stage2.py has been run).

These check invariants (identities, uniqueness, missing-not-zero, one snapshot per date). They deliberately do
NOT assert the spec's reference numbers; the quality report compares those without forcing them.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = sorted((ROOT / "data" / "processed").glob("cta_ref__*/manifest.json"))
pytestmark = pytest.mark.skipif(not VERSIONS, reason="no Stage 2 data version built yet")


@pytest.fixture(scope="module")
def out():
    vdir = VERSIONS[-1].parent
    read = lambda n: pd.read_csv(vdir / n, dtype={"route": str, "route_id": str})  # noqa: E731
    return {
        "manifest": json.loads((vdir / "manifest.json").read_text(encoding="utf-8")),
        "schedule": read("expanded_scheduled_route_day_service.csv"),
        "matched": read("expanded_matched_utilization.csv"),
        "rws": read("expanded_ridership_without_schedule.csv"),
        "swr": read("expanded_schedule_without_ridership.csv"),
    }


def test_identities_hold(out):
    rec = out["manifest"]["reconciliation"]
    assert len(out["schedule"]) == len(out["matched"]) + len(out["swr"])
    assert rec["ridership_observations"] == len(out["matched"]) + len(out["rws"])


def test_keys_unique_and_sets_disjoint(out):
    keys = {k: set(zip(df["route"], df["date"])) for k, df in out.items() if k != "manifest"}
    for k in ["schedule", "matched", "rws", "swr"]:
        assert len(keys[k]) == len(out[k]), f"{k} has duplicate route/date keys"
    assert keys["matched"] | keys["swr"] == keys["schedule"]
    assert not keys["matched"] & keys["rws"] and not keys["rws"] & keys["schedule"]


def test_one_snapshot_per_date(out):
    assert (out["schedule"].groupby("date")["snapshot_id"].nunique() == 1).all()


def test_schedule_without_ridership_is_missing_not_zero(out):
    assert out["swr"]["rides"].isna().all()
    assert (out["rws"]["rides"].notna()).all() and (out["matched"]["rides"].notna()).all()


def test_hours_missing_exactly_when_durations_incomplete(out):
    s = out["schedule"]
    assert (s["scheduled_service_hours"].isna() == ~s["duration_complete"]).all()
    assert (s["scheduled_trips"] > 0).all()
