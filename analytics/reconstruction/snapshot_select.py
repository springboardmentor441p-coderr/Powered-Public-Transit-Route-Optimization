"""Step 11: daily snapshot selection (spec 9.6.3).

For date D choose the latest archive captured on or before D: ONE whole snapshot per date.
There is deliberately no per-route fallback to older archives (that would resurrect withdrawn routes),
and overlapping archives are never added together.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd


def select_snapshot(d: date, archives: list[dict]) -> str | None:
    """archives: [{"snapshot_id": str, "captured": date}, ...]. Returns None when no archive exists yet."""
    eligible = [a for a in archives if a["captured"] <= d]
    if not eligible:
        return None
    return max(eligible, key=lambda a: (a["captured"], a["snapshot_id"]))["snapshot_id"]


def archive_available_from(captured: date) -> date:
    """Conservative availability (spec 9.14.3): only the capture DATE is known, not the time of day, so an
    archive may be used for forecasts issued on dates strictly after the capture date."""
    return captured + timedelta(days=1)


def select_forecast_snapshot(target: date, archives: list[dict]) -> str | None:
    """Forecast-input selection (spec 9.14.3): latest archive available by the issue time (start of `target`),
    i.e. captured strictly BEFORE the target date. Whole snapshot only; the caller must still check that it
    defines service on the target date. The descriptive select_snapshot() above is unchanged."""
    eligible = [a for a in archives if archive_available_from(a["captured"]) <= target]
    if not eligible:
        return None
    return max(eligible, key=lambda a: (a["captured"], a["snapshot_id"]))["snapshot_id"]


def date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def selection_table(start: date, end: date, archives: list[dict]) -> pd.DataFrame:
    """One row per calendar date in [start, end]: date, snapshot_id (None = gap: no archive captured yet)."""
    return pd.DataFrame([{"date": d, "snapshot_id": select_snapshot(d, archives)} for d in date_range(start, end)])


def applied_ranges(selection: pd.DataFrame) -> dict[str, tuple[date, date]]:
    """First and last date each snapshot is applied to (for comparison with spec 9.4.2)."""
    sel = selection.dropna(subset=["snapshot_id"])
    g = sel.groupby("snapshot_id")["date"]
    return {sid: (lo, hi) for sid, lo, hi in zip(g.min().index, g.min().values, g.max().values)}
