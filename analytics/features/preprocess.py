"""Step 23: the shared preprocessing (spec 9.10.2). Used unchanged by training, evaluation and the backend.

Order (each step only reads what earlier steps produced):
  1. descriptive-name mapping (naming.EXPORT_TO_MODEL)
  2. issue-time calendar predictor (Sundays + fixed holiday list), never the target row's daytype
  3. availability counts / seasonal summary are taken AS EXPORTED, i.e. computed before any filling
  4. history policy:
     option_1 (comparison): all five lags 1/7/14/21/28 required
     option_2 (selected):   keep existing values; if rides_28_days_before is missing, fill it with the mean of the
                            available 7/14/21-day counts and set rides_28_days_before_available = 0 (original = 1);
                            withhold if no donor exists or any of the 1/7/14/21-day counts is missing
  5. schedule-augmented model only: valid target-date schedule inputs are required (never filled)
Targets are never filled or changed. The policy uses no statistics learned from other rows, so it cannot leak
validation/test information. Withholding is a status of the row, not a third model.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from .lags import sunday_holiday_service_day
from .naming import CALENDAR_HOLIDAY_PREDICTOR, LAG_MODEL, to_model_names

POLICIES = ("option_1", "option_2")
FILL_DONORS = [7, 14, 21]
OPTION_2_REQUIRED = [1, 7, 14, 21]


def prepare(features: pd.DataFrame, policy: str, holidays: set[date], with_schedule: bool,
            schedule_cols: tuple[str, str] = ("scheduled_trips", "scheduled_service_hours")) -> pd.DataFrame:
    """Return model-named rows with `eligible` and `withheld_reason` (empty when eligible)."""
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy}")
    df = to_model_names(features.copy())
    df[CALENDAR_HOLIDAY_PREDICTOR] = sunday_holiday_service_day(df["date"], holidays)
    lag = {k: df[c].astype("Float64") for k, c in LAG_MODEL.items()}
    reasons = pd.DataFrame(index=df.index)

    if policy == "option_1":
        for k, s in lag.items():
            reasons[f"missing_{LAG_MODEL[k]}"] = s.isna()
    else:
        donors = pd.concat([lag[k] for k in FILL_DONORS], axis=1)
        fill = donors.mean(axis=1, skipna=True)  # mean of AVAILABLE 7/14/21-day counts
        original = lag[28].notna()
        df["rides_28_days_before_available"] = original.astype("int64")
        df[LAG_MODEL[28]] = lag[28].where(original, fill)
        reasons["no_donor_for_rides_28_days_before"] = ~original & fill.isna()
        for k in OPTION_2_REQUIRED:
            reasons[f"missing_{LAG_MODEL[k]}"] = lag[k].isna()

    if with_schedule:
        trips, hours = schedule_cols
        reasons["missing_schedule"] = df[trips].isna()
        reasons["invalid_schedule_inputs"] = df[trips].notna() & (
            (df[trips].astype("Float64") <= 0).fillna(True) | df[hours].isna())

    flags = reasons.fillna(False).astype(bool)
    df["eligible"] = ~flags.any(axis=1)
    df["withheld_reason"] = flags.apply(lambda r: ";".join(c for c, v in r.items() if v), axis=1)
    df["policy"] = policy
    return df


def withheld_counts(prepared: pd.DataFrame) -> dict[str, int]:
    return {s: int((~prepared.loc[prepared["split"] == s, "eligible"]).sum())
            for s in ["train", "validation", "test"]}
