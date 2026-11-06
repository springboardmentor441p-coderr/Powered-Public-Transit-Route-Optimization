"""Bounded route trip-allocation scenarios based on forecast boardings."""

from __future__ import annotations

import heapq
import math
from typing import Any

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {"route", "predicted_rides", "scheduled_trips"}


def optimize_trip_allocation(
    routes: pd.DataFrame,
    max_shift_pct: float = 0.10,
) -> dict[str, Any]:
    """Minimize the highest predicted boardings-per-trip ratio.

    The total scheduled trip count is fixed. Each route stays within the
    requested percentage change from its current daily trip count. This is a
    planning proxy only: daily boardings divided by daily trips is not vehicle
    load, passenger capacity, crowding, or a service-quality measure.
    """
    if not math.isfinite(float(max_shift_pct)) or not 0 <= max_shift_pct <= 0.5:
        raise ValueError("max_shift_pct must be between 0 and 0.5")
    missing = REQUIRED_COLUMNS - set(routes.columns)
    if missing:
        raise ValueError(f"Scenario input is missing columns: {sorted(missing)}")

    frame = routes[["route", "predicted_rides", "scheduled_trips"]].copy()
    frame["route"] = frame["route"].astype("string").str.strip()
    frame["predicted_rides"] = pd.to_numeric(frame["predicted_rides"], errors="coerce")
    frame["scheduled_trips"] = pd.to_numeric(frame["scheduled_trips"], errors="coerce")
    invalid = (
        frame["route"].isna() | frame["route"].eq("")
        | frame["predicted_rides"].isna() | ~np.isfinite(frame["predicted_rides"])
        | frame["predicted_rides"].lt(0)
        | frame["scheduled_trips"].isna() | ~np.isfinite(frame["scheduled_trips"])
        | frame["scheduled_trips"].lt(1)
        | frame["scheduled_trips"].mod(1).ne(0)
    )
    if invalid.any():
        raise ValueError("Routes need a name, nonnegative finite predictions, and positive integer scheduled trips")
    if frame["route"].duplicated().any():
        duplicate_routes = frame.loc[frame["route"].duplicated(keep=False), "route"].astype(str).unique().tolist()
        raise ValueError(f"Scenario input has duplicate routes: {duplicate_routes[:10]}")
    if frame.empty:
        raise ValueError("Scenario input must contain at least one route")

    route_names = frame["route"].astype(str).to_numpy()
    demand = frame["predicted_rides"].to_numpy(dtype=float)
    current = frame["scheduled_trips"].to_numpy(dtype=int)
    total_trips = int(current.sum())
    lower = np.maximum(1, np.ceil(current * (1 - max_shift_pct)).astype(int))
    upper = np.maximum(current, np.floor(current * (1 + max_shift_pct)).astype(int))
    if int(lower.sum()) > total_trips or int(upper.sum()) < total_trips:
        raise ValueError("The trip change bound cannot preserve the current systemwide trip total")

    if np.max(demand) == 0:
        allocation = current.copy()
    else:
        def minimum_allocation(max_ratio: float) -> np.ndarray:
            if max_ratio <= 0:
                return np.full(len(demand), np.iinfo(np.int64).max, dtype=np.int64)
            needed = np.ceil(demand / max_ratio - 1e-12).astype(np.int64)
            return np.maximum(lower, needed)

        low = 0.0
        high = float(np.max(demand / lower))
        for _ in range(80):
            middle = (low + high) / 2
            needed = minimum_allocation(middle)
            if np.all(needed <= upper) and int(needed.sum()) <= total_trips:
                high = middle
            else:
                low = middle
        allocation = minimum_allocation(high).astype(int)
        if np.any(allocation > upper) or int(allocation.sum()) > total_trips:
            raise RuntimeError("Could not construct a feasible trip allocation")

        # Allocate any spare trips to the route with the highest remaining
        # ratio; adding trips can only reduce that route's ratio.
        spare = total_trips - int(allocation.sum())
        heap = [(-demand[i] / allocation[i], i) for i in range(len(demand)) if allocation[i] < upper[i]]
        heapq.heapify(heap)
        for _ in range(spare):
            if not heap:
                raise RuntimeError("Trip allocation exhausted route bounds before preserving the total")
            _, index = heapq.heappop(heap)
            allocation[index] += 1
            if allocation[index] < upper[index]:
                heapq.heappush(heap, (-demand[index] / allocation[index], index))

    current_ratio = demand / current
    new_ratio = demand / allocation
    results = pd.DataFrame({
        "route": route_names,
        "predicted_rides": demand,
        "current_scheduled_trips": current,
        "scenario_scheduled_trips": allocation,
        "trip_change": allocation - current,
        "boardings_per_current_trip": current_ratio,
        "boardings_per_scenario_trip": new_ratio,
    }).sort_values(["trip_change", "route"], ascending=[False, True]).reset_index(drop=True)
    return {
        "objective": "minimize the maximum predicted boardings per scheduled trip, subject to a fixed total trip count and route-level change bounds",
        "max_route_change_pct": float(max_shift_pct * 100),
        "total_scheduled_trips": total_trips,
        "scenario_total_trips": int(allocation.sum()),
        "current_max_boardings_per_trip": float(current_ratio.max()),
        "scenario_max_boardings_per_trip": float(new_ratio.max()),
        "current_mean_route_boardings_per_trip": float(current_ratio.mean()),
        "scenario_mean_route_boardings_per_trip": float(new_ratio.mean()),
        "interpretation_limit": "Boardings divided by scheduled trips is an aggregate screening proxy. It is not passenger load, capacity, crowding, waiting time, or an operational recommendation.",
        "routes": results.to_dict(orient="records"),
    }
