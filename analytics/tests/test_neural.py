"""Stage 4b correctness cases (an additional modelling experiment) on tiny synthetic data:
sequences, fairness of the row parts and scalers, determinism, exact reload, floor, batch independence."""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
import torch

from analytics.features.naming import LAG_MODEL, LAGS
from analytics.models import neural as N
from analytics.models.sequences import SequenceGuardError, build_sequences, check_against_lags

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / "analytics" / "config" / "neural.json").read_text(encoding="utf-8"))


def cfg(epochs=3, patience=None):
    c = copy.deepcopy(BASE)
    c["training"]["max_epochs"] = epochs
    if patience is not None:
        c["training"]["early_stopping_patience"] = patience
    return c


def history(routes=("A", "B"), start="2025-12-01", end="2026-05-31", seed=0, gaps=()):
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, end)
    h = pd.DataFrame([(r, d, float(rng.integers(50, 500))) for r in routes for d in days],
                     columns=["route", "date", "rides"])
    drop = h.set_index(["route", "date"]).index.isin([(r, pd.Timestamp(d)) for r, d in gaps])
    return h[~drop].reset_index(drop=True)


def rows_from(hist, start="2026-01-01", train_end="2026-03-31"):
    r = hist[hist["date"] >= start].copy()
    r["split"] = np.where(r["date"] <= train_end, "train", "validation")
    r["eligible"] = True
    r["excluded_reason"] = np.nan
    r["day_of_week"] = r["date"].dt.day_of_week
    r["month"] = r["date"].dt.month
    r["is_weekend"] = r["day_of_week"].ge(5).astype(int)
    r["is_sunday_like_day"] = r["day_of_week"].eq(6).astype(int)
    return r.reset_index(drop=True)


def inputs(prep, rows, hist):
    raw, obs = build_sequences(rows, hist)
    seq, static = prep.transform(rows, raw, obs)
    return seq, static, prep.scale_target(rows["rides"])


def fitted(c, hist, rows):
    fit, stop = N.training_parts(rows, c)
    prep = N.NeuralPreprocessor().fit(fit, c)
    return prep, inputs(prep, fit, hist), inputs(prep, stop, hist)


# ----------------------------------------------------------------------------- sequences
def test_gap_is_marked_missing_not_copied_from_previous_day():
    hist = history(gaps=[("A", "2026-02-09")])
    target = pd.DataFrame({"route": ["A"], "date": [pd.Timestamp("2026-02-10")]})
    raw, obs = build_sequences(target, hist)
    assert np.isnan(raw[0, -1]) and obs[0, -1] == 0  # D-1 = the gap
    prev = hist[(hist["route"] == "A") & (hist["date"] == "2026-02-08")]["rides"].item()
    assert raw[0, -2] == prev and obs[0, -2] == 1  # D-2 is its own day, not shifted


def test_recorded_zero_is_observed_and_differs_from_the_placeholder():
    hist = history()
    hist.loc[(hist["route"] == "A") & (hist["date"] == "2026-02-09"), "rides"] = 0.0
    rows = rows_from(hist)
    c = cfg()
    prep = N.NeuralPreprocessor().fit(N.training_parts(rows, c)[0], c)
    target = rows[(rows["route"] == "A") & (rows["date"] == "2026-02-10")]
    raw, obs = build_sequences(target, hist)
    assert raw[0, -1] == 0.0 and obs[0, -1] == 1
    seq, _ = prep.transform(target, raw, obs)
    assert seq[0, -1, 0].item() != c["sequence"]["missing_placeholder_scaled"]  # scaled 0 boardings != training mean
    assert seq[0, -1, 1].item() == 1.0


def test_target_day_and_later_never_change_the_window():
    hist = history()
    target = pd.DataFrame({"route": ["A", "B"], "date": pd.to_datetime(["2026-03-15", "2026-03-15"])})
    before, _ = build_sequences(target, hist)
    changed = hist.copy()
    changed.loc[changed["date"] >= "2026-03-15", "rides"] = 1e9
    after, _ = build_sequences(target, changed)
    assert np.array_equal(before, after, equal_nan=True)


def test_guard_catches_a_window_shifted_by_one_day():
    hist = history(gaps=[("A", "2026-02-01"), ("B", "2026-02-20")])
    rows = rows_from(hist)
    raw, _ = build_sequences(rows, hist)
    for k in LAGS:  # lag columns built independently of the window: exact date D-k
        lookup = hist.assign(date=hist["date"] + pd.Timedelta(days=k)).rename(columns={"rides": LAG_MODEL[k]})
        rows = rows.merge(lookup, on=["route", "date"], how="left")
    check_against_lags(rows, raw)  # correct window passes
    shifted = np.roll(raw, 1, axis=1)
    with pytest.raises(SequenceGuardError):
        check_against_lags(rows, shifted)


# ----------------------------------------------------------------------------- fairness
def test_fit_and_stop_parts_cover_training_only_and_refuse_validation_rows():
    rows = rows_from(history())
    c = cfg()
    fit, stop = N.training_parts(rows, c)
    es = c["periods"]["early_stopping"]
    assert fit["date"].max() < pd.Timestamp(es["start"]) <= stop["date"].min()
    assert stop["date"].max() == pd.Timestamp(es["end"])
    assert len(fit) + len(stop) == int((rows["split"] == "train").sum())
    assert not set(fit.index) & set(stop.index)
    with pytest.raises(N.FairnessError):
        N.NeuralPreprocessor().fit(rows, c)  # includes validation rows


