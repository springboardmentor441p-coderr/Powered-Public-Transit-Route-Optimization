"""Stage 4b, Step 38: 28-day input sequences for the neural networks (an additional modelling experiment).

For each target row (route, D) the window is the SAME route's boardings on the exact calendar dates
D-28, D-27, ..., D-1 (position 0 = D-28, the oldest; position 27 = D-1, the day before the target).
Lookups use date arithmetic on a (route, date) index, never "the previous row", so a gap in the record stays a
gap. The target date D (and anything later) is never looked up.

Two channels per day:
  raw value   recorded boardings, NaN when there is no record (a recorded 0 stays 0)
  observed    1.0 when a record exists, else 0.0
Scaling (and turning NaN into the scaled placeholder) happens later, in the preprocessor fitted on the fit part
only. A day closer than the reporting delay is treated as not yet published (observed = 0), as in build_features.

Guard: the window's D-1/7/14/21/28 positions must equal the Stage 3 lag columns boardings_<k>d_ago EXACTLY
(missing for missing). Two independent lookups agreeing shows neither is shifted.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analytics.features.model_features import KEY
from analytics.features.naming import LAG_MODEL, LAGS


class SequenceGuardError(ValueError):
    pass


def history_index(history: pd.DataFrame) -> pd.Series:
    """Boardings indexed by (route, date); unique keys required. NaN = no usable record."""
    h = history[KEY + ["rides"]].copy()
    h["date"] = pd.to_datetime(h["date"]).astype("datetime64[ns]")
    h["rides"] = h["rides"].astype("Float64").astype("float64")  # <NA> -> NaN, a recorded 0 stays 0
    if h.duplicated(KEY).any():
        raise ValueError("history must have one row per route/date")
    return h.set_index(KEY)["rides"].sort_index()


def build_sequences(rows: pd.DataFrame, history: pd.DataFrame, length: int = 28,
                    reporting_delay_days: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Return (raw_values, observed), each shaped (len(rows), length), positions ordered D-length .. D-1."""
    hist = history_index(history)
    routes = rows["route"].astype(str).to_numpy()
    dates = pd.to_datetime(rows["date"]).astype("datetime64[ns]").to_numpy()
    raw = np.full((len(rows), length), np.nan)
    for pos in range(length):
        k = length - pos  # position 0 -> D-length, last position -> D-1
        if k < reporting_delay_days:
            continue  # not yet published at the issue time: stays missing
        keys = pd.MultiIndex.from_arrays([routes, dates - np.timedelta64(k, "D")], names=KEY)
        raw[:, pos] = hist.reindex(keys).to_numpy(dtype=float)
    observed = (~np.isnan(raw)).astype(float)
    return raw, observed


def check_against_lags(rows: pd.DataFrame, raw: np.ndarray, length: int = 28) -> dict:
    """Stop unless every Stage 3 lag column equals the window position for the same day (NaN == NaN)."""
    out = {}
    for k in LAGS:
        if k > length:
            continue
        window = raw[:, length - k]
        lag = rows[LAG_MODEL[k]].to_numpy(dtype=float)
        if not np.array_equal(window, lag, equal_nan=True):
            bad = int((~((window == lag) | (np.isnan(window) & np.isnan(lag)))).sum())
            raise SequenceGuardError(f"window position D-{k} disagrees with {LAG_MODEL[k]} on {bad} rows")
        out[LAG_MODEL[k]] = "equal"
    return out
