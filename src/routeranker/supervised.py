"""Module 5b - Supervised models.

* Classification (Random Forest vs XGBoost): route-hour performance class
  - Underutilized / Balanced / Overcrowded.
* Regression / forecasting (XGBoost vs Random Forest vs seasonal-profile
  baseline): hourly boardings per route, used for date-specific prediction.

Both use a chronological split: train = everything before the last
``VALIDATION_DAYS`` days, validation = the last ``VALIDATION_DAYS`` days.
"""
from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, classification_report,
                             confusion_matrix, f1_score, mean_absolute_error, mean_squared_error,
                             r2_score)
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier, XGBRegressor

from . import config as C
from .preprocessing import MODEL_FEATURES

log = logging.getLogger(__name__)
CLASS_TO_INT = {c: i for i, c in enumerate(C.CLASS_LABELS)}


def _sample(X: pd.DataFrame, y, n: int, seed: int = C.RANDOM_STATE):
    """Random row sample (without replacement) to bound training time."""
    if len(X) <= n:
        return X, y
    idx = np.random.default_rng(seed).choice(len(X), n, replace=False)
    return X.iloc[idx], (y.iloc[idx] if hasattr(y, "iloc") else y[idx])


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def classification_metrics(y_true, y_pred) -> dict:
    """Accuracy, balanced accuracy, macro/weighted F1, per-class report and confusion matrix."""
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro")),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted")),
        "report": classification_report(y_true, y_pred, labels=[0, 1, 2], target_names=C.CLASS_LABELS,
                                        output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=[0, 1, 2]).tolist(),
    }


def train_classifiers(Xtr: pd.DataFrame, ytr: pd.Series, Xva: pd.DataFrame, yva: pd.Series,
                      rf_rows: int = 400_000, xgb_rows: int = 1_500_000) -> dict:
    """Train RandomForestClassifier and XGBClassifier with class balancing,
    evaluate on the chronological validation set, return models + metrics."""
    ytr_i, yva_i = ytr.map(CLASS_TO_INT).astype(int), yva.map(CLASS_TO_INT).astype(int)
    out = {}

    Xs, ys = _sample(Xtr, ytr_i, rf_rows)
    t0 = time.time()
    rf = RandomForestClassifier(n_estimators=200, max_depth=20, min_samples_leaf=5, max_features="sqrt",
                                class_weight="balanced_subsample", n_jobs=-1, random_state=C.RANDOM_STATE)
    rf.fit(Xs, ys)
    pred = rf.predict(Xva)
    out["RandomForest"] = {"model": rf, "train_seconds": round(time.time() - t0, 1),
                           "train_rows": int(len(Xs)), **classification_metrics(yva_i, pred)}
    log.info("RF classifier macro-F1 %.3f", out["RandomForest"]["f1_macro"])

    Xs, ys = _sample(Xtr, ytr_i, xgb_rows)
    t0 = time.time()
    xgb = XGBClassifier(n_estimators=600, max_depth=8, learning_rate=0.08, subsample=0.8,
                        colsample_bytree=0.8, min_child_weight=5, reg_lambda=1.0, tree_method="hist",
                        objective="multi:softprob", eval_metric="mlogloss", n_jobs=-1,
                        random_state=C.RANDOM_STATE, early_stopping_rounds=40)
    xgb.fit(Xs, ys, sample_weight=compute_sample_weight("balanced", ys),
            eval_set=[(Xva, yva_i)], verbose=False)
    pred = xgb.predict(Xva)
    out["XGBoost"] = {"model": xgb, "train_seconds": round(time.time() - t0, 1),
                      "train_rows": int(len(Xs)), "best_iteration": int(xgb.best_iteration),
                      **classification_metrics(yva_i, pred)}
    log.info("XGB classifier macro-F1 %.3f", out["XGBoost"]["f1_macro"])

    best = max(("RandomForest", "XGBoost"), key=lambda k: out[k]["f1_macro"])
    out["best"] = best
    out["feature_importance"] = {
        k: pd.Series(out[k]["model"].feature_importances_, index=MODEL_FEATURES)
              .sort_values(ascending=False).round(5).to_dict()
        for k in ("RandomForest", "XGBoost")}
    return out


# --------------------------------------------------------------------------- #
# Forecasting (regression on log1p ridership)
# --------------------------------------------------------------------------- #
def regression_metrics(y_true, y_pred) -> dict:
    """MAE, RMSE, R^2 and WAPE on the original (boardings) scale."""
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    return {"mae": float(mean_absolute_error(y_true, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
            "r2": float(r2_score(y_true, y_pred)),
            "wape": float(np.abs(y_true - y_pred).sum() / max(y_true.sum(), 1))}


def train_forecasters(Xtr: pd.DataFrame, ytr_log: pd.Series, Xva: pd.DataFrame, yva: pd.Series,
                      rf_rows: int = 500_000) -> dict:
    """Train XGBRegressor and RandomForestRegressor on log1p(boardings); compare to the
    seasonal-profile baseline exp(te_route_dow_hour) - 1."""
    out = {}
    base = np.expm1(Xva["te_route_dow_hour"].to_numpy())
    out["SeasonalProfileBaseline"] = regression_metrics(yva, base)

    t0 = time.time()
    xgb = XGBRegressor(n_estimators=1500, max_depth=9, learning_rate=0.05, subsample=0.8,
                       colsample_bytree=0.8, min_child_weight=10, reg_lambda=2.0, tree_method="hist",
                       n_jobs=-1, random_state=C.RANDOM_STATE, early_stopping_rounds=60)
    xgb.fit(Xtr, ytr_log, eval_set=[(Xva, np.log1p(yva))], verbose=False)
    p = np.clip(np.expm1(xgb.predict(Xva)), 0, None)
    out["XGBoost"] = {"model": xgb, "train_seconds": round(time.time() - t0, 1),
                      "best_iteration": int(xgb.best_iteration), **regression_metrics(yva, p)}
    log.info("XGB regressor MAE %.2f", out["XGBoost"]["mae"])

    Xs, ys = _sample(Xtr, ytr_log, rf_rows)
    t0 = time.time()
    rf = RandomForestRegressor(n_estimators=150, max_depth=22, min_samples_leaf=3, max_features=0.5,
                               n_jobs=-1, random_state=C.RANDOM_STATE)
    rf.fit(Xs, ys)
    p_rf = np.clip(np.expm1(rf.predict(Xva)), 0, None)
    out["RandomForest"] = {"model": rf, "train_seconds": round(time.time() - t0, 1),
                           "train_rows": int(len(Xs)), **regression_metrics(yva, p_rf)}
    log.info("RF regressor MAE %.2f", out["RandomForest"]["mae"])

    best = min(("RandomForest", "XGBoost"), key=lambda k: out[k]["mae"])
    out["best"] = best
    out["feature_importance"] = {
        k: pd.Series(out[k]["model"].feature_importances_, index=MODEL_FEATURES)
              .sort_values(ascending=False).round(5).to_dict()
        for k in ("RandomForest", "XGBoost")}
    out["validation_predictions"] = p if best == "XGBoost" else p_rf
    return out
