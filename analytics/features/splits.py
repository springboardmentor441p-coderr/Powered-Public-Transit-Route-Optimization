"""Step 22: chronological split labels (spec 9.10.3). Each target date belongs to exactly one split."""
from __future__ import annotations

from datetime import date

import pandas as pd

SPLITS = ["train", "validation", "test"]


class SplitError(ValueError):
    pass


def parse_ranges(cfg_ranges: dict) -> dict[str, tuple[date, date]]:
    r = {s: (date.fromisoformat(cfg_ranges[s][0]), date.fromisoformat(cfg_ranges[s][1])) for s in SPLITS}
    for a, b in zip(SPLITS, SPLITS[1:]):
        if not r[a][1] < r[b][0]:
            raise SplitError(f"split ranges overlap or are out of order: {a} {r[a]} vs {b} {r[b]}")
    return r


def assign_split(dates: pd.Series, ranges: dict[str, tuple[date, date]]) -> pd.Series:
    d = pd.to_datetime(dates)
    out = pd.Series(pd.NA, index=dates.index, dtype="string")
    for s, (lo, hi) in ranges.items():
        out[(d >= pd.Timestamp(lo)) & (d <= pd.Timestamp(hi))] = s
    if out.isna().any():
        raise SplitError(f"{int(out.isna().sum())} target rows fall outside every split range")
    return out


def date_overlap(df: pd.DataFrame) -> dict[str, int]:
    """Number of dates shared between each pair of splits (must all be 0)."""
    sets = {s: set(df.loc[df["split"] == s, "date"]) for s in SPLITS}
    return {f"{a}&{b}": len(sets[a] & sets[b]) for i, a in enumerate(SPLITS) for b in SPLITS[i + 1:]}
