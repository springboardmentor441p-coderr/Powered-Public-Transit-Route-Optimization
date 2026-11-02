"""Loading and validation helpers for Chicago CTA bus ridership data."""

from pathlib import Path

import pandas as pd


def load_bus_ridership(path: str | Path) -> pd.DataFrame:
    """Load validated route/date boardings with canonical columns.

    CTA's public export uses ``route``, ``date``, ``daytype``, and ``rides``.
    Exact duplicate records are removed; conflicting duplicates and malformed
    observations fail loudly so they can be investigated instead of summed.
    """
    frame = pd.read_csv(path, dtype="string", keep_default_na=False)
    by_lower = {str(column).strip().lower(): column for column in frame.columns}
    aliases = {
        "date": ("date", "service_date"),
        "route": ("route", "route_name", "bus_route"),
        "daytype": ("daytype", "day_type"),
        "rides": ("rides", "ridership", "total_rides", "boardings", "daily_boardings"),
    }
    rename = {}
    missing = []
    for canonical, options in aliases.items():
        match = next((by_lower[name] for name in options if name in by_lower), None)
        if match is None:
            missing.append(f"{canonical} ({', '.join(options)})")
        else:
            rename[match] = canonical
    if missing:
        raise ValueError(f"CSV is missing required columns: {'; '.join(missing)}. Found: {list(frame.columns)}")

    frame = frame.rename(columns=rename)[["date", "route", "daytype", "rides"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["route"] = frame["route"].str.strip()
    frame["daytype"] = frame["daytype"].str.strip().str.upper()
    frame["rides"] = pd.to_numeric(frame["rides"].str.replace(",", "", regex=False), errors="coerce")

    invalid = (
        frame["date"].isna()
        | frame["route"].eq("")
        | ~frame["daytype"].isin(["W", "A", "U"])
        | frame["rides"].isna()
        | (frame["rides"] < 0)
        | (frame["rides"] % 1 != 0)
    )
    if invalid.any():
        raise ValueError(f"Found {int(invalid.sum())} invalid ridership rows; inspect source before training")

    frame["date"] = frame["date"].dt.normalize()
    frame["rides"] = frame["rides"].astype("int64")
    frame = frame.drop_duplicates()
    conflicts = frame.duplicated(["route", "date"], keep=False)
    if conflicts.any():
        examples = frame.loc[conflicts, ["route", "date", "daytype", "rides"]].head(8).to_dict("records")
        raise ValueError(f"Conflicting route/date observations found; quarantine and resolve them. Examples: {examples}")
    return frame.sort_values(["date", "route"]).reset_index(drop=True)
