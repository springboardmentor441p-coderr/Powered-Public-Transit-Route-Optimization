"""Step 33: Ridge and Random Forest pipelines (notebook step 23, spec 9.10.1 steps 3-4).

One sklearn Pipeline holds the whole learned state, so the backend loads ONE object and never refits by hand:
  route    -> OneHotEncoder(handle_unknown="ignore"): an unseen route gets an all-zero encoding (no crash, no
              route-specific learning; its own history and schedule still drive the forecast)
  numeric  -> StandardScaler
  model    -> Ridge(alpha) or RandomForestRegressor(n_estimators, max_depth, min_samples_leaf, random_state)
`fit` sees training rows only, so the encoder's categories and the scaler's means/scales come from training data.
Predictions are floored at 0 (a negative count of boardings is impossible), as specified before evaluation.
"""
from __future__ import annotations

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from analytics.features.naming import DEMAND_FEATURES, SERVICE_FEATURES

# name -> (model kind, input columns); the notebook's four candidates, in the notebook's order
MODEL_CANDIDATES = {
    "ridge_demand": ("ridge", DEMAND_FEATURES),
    "rf_demand": ("rf", DEMAND_FEATURES),
    "ridge_service": ("ridge", SERVICE_FEATURES),
    "rf_service": ("rf", SERVICE_FEATURES),
}


def make_regressor(kind: str, columns: list[str], cfg: dict) -> Pipeline:
    numeric = [c for c in columns if c != "route"]
    preprocess = ColumnTransformer([
        ("route", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["route"]),
        ("numeric", StandardScaler(), numeric)])
    if kind == "ridge":
        model = Ridge(alpha=cfg["ridge"]["alpha"])
    elif kind == "rf":
        rf = cfg["random_forest"]
        model = RandomForestRegressor(n_estimators=rf["n_estimators"], max_depth=rf["max_depth"],
                                      min_samples_leaf=rf["min_samples_leaf"], random_state=cfg["seed"],
                                      n_jobs=rf.get("n_jobs"))
    else:
        raise ValueError(f"unknown model kind {kind}")
    return Pipeline([("preprocess", preprocess), ("model", model)])


def training_rows(features):
    """The ONLY rows any learned state may see: eligible rows of the training split."""
    return features.loc[features["eligible"].astype(bool) & features["split"].eq("train")]


def fit_candidates(features, cfg: dict) -> dict:
    """Fit the four model candidates on training rows only. Validation/test rows are never passed to fit."""
    train = training_rows(features)
    out = {}
    for name, (kind, columns) in MODEL_CANDIDATES.items():
        pipe = make_regressor(kind, columns, cfg).fit(train[columns], train["rides"])
        out[name] = {"kind": kind, "columns": list(columns), "pipeline": pipe,
                     "predict": make_predictor(pipe, columns, cfg.get("prediction_floor", 0.0))}
    return out


def make_predictor(pipeline: Pipeline, columns: list[str], floor: float = 0.0):
    def predict(frame):
        return np.maximum(pipeline.predict(frame[columns]), floor)
    return predict
