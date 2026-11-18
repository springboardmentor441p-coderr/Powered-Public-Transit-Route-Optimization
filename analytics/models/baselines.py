"""Step 32: fixed-rule baselines (notebook step 24, spec 9.10.1 steps 1-2). Nothing is fitted.

last_week      the same route's boardings exactly 7 days earlier
seasonal_mean  mean of the available 7/14/21/28-day values (at least two)
Every eligible row has both inputs (the 7-day value is required, so the seasonal count is at least 3).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BASELINE_RULES = {"last_week": "boardings_7d_ago", "seasonal_mean": "seasonal_mean"}


def baseline_predictor(name: str):
    column = BASELINE_RULES[name]

    def predict(frame: pd.DataFrame) -> np.ndarray:
        return frame[column].to_numpy(dtype=float)
    return predict
