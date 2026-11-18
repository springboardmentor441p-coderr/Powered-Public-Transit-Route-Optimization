"""Step 31: scoring (notebook step 22, spec 9.10.3).

`score` is the arithmetic: MAE, RMSE and WAPE. WAPE = 100 * sum|error| / sum(actual) and is UNAVAILABLE (None)
when the actual total is 0; with no scored rows every metric is unavailable (None), never 0 error.
`evaluate` wraps it with coverage: it predicts ONLY eligible rows, so a withheld row can never be scored.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd


class ScoringError(ValueError):
    pass


def score(actual, predicted) -> dict:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if actual.shape != predicted.shape:
        raise ScoringError("actual and predicted have different lengths")
    if not (np.isfinite(actual).all() and np.isfinite(predicted).all()):
        raise ScoringError("scored rows need a recorded actual and a numeric prediction")
    n = int(len(actual))
    gap = actual - predicted
    total = float(actual.sum())
    abs_sum = float(np.abs(gap).sum())
    return {"rows": n,
            "MAE": float(np.abs(gap).mean()) if n else None,
            "RMSE": float(np.sqrt((gap ** 2).mean())) if n else None,
            "WAPE_percent": float(100 * abs_sum / total) if total > 0 else None,
            "abs_error_sum": abs_sum, "actual_sum": total}


def evaluate(frame: pd.DataFrame, predict: Callable[[pd.DataFrame], np.ndarray]) -> tuple[dict, pd.Series]:
    """Score `predict` on the eligible rows of `frame`. Returns (metrics with coverage, predictions on eligible rows).

    `predict` is called with the eligible rows only. An eligible row without a numeric forecast is an error, not a
    silent drop: dropping it would quietly change the scored population."""
    eligible = frame["eligible"].astype(bool)
    rows = frame.loc[eligible]
    preds = np.asarray(predict(rows), dtype=float) if len(rows) else np.empty(0)
    if len(preds) != len(rows):
        raise ScoringError("predict must return one value per eligible row")
    if np.isnan(preds).any():
        raise ScoringError(f"{int(np.isnan(preds).sum())} eligible rows received no forecast")
    withheld = frame.loc[~eligible]
    m = {"target_rows": int(len(frame)), "scored_rows": int(len(rows)), "withheld_rows": int(len(withheld)),
         "coverage": float(len(rows) / len(frame)) if len(frame) else None,
         "withheld_by_reason": {str(k): int(v) for k, v in withheld["excluded_reason"].value_counts().items()},
         **score(rows["rides"].to_numpy(dtype=float), preds)}
    return m, pd.Series(preds, index=rows.index, name="prediction")
