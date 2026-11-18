"""Stage 4a checks on the REAL saved artifacts (skipped until train_stage4a.py has been run).

These re-read files only; they never refit or rescore anything on the test period.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from analytics.features.naming import DEMAND_FEATURES, REQUIRED, SERVICE_FEATURES
from analytics.models.regressors import make_predictor
from analytics.reconstruction.build_stage2 import sha256

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts" / "stage4a"
pytestmark = pytest.mark.skipif(not (ART / "model_manifest.json").exists(), reason="Stage 4a not trained yet")


@pytest.fixture(scope="module")
def manifest():
    return json.loads((ART / "model_manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def feature_rows(manifest):
    path = ROOT / "data" / "processed" / manifest["data_version"] / "feature_rows.csv"
    assert sha256(path) == manifest["input_fingerprints"]["feature_rows.csv"]
    fr = pd.read_csv(path, dtype={"route": str}, parse_dates=["date"])
    fr["eligible"] = fr["eligible"].astype(bool)
    return fr


def test_split_counts_equal_the_notebook_reference(feature_rows):
    nref = json.loads((ROOT / "analytics" / "config" / "sources.json").read_text(encoding="utf-8"))["notebook_reference"]
    for split, ref in nref["split_rows"].items():
        g = feature_rows[feature_rows["split"] == split]
        assert (len(g), int(g["eligible"].sum())) == (ref["target"], ref["eligible"])


def test_every_saved_file_is_under_20_mb_and_unchanged(manifest):
    limit = manifest["settings"]["max_model_file_bytes"]
    assert manifest["files"]
    for rel, info in manifest["files"].items():
        path = ART / rel
        assert path.stat().st_size == info["compressed_bytes"] < limit, rel
        assert sha256(path) == info["sha256"], rel
        assert info["compress"] == 3


def test_compressed_models_reproduce_stored_validation_predictions_exactly(manifest, feature_rows):
    stored = pd.read_csv(ART / "validation_predictions.csv", dtype={"route": str}, parse_dates=["date"])
    assert sha256(ART / "validation_predictions.csv") == manifest["validation_predictions_sha256"]
    val = feature_rows[(feature_rows["split"] == "validation") & feature_rows["eligible"]]
    for name, columns in [("ridge_demand", DEMAND_FEATURES), ("rf_demand", DEMAND_FEATURES),
                          ("ridge_service", SERVICE_FEATURES), ("rf_service", SERVICE_FEATURES)]:
        s = stored[stored["method"] == name]
        rows = s[["route", "date"]].merge(val, on=["route", "date"], how="left", validate="one_to_one")
        predict = make_predictor(joblib.load(ART / "models" / f"{name}.joblib"), columns,
                                 manifest["settings"]["prediction_floor"])
        assert np.array_equal(predict(rows), s["prediction"].to_numpy()), name


def test_only_eligible_rows_were_predicted(manifest, feature_rows):
    stored = pd.read_csv(ART / "validation_predictions.csv", dtype={"route": str}, parse_dates=["date"])
    eligible = feature_rows[(feature_rows["split"] == "validation") & feature_rows["eligible"]]
    for _, s in stored.groupby("method"):
        assert len(s) == len(eligible)
        assert set(zip(s["route"], s["date"])) == set(zip(eligible["route"], eligible["date"]))
    assert (stored["prediction"] >= 0).all()  # the floor


def test_serving_bundle_and_contract(manifest):
    bundle = joblib.load(ART / "models" / "serving_bundle.joblib")
    assert bundle["selected_method"] == manifest["selected_method"]
    assert bundle["required_fields"] == REQUIRED
    if bundle["pipeline_file"] is None:
        assert bundle["baseline_rule"] in ("boardings_7d_ago", "seasonal_mean")
    else:
        assert (ART / bundle["pipeline_file"]).exists() and bundle["feature_columns"] in (DEMAND_FEATURES, SERVICE_FEATURES)
    contract = json.loads((ART / "feature_contract.json").read_text(encoding="utf-8"))
    assert sha256(ART / "feature_contract.json") == manifest["feature_contract"]["sha256"]
    assert contract["demand_features"] == DEMAND_FEATURES and contract["service_features"] == SERVICE_FEATURES
    assert manifest["frozen_at"] <= manifest["test_scored_at"]
