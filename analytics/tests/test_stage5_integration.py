"""Stage 5 checks on the REAL saved outputs (skipped until build_stage5.py has been run).
These re-read files only; they never refit groups or rebuild any table."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from analytics.groups import clustering as C
from analytics.groups.profiles import VIEWS, load_matched
from analytics.reconstruction.build_stage2 import sha256

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts" / "stage5"
pytestmark = pytest.mark.skipif(not (ART / "groups_manifest.json").exists(), reason="Stage 5 not built yet")


@pytest.fixture(scope="module")
def manifest():
    return json.loads((ART / "groups_manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def data_dir(manifest):
    return ROOT / "data" / "processed" / manifest["data_products"]["data_version"]


@pytest.fixture(scope="module")
def membership(data_dir):
    return pd.read_csv(data_dir / "route_group_membership.csv", dtype={"route": str, "group": str})


def test_artifact_is_under_20_mb_compressed_and_unchanged(manifest):
    info, path = manifest["file"], ART / "route_groups.joblib"
    assert path.stat().st_size == info["compressed_bytes"] < 20_000_000
    assert info["compressed_bytes"] <= info["uncompressed_bytes"] and info["compress"] == 3
    assert sha256(path) == info["sha256"]


def test_data_products_match_their_manifest(data_dir):
    dm = json.loads((data_dir / "groups_data_manifest.json").read_text(encoding="utf-8"))
    for name, rec in dm["outputs"].items():
        assert sha256(data_dir / name) == rec["sha256"], name
        assert len(pd.read_csv(data_dir / name, dtype=str)) == rec["rows"], name


def test_reloaded_pipeline_reproduces_the_saved_memberships(manifest, data_dir, membership):
    prof = pd.read_csv(data_dir / "route_profiles.csv", dtype={"route": str})
    prof["base_eligible"] = prof["base_eligible"].astype(str).eq("True")
    base = prof[prof["base_eligible"]]
    pipe = joblib.load(ART / "route_groups.joblib")
    frame = C.model_frame(base, manifest["features"], manifest["settings"])
    labels = pd.Series(C.predict(pipe, frame), index=frame.index).astype(str)
    saved = membership.set_index("route").loc[frame.index, "group"]
    assert np.array_equal(labels.to_numpy(), saved.to_numpy())


def test_group_names_equal_the_frozen_memberships(manifest, membership):
    names = json.loads((ROOT / "analytics" / "config" / "group_names.json").read_text(encoding="utf-8"))
    assert names["k"] == manifest["k"]
    for gid, g in names["groups"].items():
        frozen = set(membership.loc[membership["group"] == gid, "route"])
        assert frozen == set(g["routes"]), gid
        assert (membership.loc[membership["group"] == gid, "group_name"] == g["name"]).all()


def test_every_route_in_the_window_has_one_membership_row_with_a_reason(membership):
    assert membership["route"].is_unique
    assert membership["reason"].notna().all()
    ungrouped = membership[membership["group"] == "ungrouped"]
    assert not ungrouped["reason"].eq("grouped").any()
    assert ungrouped["group_name"].isna().all()


def test_ranking_identities_and_no_rank_on_an_ineligible_row(manifest, data_dir):
    rk = pd.read_csv(data_dir / "expanded_utilization_profiles.csv", dtype={"route": str})
    matched = load_matched(ROOT / "data" / "processed" / manifest["data_products"]["data_version"].split("/")[0]
                           / "expanded_matched_utilization.csv")
    for period, (a, b) in manifest["settings"]["periods"]["ranking_periods"].items():
        r = rk[rk["period_name"] == period]
        mm = matched[matched["date"].between(a, b) & matched["daytype"].isin(["W", "A", "U"])]
        assert int(r["rides_sum"].sum()) == int(mm["rides"].sum()), period
        assert int(r["observed_days"].sum()) == len(mm), period
        assert r.groupby("route")["daytype"].nunique().eq(3).all(), period
        for v in VIEWS:
            eligible = r[f"{v}_eligible"].astype(str).eq("True")
            assert r.loc[~eligible, v].isna().all(), (period, v)
            assert r.loc[~eligible, f"{v}_reason"].notna().all(), (period, v)
            assert r.loc[eligible, v].notna().all(), (period, v)


def test_stage4a_serving_bundle_is_unchanged():
    m4a = json.loads((ROOT / "artifacts" / "stage4a" / "model_manifest.json").read_text(encoding="utf-8"))
    info = m4a["files"]["models/serving_bundle.joblib"]
    assert sha256(ROOT / "artifacts" / "stage4a" / "models" / "serving_bundle.joblib") == info["sha256"]
