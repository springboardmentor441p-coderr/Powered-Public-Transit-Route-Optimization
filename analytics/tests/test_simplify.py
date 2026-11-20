"""Display simplification (analytics/geometry/simplify.py): every stored point stays within the tolerance."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analytics.geometry.simplify import simplify, to_metres

VERSION_DIR = Path(__file__).resolve().parents[2] / "data/processed/cta_ref__r20261113__gtfs8__to20260731"


def max_gap_m(original, simplified) -> float:
    """Largest distance from any original point to the simplified polyline (point-to-segment), in metres."""
    p, s = to_metres(original), to_metres(simplified)
    a, b = s[:-1], s[1:]
    ab = b - a
    worst = 0.0
    for q in p:
        t = np.clip(((q - a) * ab).sum(axis=1) / np.maximum((ab * ab).sum(axis=1), 1e-12), 0, 1)
        d = np.hypot(*(a + t[:, None] * ab - q).T)
        worst = max(worst, float(d.min()))
    return worst


def test_a_straight_line_keeps_only_its_endpoints():
    line = [[-87.6 + i * 1e-4, 41.9] for i in range(50)]
    assert simplify(line, 5) == [[round(line[0][0], 5), 41.9], [round(line[-1][0], 5), 41.9]]


def test_an_l_shape_keeps_its_corner():
    leg1 = [[-87.6 + i * 1e-4, 41.9] for i in range(20)]
    leg2 = [[leg1[-1][0], 41.9 + i * 1e-4] for i in range(1, 20)]
    out = simplify(leg1 + leg2, 5)
    assert len(out) == 3 and out[1] == [round(leg1[-1][0], 5), 41.9]


def test_zero_tolerance_returns_the_input_unchanged():
    line = [[-87.6, 41.9], [-87.601, 41.901], [-87.602, 41.9]]
    assert simplify(line, 0) is line


def test_every_stored_point_of_every_real_line_is_within_the_tolerance():
    path = VERSION_DIR / "geometry" / "route_shapes.csv"
    if not path.exists():
        pytest.skip("geometry/route_shapes.csv not built")
    df = pd.read_csv(path, dtype=str, usecols=["geometry_version", "line_geojson"])
    df = df[df["geometry_version"] == "mdb-389-202607110020"]
    tol = 10.0
    for s in df["line_geojson"]:
        coords = json.loads(s)["coordinates"]
        out = simplify(coords, tol)
        assert out[0] == [round(coords[0][0], 5), round(coords[0][1], 5)]  # endpoints kept
        assert out[-1] == [round(coords[-1][0], 5), round(coords[-1][1], 5)]
        assert max_gap_m(coords, out) <= tol + 1.0  # + 1 m for rounding to 5 decimals (about 0.8 m)
