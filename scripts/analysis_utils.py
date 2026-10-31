"""Small, tested transformations used by the editable analysis notebooks.

No downloads, training, automatic corrections or file writes happen on import.
"""

import numpy as np
import pandas as pd


def separate_duplicates(frame, keys):
    """Remove exact copies; quarantine every version of conflicting keys."""
    unique = frame.drop_duplicates().copy()
    conflicts = unique.duplicated(keys, keep=False)
    return unique.loc[~conflicts].copy(), unique.loc[conflicts].copy(), len(frame) - len(unique)


def exact_date_lags(frame, route="bus_route", date="payment_date", target="analysis_boardings",
                    days=(1, 7, 14, 21, 28)):
    """Calendar-date lookups, not previous-row shifts across missing dates."""
    if frame.duplicated([route, date]).any():
        raise ValueError("Lag input must have one row per route/date")
    result = frame.copy()
    lookup = frame.set_index([route, date])[target]
    for lag in days:
        index = pd.MultiIndex.from_arrays([frame[route], frame[date] - pd.Timedelta(days=lag)])
        result[f"lag_{lag}d"] = lookup.reindex(index).to_numpy()
    seasonal = [f"lag_{lag}d" for lag in (7, 14, 21, 28) if lag in days]
    if seasonal:
        result["seasonal_history_count"] = result[seasonal].notna().sum(axis=1)
        result["past_same_weekday_mean"] = result[seasonal].mean(axis=1).where(
            result.seasonal_history_count >= 2)
    return result


def gtfs_anchor_utc(service_date, timezone="America/New_York"):
    """GTFS time origin: local noon minus twelve elapsed hours (DST aware)."""
    noon = (pd.Timestamp(service_date).normalize() + pd.Timedelta(hours=12)).tz_localize(timezone)
    return noon.tz_convert("UTC") - pd.Timedelta(hours=12)


def trip_clock_hours(trips, service_date, timezone="America/New_York"):
    """Count starts and integrate scheduled trip duration into local clock hours.

    Input is already calendar-selected. UTC buckets preserve both fall-back hours;
    local_hour is naive only at output, matching the publisher's floating timestamps.
    Repeated local hours aggregate. DST-neighbourhood comparisons are withheld by
    the notebook because publisher repeated-hour semantics remain unverified.
    """
    columns = ["bus_route", "local_hour", "scheduled_departures", "scheduled_service_hours"]
    if trips.empty:
        return pd.DataFrame(columns=columns)
    start = trips.first_departure_seconds.to_numpy(dtype="int64")
    end = trips.final_arrival_seconds.to_numpy(dtype="int64")
    if np.any(end <= start):
        raise ValueError("A missing/nonpositive duration cannot become zero service hours")
    anchor = int(gtfs_anchor_utc(service_date, timezone).timestamp())
    starts, ends = anchor + start, anchor + end
    start_hours = starts // 3600
    pieces = [pd.DataFrame({"bus_route": trips.bus_route.to_numpy(), "utc_hour": start_hours,
                            "scheduled_departures": 1, "scheduled_service_hours": 0.0})]
    # Each positive overlap is emitted exactly once; no trip-by-trip Python loop.
    for offset in range(int(((ends - 1) // 3600 - start_hours).max()) + 1):
        bucket = start_hours + offset
        overlap = np.maximum(0, np.minimum(ends, (bucket + 1) * 3600) - np.maximum(starts, bucket * 3600))
        keep = overlap > 0
        pieces.append(pd.DataFrame({"bus_route": trips.bus_route.to_numpy()[keep],
                                    "utc_hour": bucket[keep], "scheduled_departures": 0,
                                    "scheduled_service_hours": overlap[keep] / 3600.0}))
    result = pd.concat(pieces, ignore_index=True).groupby(["bus_route", "utc_hour"], as_index=False).sum()
    result["local_hour"] = pd.to_datetime(result.utc_hour * 3600, unit="s", utc=True).dt.tz_convert(
        timezone).dt.tz_localize(None)
    result = result.groupby(["bus_route", "local_hour"], as_index=False)[
        ["scheduled_departures", "scheduled_service_hours"]].sum()
    assert result.scheduled_departures.sum() == len(trips)
    assert np.isclose(result.scheduled_service_hours.sum(), ((end - start) / 3600).sum())
    return result[columns]


def haversine_km(lat1, lon1, lat2, lon2):
    """Spherical distance; shape polyline estimate, not a routed road distance."""
    a1, o1, a2, o2 = [np.radians(v) for v in (lat1, lon1, lat2, lon2)]
    a = np.sin((a2-a1)/2)**2 + np.cos(a1)*np.cos(a2)*np.sin((o2-o1)/2)**2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def ratio_of_sums(frame, numerator, denominator):
    """Exclude incomplete pairs; do not average row ratios or divide by zero."""
    valid = frame[[numerator, denominator]].notna().all(axis=1) & frame[denominator].gt(0)
    total = frame.loc[valid, denominator].sum()
    return frame.loc[valid, numerator].sum() / total if total > 0 else np.nan
