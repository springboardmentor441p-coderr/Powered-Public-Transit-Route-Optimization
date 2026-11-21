"""Stage 6c: GET /api/models/summary (the Data screen's model card) and the coverage import checks."""
from __future__ import annotations

import json
import math

from backend.app.routers.models import MANIFEST_4A, MANIFEST_4B, missing_words


def test_model_card_numbers_equal_the_manifests(client):
    body = client.get("/api/models/summary").json()
    a = json.loads(MANIFEST_4A.read_text(encoding="utf-8"))
    b = json.loads(MANIFEST_4B.read_text(encoding="utf-8"))
    assert body["available"] is True and body["selected"]["method"] == a["selected_method"]
    val = {m["method"]: m for m in b["validation_metrics"]}
    assert {m["method"] for m in body["methods"]} == set(val) and len(body["methods"]) == 10
    for m in body["methods"]:
        assert m["validation"]["mae"] == val[m["method"]]["MAE"] and m["label"] and "_" not in m["label"]
    maes = [m["validation"]["mae"] for m in body["methods"]]
    assert maes == sorted(maes)                                             # ordered best first
    assert body["best_baseline"]["method"] == min((k for k in val if val[k]["kind"] == "baseline"), key=lambda k: val[k]["MAE"])


def test_the_gain_over_the_best_baseline_is_computed_not_written(client):
    body = client.get("/api/models/summary").json()
    for split in ("validation", "test"):
        g = body["gain"][split]
        assert math.isclose(g["mae_reduction"], g["baseline_mae"] - g["model_mae"])
        assert math.isclose(g["mae_reduction_percent"], 100 * g["mae_reduction"] / g["baseline_mae"])
    assert body["best_network"]["beats_selected"] is False                  # no network beat the random forest
    assert "reused holdout" in body["test_status"]


def test_model_results_are_hidden_under_a_cutoff_before_the_test_period_ends(client):
    body = client.get("/api/models/summary", params={"cutoff": "2026-06-30"}).json()
    assert body["available"] is False and "after the cutoff" in body["reason"] and "methods" not in body
    assert client.get("/api/models/summary", params={"cutoff": "2026-07-31"}).json()["available"] is True


def test_withheld_reasons_are_words():
    assert missing_words("boardings_1d_ago") == "rides 1 day earlier missing"
    assert missing_words("boardings_7d_ago, boardings_28d_filled") == "rides 7 days and 28 days earlier missing"
    assert missing_words("no recorded boardings") == "no recorded rides"


def test_import_checks_have_plain_labels(client):
    q = client.get("/api/data/coverage").json()["quality"]
    checks = q["import_checks"]
    assert len(checks) == len(q["import_identities"]) and all(c["violations"] == 0 for c in checks)
    assert all(c["label"] and "_" not in c["label"] for c in checks)
