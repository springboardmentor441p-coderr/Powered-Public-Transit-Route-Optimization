"""Stage 4a correctness cases on small synthetic tables: scoring, withholding, encoder fit, floor, saved models."""
from __future__ import annotations

import io

import joblib
import numpy as np
import pandas as pd
import pytest

from analytics.features.naming import NO_ACTUAL_REASON, SERVICE_FEATURES
from analytics.models.baselines import baseline_predictor
from analytics.models.regressors import fit_candidates, make_predictor, make_regressor
from analytics.models.scoring import ScoringError, evaluate, score

CFG = {"seed": 42, "ridge": {"alpha": 100}, "prediction_floor": 0,
       "random_forest": {"n_estimators": 5, "max_depth": 4, "min_samples_leaf": 2, "n_jobs": 1}}


def table(n=60, seed=0, split="train", routes=("A", "B"), scale=1.0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({"route": [routes[i % len(routes)] for i in range(n)]})
    for c in SERVICE_FEATURES[1:]:
        df[c] = rng.uniform(1, 100, n) * scale
    df["rides"] = df["boardings_7d_ago"] * 1.1 + rng.normal(0, 1, n)
    df["split"], df["eligible"], df["excluded_reason"] = split, True, np.nan
    return df


# ----------------------------------------------------------------------------- scoring
def test_score_arithmetic():
    m = score([10, 20, 30], [12, 18, 30])
    assert m["MAE"] == pytest.approx(4 / 3) and m["RMSE"] == pytest.approx(np.sqrt(8 / 3))
    assert m["WAPE_percent"] == pytest.approx(100 * 4 / 60)


def test_wape_unavailable_for_zero_total_but_errors_still_computed():
    m = score([0, 0], [3, 1])
    assert m["WAPE_percent"] is None  # unavailable, not 0 and not infinity
    assert m["MAE"] == 2 and m["RMSE"] == pytest.approx(np.sqrt(5))
    empty = score([], [])
    assert empty["rows"] == 0 and empty["MAE"] is None and empty["WAPE_percent"] is None  # no rows -> unavailable


def test_withheld_rows_are_never_scored_or_predicted():
    f = pd.DataFrame({"rides": [100.0, 1e9, np.nan, 50.0], "boardings_7d_ago": [90.0, 1.0, np.nan, 50.0],
                      "seasonal_mean": [1.0] * 4, "eligible": [True, False, False, True],
                      "excluded_reason": [np.nan, "boardings_1d_ago", NO_ACTUAL_REASON, np.nan]})
    seen = []

    def spy(rows):
        seen.append(rows.index.tolist())
        return baseline_predictor("last_week")(rows)
    m, preds = evaluate(f, spy)
    assert seen == [[0, 3]]  # the predictor never saw a withheld row
    assert m["MAE"] == 5 and m["scored_rows"] == 2 and m["withheld_rows"] == 2  # the 1e9 sentinel had no effect
    assert m["withheld_by_reason"] == {"boardings_1d_ago": 1, NO_ACTUAL_REASON: 1}
    assert m["coverage"] == 0.5 and list(preds.index) == [0, 3]


def test_eligible_row_without_forecast_is_an_error():
    f = pd.DataFrame({"rides": [10.0], "eligible": [True], "excluded_reason": [np.nan]})
    with pytest.raises(ScoringError):
        evaluate(f, lambda rows: np.array([np.nan]))


def test_real_zero_actual_is_scored_missing_actual_is_not():
    f = pd.DataFrame({"rides": [0.0, np.nan], "boardings_7d_ago": [4.0, 4.0], "eligible": [True, False],
                      "excluded_reason": [np.nan, NO_ACTUAL_REASON]})
    m, _ = evaluate(f, baseline_predictor("last_week"))
    assert m["scored_rows"] == 1 and m["MAE"] == 4  # the recorded zero is a real observation
    assert m["WAPE_percent"] is None  # its total is 0, so WAPE is unavailable
    with pytest.raises(ScoringError):  # a missing actual can never be scored as if it were a value
        score([np.nan], [1.0])


# ----------------------------------------------------------------------------- learned state
def test_encoder_and_scaler_learn_only_from_training_rows():
    train = table(seed=1)
    other = pd.concat([table(30, seed=2, split="validation", routes=("Z",), scale=1000),
                       table(30, seed=3, split="test", routes=("Y",), scale=-50)], ignore_index=True)
    withheld_train = table(10, seed=4, routes=("W",), scale=500).assign(eligible=False, excluded_reason="x")
    fitted = fit_candidates(pd.concat([train, other, withheld_train], ignore_index=True), CFG)
    for name, c in fitted.items():
        pre = c["pipeline"].named_steps["preprocess"]
        assert [list(x) for x in pre.named_transformers_["route"].categories_] == [["A", "B"]], name
        numeric = [col for col in c["columns"] if col != "route"]
        assert np.allclose(pre.named_transformers_["numeric"].mean_, train[numeric].mean().to_numpy()), name
    # changing every non-training row leaves the fitted models' predictions unchanged
    changed = other.assign(rides=-1.0, boardings_7d_ago=1e6)
    refit = fit_candidates(pd.concat([train, changed, withheld_train], ignore_index=True), CFG)
    probe = table(8, seed=9)
    for name in fitted:
        assert np.array_equal(fitted[name]["predict"](probe), refit[name]["predict"](probe)), name
    # an unseen route still gets a forecast (all-zero route encoding), it does not crash
    unseen = table(3, seed=5, routes=("NEW",))
    assert np.isfinite(fitted["ridge_service"]["predict"](unseen)).all()


def test_predictions_are_floored_at_zero():
    train = table(seed=6)
    pipe = make_regressor("ridge", SERVICE_FEATURES, CFG).fit(train[SERVICE_FEATURES], train["rides"])
    low = table(5, seed=7).assign(**{c: -1000.0 for c in SERVICE_FEATURES[1:]})
    raw = pipe.predict(low[SERVICE_FEATURES])
    assert (raw < 0).all()  # the unfloored model really does go negative here
    floored = make_predictor(pipe, SERVICE_FEATURES)(low)
    assert (floored == 0).all()
    normal = table(5, seed=8)
    assert np.array_equal(make_predictor(pipe, SERVICE_FEATURES)(normal), np.maximum(pipe.predict(normal[SERVICE_FEATURES]), 0))


def test_configured_forest_predicts_repeatably():
    """With the project settings, two predict() calls give bit-identical results (multi-threaded summation did not)."""
    import json
    from pathlib import Path
    cfg = json.loads((Path(__file__).resolve().parents[1] / "config" / "models.json").read_text(encoding="utf-8"))
    small = {**cfg, "random_forest": {**cfg["random_forest"], "n_estimators": 20}}
    rf = fit_candidates(table(200, seed=12), small)["rf_service"]
    probe = table(100, seed=13)
    assert np.array_equal(rf["predict"](probe), rf["predict"](probe))


def test_compressed_models_reload_and_reproduce_predictions_exactly(tmp_path):
    fitted = fit_candidates(table(seed=10), CFG)
    probe = table(20, seed=11, routes=("A", "B", "NEW"))
    for name, c in fitted.items():
        path = tmp_path / f"{name}.joblib"
        joblib.dump(c["pipeline"], path, compress=3)
        buf = io.BytesIO()
        joblib.dump(c["pipeline"], buf)  # uncompressed size, for the report
        assert path.stat().st_size > 0 and buf.tell() > 0
        reloaded = make_predictor(joblib.load(path), c["columns"])
        assert np.array_equal(reloaded(probe), c["predict"](probe)), name  # exact, not approximate