def test_preprocessor_learns_only_from_the_fit_part():
    hist = history(routes=("A", "B", "C"))
    rows = rows_from(hist)
    c = cfg()
    fit, _ = N.training_parts(rows, c)
    p1 = N.NeuralPreprocessor().fit(fit, c)
    other = rows.copy()
    later = other["date"] >= c["periods"]["early_stopping"]["start"]
    other.loc[later, "rides"] *= 1000  # stop part and validation only
    other.loc[later & other["route"].eq("C"), "route"] = "D"
    p2 = N.NeuralPreprocessor().fit(N.training_parts(other, c)[0], c)
    assert (p1.mean, p1.std) == (p2.mean, p2.std)
    assert list(p1.encoder.categories_[0]) == list(p2.encoder.categories_[0]) == ["A", "B", "C"]
    assert np.array_equal(p1.calendar.mean_, p2.calendar.mean_)
    assert p1.mean == pytest.approx(fit["rides"].mean())


# ----------------------------------------------------------------------------- training and saving
@pytest.mark.parametrize("name", N.ARCHITECTURES)
def test_training_twice_gives_bit_identical_weights(name):
    hist = history()
    rows = rows_from(hist)
    c = cfg(epochs=3)
    prep, fit_in, stop_in = fitted(c, hist, rows)
    m1, h1, _ = N.train_network(name, prep, fit_in, stop_in, c)
    m2, h2, _ = N.train_network(name, prep, fit_in, stop_in, c)
    assert h1 == h2
    for (k1, v1), (k2, v2) in zip(m1.state_dict().items(), m2.state_dict().items()):
        assert k1 == k2 and torch.equal(v1, v2), k1


@pytest.mark.parametrize("name", N.ARCHITECTURES)
def test_saved_network_reloads_and_reproduces_predictions_exactly(name, tmp_path):
    hist = history(routes=("A", "B", "NEW"))
    rows = rows_from(hist)
    c = cfg(epochs=2)
    train_rows = rows[rows["route"] != "NEW"]  # NEW is unseen in training
    prep, fit_in, stop_in = fitted(c, hist, train_rows)
    model, _, summary = N.train_network(name, prep, fit_in, stop_in, c)
    probe = rows[rows["split"] == "validation"]
    before = N.make_nn_predictor(model, prep, hist)(probe)
    path = tmp_path / f"{name}.joblib"
    joblib.dump(N.network_payload(name, model, prep, c, summary), path, compress=3)
    buf = io.BytesIO()
    joblib.dump(N.network_payload(name, model, prep, c, summary), buf)
    assert 0 < path.stat().st_size < 20_000_000 and buf.tell() > 0
    m2, p2 = N.load_network(joblib.load(path))
    after = N.make_nn_predictor(m2, p2, hist)(probe)
    assert np.array_equal(before, after)  # exact, not approximate
    assert np.isfinite(after[probe["route"].eq("NEW").to_numpy()]).all()  # unseen route still predicts


def test_predictions_are_floored_at_zero():
    hist = history()
    rows = rows_from(hist)
    c = cfg()
    prep = N.NeuralPreprocessor().fit(N.training_parts(rows, c)[0], c)
    model = N.make_network("mlp", prep.length, prep.static_dim, c).eval()
    with torch.no_grad():
        model.net[-1][-1].bias.fill_(-1e6)  # force very negative outputs
    preds = N.make_nn_predictor(model, prep, hist)(rows.head(20))
    assert (preds == 0).all()


@pytest.mark.parametrize("name", N.ARCHITECTURES)
def test_prediction_does_not_depend_on_how_rows_are_grouped(name):
    hist = history()
    rows = rows_from(hist)
    c = cfg(epochs=1)
    prep, fit_in, stop_in = fitted(c, hist, rows)
    model, _, _ = N.train_network(name, prep, fit_in, stop_in, c)
    predict = N.make_nn_predictor(model, prep, hist)
    full = predict(rows)
    assert np.array_equal(predict(rows.iloc[[77]]), full[[77]])
    assert np.array_equal(predict(rows.iloc[30:140]), full[30:140])
    assert np.array_equal(predict(rows.iloc[::-1]), full[::-1])


def test_early_stopping_stops_and_restores_the_best_epoch():
    hist = history()
    rows = rows_from(hist)
    c = cfg(epochs=60, patience=3)
    prep, fit_in, stop_in = fitted(c, hist, rows)
    model, hist_rows, summary = N.train_network("mlp", prep, fit_in, stop_in, c)
    losses = [h["stop_loss"] for h in hist_rows]
    assert summary["epochs_run"] == len(hist_rows) < 60  # random targets: stop loss cannot keep improving
    assert summary["best_epoch"] == int(np.argmin(losses)) + 1
    assert summary["epochs_run"] - summary["best_epoch"] == 3
    with torch.no_grad():
        restored = float(torch.nn.MSELoss()(model(stop_in[0], stop_in[1]), stop_in[2]))
    assert restored == pytest.approx(summary["best_stop_loss"], rel=0, abs=1e-7)
