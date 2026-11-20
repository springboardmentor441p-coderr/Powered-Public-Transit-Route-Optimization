"""Stage 6a, Step 56: one representative line per route and direction, per geometry version (spec 9.17.2, 9.19.2).

Geometry version = one GTFS archive (snapshot_id), as in the Stage 5 overlap step. Trips counted are the BUS trips
whose service is active on at least one of the archive's APPLIED dates, built from the same pieces as
analytics.groups.overlap.served_stops (bus_crosswalk + active_service_dates).

"Most common" means USED MOST IN THE VERSION'S PERIOD, measured in trip-days: each active trip counts once for
every applied date its service runs on. (Counting trips alone treated a timetable edition that ran 1 day the same as
one that ran 11; see NOTES Step 57.) For each (route, direction_id) the chosen shape has the most trip-days. Exact
ties: lowest shape_id compared as text. The number of shapes tied at the top is stored, so ties stay visible, and
the map says "tied with N other path(s) this version".

Coordinates are GeoJSON [lon, lat] (RFC 7946). Leaflet's GeoJSON layer converts them to (lat, lon) itself, so no
code downstream flips them by hand. A Chicago bounding box catches a swap here.

Label on every map: "Most common path per direction". It is a drawing aid, not the full set of paths a route runs.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from analytics.reconstruction.gtfs_tables import _csv_view, bus_crosswalk
from analytics.reconstruction.service_calendar import active_service_dates, load_calendar, load_calendar_dates

PATH_LABEL = "Most common path per direction"
PATH_DEFINITION = ("for each route and direction, the GTFS shape with the most trip-days on the archive's applied "
                   "dates (each active bus trip counted once per applied date its service runs); exact ties go to the "
                   "lowest shape_id compared as text")
TIE_RULE = "trip_days_using_shape descending, then shape_id ascending (text)"
TIE_LABEL = "tied with {n} other path(s) this version"
COORD_ORDER = "[lon, lat] (GeoJSON, RFC 7946)"
BOUNDS = {"lon": (-88.5, -87.3), "lat": (41.5, 42.3)}  # generous box around the CTA service area
DIR = ["route", "direction_id"]
COLUMNS = ["geometry_version", "route", "route_id", "direction_id", "direction_label", "shape_id",
           "trip_days_using_shape", "active_trip_days", "trips_using_shape", "active_trips", "tied_top_shapes",
           "point_count", "line_geojson"]


class ShapeError(ValueError):
    pass


def tie_label(tied_top_shapes: int) -> str | None:
    """Map text for a line whose top trip-day count was shared; None when the choice was unique."""
    if tied_top_shapes < 1:
        raise ShapeError("tied_top_shapes counts the chosen shape itself, so it is at least 1")
    return None if tied_top_shapes == 1 else TIE_LABEL.format(n=tied_top_shapes - 1)


def active_bus_trips(con: duckdb.DuckDBPyConnection, snapshot_id: str, applied: list[date]) -> pd.DataFrame:
    """One row per bus trip active on >= 1 applied date: route, route_id, direction_id, direction, shape_id, plus
    active_days = the number of applied dates its service runs on."""
    bus_crosswalk(con, snapshot_id)
    con.register("_svc", active_service_dates(load_calendar(con), load_calendar_dates(con), applied))
    try:
        t = con.execute("""
            SELECT cw.route, cw.route_id, t.trip_id, t.direction_id, t.direction, t.shape_id,
                   count(DISTINCT _svc.date) AS active_days
            FROM trips t
            JOIN _svc ON _svc.service_id = t.service_id
            JOIN bus_cw cw ON cw.route_id = t.route_id
            GROUP BY ALL""").df()
    finally:
        con.unregister("_svc")
    if t.duplicated("trip_id").any():
        raise ShapeError("a trip_id appears with two different route/direction/shape rows")
    return t.astype({c: "string" for c in t.columns if c != "active_days"}).astype({"active_days": "int64"})


def choose_shapes(trips: pd.DataFrame) -> pd.DataFrame:
    """Pick one shape per (route, direction_id); fixed tie-breaker; refuse rows that would make the choice unclear."""
    for col in ["shape_id", "direction_id"]:
        bad = trips[col].isna() | (trips[col] == "")
        if bad.any():
            raise ShapeError(f"{int(bad.sum())} active bus trips have no {col}")
    if not trips["direction_id"].isin(["0", "1"]).all():
        raise ShapeError(f"direction_id outside {{0, 1}}: {sorted(set(trips['direction_id']) - {'0', '1'})}")
    labels = trips.groupby(DIR)["direction"].nunique(dropna=False)
    if (labels > 1).any():
        raise ShapeError(f"several direction labels for one direction_id: {labels[labels > 1].index.tolist()[:5]}")
    k = (trips.groupby(["route", "route_id", "direction_id", "direction", "shape_id"], dropna=False)
         .agg(trip_days_using_shape=("active_days", "sum"), trips_using_shape=("trip_id", "size")).reset_index())
    by_dir = k.groupby(DIR)
    k["active_trip_days"] = by_dir["trip_days_using_shape"].transform("sum")
    k["active_trips"] = by_dir["trips_using_shape"].transform("sum")
    top = k["trip_days_using_shape"] == by_dir["trip_days_using_shape"].transform("max")
    k["tied_top_shapes"] = top.groupby([k["route"], k["direction_id"]]).transform("sum")
    k = k.sort_values(["route", "direction_id", "trip_days_using_shape", "shape_id"],
                      ascending=[True, True, False, True], kind="mergesort")  # most trip-days, then lowest id
    best = k.drop_duplicates(DIR, keep="first").rename(columns={"direction": "direction_label"})
    return best.reset_index(drop=True)


def shape_lines(con: duckdb.DuckDBPyConnection, shape_ids: list[str]) -> dict[str, list[list[float]]]:
    """shape_id -> [[lon, lat], ...] in numeric shape_pt_sequence order (so 10 comes after 9, not after 1)."""
    con.register("_ids", pd.DataFrame({"shape_id": shape_ids}, dtype="string"))
    try:
        pts = con.execute("""
            SELECT s.shape_id, CAST(s.shape_pt_sequence AS INTEGER) AS seq,
                   CAST(s.shape_pt_lon AS DOUBLE) AS lon, CAST(s.shape_pt_lat AS DOUBLE) AS lat
            FROM shapes s JOIN _ids ON _ids.shape_id = s.shape_id
            ORDER BY s.shape_id, seq""").df()  # a non-numeric value fails the CAST and stops the build
    finally:
        con.unregister("_ids")
    if pts.duplicated(["shape_id", "seq"]).any():
        raise ShapeError("a shape has a repeated shape_pt_sequence, so its point order is undefined")
    missing = set(shape_ids) - set(pts["shape_id"])
    if missing:
        raise ShapeError(f"chosen shapes absent from shapes.txt: {sorted(missing)[:5]}")
    out_box = ~pts["lon"].between(*BOUNDS["lon"]) | ~pts["lat"].between(*BOUNDS["lat"])
    if out_box.any():
        raise ShapeError(f"{int(out_box.sum())} points outside the Chicago box (lon/lat swapped or bad data)")
    lines = {sid: g[["lon", "lat"]].round(6).values.tolist() for sid, g in pts.groupby("shape_id", sort=False)}
    short = [sid for sid, c in lines.items() if len(c) < 2]
    if short:
        raise ShapeError(f"shapes with fewer than 2 points cannot be drawn: {short[:5]}")
    return lines


def version_shapes(con: duckdb.DuckDBPyConnection, snapshot_id: str, shapes_txt: Path,
                   applied: list[date]) -> pd.DataFrame:
    _csv_view(con, "shapes", shapes_txt)
    best = choose_shapes(active_bus_trips(con, snapshot_id, applied))
    lines = shape_lines(con, best["shape_id"].tolist())
    best["point_count"] = best["shape_id"].map(lambda s: len(lines[s]))
    best["line_geojson"] = best["shape_id"].map(
        lambda s: json.dumps({"type": "LineString", "coordinates": lines[s]}, separators=(",", ":")))
    best.insert(0, "geometry_version", snapshot_id)
    return best[COLUMNS]


def verify(shapes: pd.DataFrame, expected_routes: set[str]) -> dict:
    """Identities that must hold for one version; any failure stops the build."""
    routes = set(shapes["route"])
    checks = {
        "one row per (version, route, direction)": not shapes.duplicated(["geometry_version", *DIR]).any(),
        "routes equal Stage 5 route_stop_coverage for this version": routes == expected_routes,
        "chosen shape trip-days <= active trip-days": bool((shapes["trip_days_using_shape"]
                                                             <= shapes["active_trip_days"]).all()),
        "chosen shape trips <= active trips": bool((shapes["trips_using_shape"] <= shapes["active_trips"]).all()),
        "trip-days >= trips (each active trip runs >= 1 applied day)":
            bool((shapes["trip_days_using_shape"] >= shapes["trips_using_shape"]).all()),
        "at least one tied-top shape (itself)": bool((shapes["tied_top_shapes"] >= 1).all()),
    }
    if not all(checks.values()):
        failed = [k for k, v in checks.items() if not v]
        raise ShapeError(f"{shapes['geometry_version'].iat[0]}: geometry identities failed: {failed} "
                         f"(only here {sorted(routes - expected_routes)}, only in coverage "
                         f"{sorted(expected_routes - routes)})")
    return checks
