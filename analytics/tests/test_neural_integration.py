"""Stage 4b checks on the REAL saved networks (an additional modelling experiment; skipped until
train_stage4b.py has been run). These re-read files only; they never retrain or rescore the test period."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from analytics.models import neural as N
from analytics.models.train_stage4b import load_history
from analytics.reconstruction.build_stage2 import sha256

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts" / "stage4b"
pytestmark = pytest.mark.skipif(not (ART / "model_manifest.json").exists(), reason="Stage 4b not trained yet")


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


@pytest.fixture(scope="module")
def history(manifest):
    features_dir = ROOT / "data" / "processed" / manifest["data_version"]
    fmanifest = json.loads((features_dir / "features_manifest.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "analytics" / "config" / "sources.json").read_text(encoding="utf-8"))
    hist, rid = load_history(ROOT / "data" / "raw" / "source_register.csv", sources, fmanifest,
                             pd.Timestamp("2026-07-31"))
    assert rid == manifest["input_fingerprints"]["ridership"]
    return hist


def test_every_saved_network_is_under_20_mb_compressed_and_unchanged(manifest):
    limit = manifest["settings"]["max_model_file_bytes"]
    assert set(manifest["files"]) == {f"models/{a}.joblib" for a in N.ARCHITECTURES}
    for rel, info in manifest["files"].items():
        path = ART / rel
        assert path.stat().st_size == info["compressed_bytes"] < limit, rel
        assert info["compressed_bytes"] <= info["uncompressed_bytes"], rel
        assert sha256(path) == info["sha256"], rel
        assert info["compress"] == 3


def test_saved_files_hold_no_run_varying_values(manifest):
    for rel in manifest["files"]:
        payload = joblib.load(ART / rel)
        assert "train_seconds" not in payload["summary"], rel  # clock time lives in the manifest only
        assert set(payload) == {"format", "architecture", "architecture_config", "length", "static_dim", "state",
                                "preprocessor", "summary", "seed", "artifact_version", "torch_version"}, rel


def test_reloaded_networks_reproduce_stored_validation_predictions_exactly(manifest, feature_rows, history):
    stored = pd.read_csv(ART / "validation_predictions.csv", dtype={"route": str}, parse_dates=["date"])
    assert sha256(ART / "validation_predictions.csv") == manifest["validation_predictions_sha256"]
    N.set_deterministic(manifest["settings"])
    val = feature_rows[(feature_rows["split"] == "validation") & feature_rows["eligible"]]
    assert len(val) == 6560
    for name in N.ARCHITECTURES:
        model, prep = N.load_network(joblib.load(ART / "models" / f"{name}.joblib"))
        preds = N.make_nn_predictor(model, prep, history, manifest["settings"]["prediction_floor"])(val)
        s = val[["route", "date"]].merge(stored[stored["method"] == name], on=["route", "date"], how="left",
                                         validate="one_to_one")
        assert np.array_equal(preds, s["prediction"].to_numpy(dtype=float)), name  # exact, not approximate


def test_networks_were_fitted_on_the_fit_part_only(manifest):
    parts = {p["part"].split(" ")[0]: p for p in manifest["parts"]}
    assert parts["fit"]["eligible rows"] + parts["early"]["eligible rows"] == 13379
    assert manifest["preprocessor"]["fitted_rows"] == parts["fit"]["eligible rows"]
    es = manifest["settings"]["periods"]["early_stopping"]
    assert parts["early"]["dates"] == f"{es['start']}..{es['end']}"
    assert parts["fit"]["dates"].split("..")[1] < es["start"]


def test_stage4a_serving_bundle_is_unchanged(manifest):
    m4a = json.loads((ROOT / "artifacts" / "stage4a" / "model_manifest.json").read_text(encoding="utf-8"))
    info = m4a["files"]["models/serving_bundle.joblib"]
    assert sha256(ROOT / "artifacts" / "stage4a" / "models" / "serving_bundle.joblib") == info["sha256"]
    assert manifest["serving"].startswith("unchanged")
