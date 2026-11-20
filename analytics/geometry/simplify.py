"""Douglas-Peucker line simplification for DISPLAY (spec 9.16.2 network map). Stored lines are never changed.

Every original point stays within `tolerance_m` metres of the simplified line; both endpoints are always kept.
Distances use a local flat projection around Chicago (error well under 1% at city scale).
"""
from __future__ import annotations

import numpy as np

LAT0 = np.radians(41.88)
EARTH_R = 6_371_000.0


def to_metres(coords: list[list[float]]) -> np.ndarray:
    c = np.asarray(coords, dtype=float)  # [lon, lat]
    return np.c_[np.radians(c[:, 0]) * EARTH_R * np.cos(LAT0), np.radians(c[:, 1]) * EARTH_R]


def keep_indices(coords: list[list[float]], tolerance_m: float) -> np.ndarray:
    xy = to_metres(coords)
    keep = np.zeros(len(xy), dtype=bool)
    keep[[0, -1]] = True
    stack = [(0, len(xy) - 1)]
    while stack:  # iterative: a 2,000-point line cannot hit Python's recursion limit
        i, j = stack.pop()
        if j <= i + 1:
            continue
        seg, pts = xy[j] - xy[i], xy[i + 1:j] - xy[i]
        length = np.hypot(*seg)
        d = (np.abs(seg[0] * pts[:, 1] - seg[1] * pts[:, 0]) / length if length > 0
             else np.hypot(pts[:, 0], pts[:, 1]))
        k = int(np.argmax(d))
        if d[k] > tolerance_m:
            keep[i + 1 + k] = True
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return np.flatnonzero(keep)


def simplify(coords: list[list[float]], tolerance_m: float) -> list[list[float]]:
    if tolerance_m <= 0 or len(coords) <= 2:
        return coords
    return [[round(coords[i][0], 5), round(coords[i][1], 5)] for i in keep_indices(coords, tolerance_m)]
