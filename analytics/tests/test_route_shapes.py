"""Stage 6a geometry rules on a tiny hand-made GTFS feed (spec 9.17.2, 9.19.2)."""
from __future__ import annotations

import json
from datetime import date

import pandas as pd
import pytest

from analytics.geometry.route_shapes import (PATH_LABEL, ShapeError, choose_shapes, tie_label, verify,
                                             version_shapes)
from analytics.reconstruction.gtfs_tables import open_snapshot

ROUTES = ("route_id,route_short_name,route_long_name,route_type\n"
          "R1,1,Bronzeville,3\nR9,X9,Ashland Express,3\nRED,,Red Line,1\n")
CAL = ("WK,1,1,1,1,1,0,0,20260101,20261231\nWE,0,0,0,0,0,1,1,20260101,20261231\n"
       "OLD,1,0,0,0,0,0,0,20260101,20261231\nNEW,0,1,1,1,1,0,0,20260101,20261231\n")  # two editions in one week
MONDAY = date(2026, 3, 2)
WEEK = [date(2026, 3, d) for d in range(2, 7)]  # Mon 2 .. Fri 6
TRIP_HEADER = "route_id,service_id,trip_id,direction_id,direction,shape_id\n"
SHAPE_HEADER = "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"

TRIPS = (
    # route 1 South: shapes "10" and "9" both have 2 active trips -> tie; "10" < "9" as text, so "10" wins
    "R1,WK,a1,0,South,10\nR1,WK,a2,0,South,10\nR1,WK,a3,0,South,9\nR1,WK,a4,0,South,9\n"
    # route 1 North: weekend shape has MORE trips but is inactive on the applied Monday
    "R1,WE,b1,1,North,SWE\nR1,WE,b2,1,North,SWE\nR1,WE,b3,1,North,SWE\nR1,WK,b4,1,North,SWK\n"
    # X9: one shape per direction
    "R9,WK,x1,0,South,XS\nR9,WK,x2,1,North,XN\n"
    # rail: many trips, never a bus line
    "RED,WK,r1,0,South,RL\nRED,WK,r2,0,South,RL\nRED,WK,r3,0,South,RL\nRED,WK,r4,0,South,RL\nRED,WK,r5,0,South,RL\n"
)


def line(shape_id: str, n: int, swap: bool = False) -> str:
    """n points written in REVERSE file order; point i has lon -87.600 - i/1000, lat 41.900 + i/1000."""
    rows = []
    for i in reversed(range(1, n + 1)):
        lat, lon = 41.9 + i / 1000, -87.6 - i / 1000
        if swap:
            lat, lon = lon, lat
        rows.append(f"{shape_id},{lat:.6f},{lon:.6f},{i}\n")
    return "".join(rows)


SHAPES = "".join(line(s, n) for s, n in [("10", 10), ("9", 3), ("SWE", 2), ("SWK", 2), ("XS", 2), ("XN", 2),
                                         ("RL", 2)])


def build(feed, trips: str = TRIPS, shapes: str = SHAPES, applied: list[date] | None = None) -> pd.DataFrame:
    folder = feed(trips="", stop_times="a1,08:00:00,08:00:00,S1,1\n", calendar=CAL, routes=ROUTES)
    (folder / "trips.txt").write_text(TRIP_HEADER + trips, encoding="utf-8")
    (folder / "shapes.txt").write_text(SHAPE_HEADER + shapes, encoding="utf-8")
    con, _ = open_snapshot(folder)
    try:
        return version_shapes(con, "v1", folder / "shapes.txt", applied or [MONDAY])
    finally:
        con.close()


@pytest.fixture
def shapes(feed):
    return build(feed).set_index(["route", "direction_id"])


def test_exact_trip_day_tie_goes_to_lowest_shape_id_as_text(shapes):
    r = shapes.loc[("1", "0")]
    assert r["shape_id"] == "10"  # "10" < "9" character by character
    assert r["trip_days_using_shape"] == 2 and r["active_trip_days"] == 4  # one applied day: trip-days = trips
    assert r["trips_using_shape"] == 2 and r["active_trips"] == 4 and r["tied_top_shapes"] == 2
    assert shapes.loc[("X9", "0"), "tied_top_shapes"] == 1  # no tie


def test_editions_tied_on_trips_are_separated_by_trip_days(feed):
    # Two timetable editions of route 1 southbound, 2 trips each. The old one (lower shape_id) runs only Monday;
    # the new one runs Tuesday-Friday. Counting trips is a tie (2 vs 2) that the tie-breaker would hand to the OLD
    # path; counting trip-days (2 vs 8) picks the path actually used most in the week.
    trips = ("R1,OLD,o1,0,South,A_OLD\nR1,OLD,o2,0,South,A_OLD\n"
             "R1,NEW,n1,0,South,B_NEW\nR1,NEW,n2,0,South,B_NEW\n")
    r = build(feed, trips=trips, shapes=line("A_OLD", 2) + line("B_NEW", 3), applied=WEEK).iloc[0]
    assert r["shape_id"] == "B_NEW"
    assert r["trips_using_shape"] == 2 and r["active_trips"] == 4  # equal on trips...
    assert r["trip_days_using_shape"] == 8 and r["active_trip_days"] == 10  # ...not on trip-days (2 vs 8)
    assert r["tied_top_shapes"] == 1 and tie_label(int(r["tied_top_shapes"])) is None


def test_tie_label():
    assert tie_label(1) is None
    assert tie_label(2) == "tied with 1 other path(s) this version"
    assert tie_label(4) == "tied with 3 other path(s) this version"
    with pytest.raises(ShapeError):
        tie_label(0)


def test_inactive_trips_are_not_counted(shapes):
    r = shapes.loc[("1", "1")]
    assert r["shape_id"] == "SWK"  # SWE has 3 trips, but only on weekends
    assert r["active_trips"] == 1 and r["direction_label"] == "North"


def test_rail_routes_are_ignored(shapes):
    assert set(shapes.index.get_level_values("route")) == {"1", "X9"}
    assert "RL" not in set(shapes["shape_id"])


def test_points_in_numeric_sequence_order_and_lon_lat(shapes):
    coords = json.loads(shapes.loc[("1", "0"), "line_geojson"])
    assert coords["type"] == "LineString" and len(coords["coordinates"]) == 10
    assert shapes.loc[("1", "0"), "point_count"] == 10
    lons = [c[0] for c in coords["coordinates"]]
    assert lons == [round(-87.6 - i / 1000, 6) for i in range(1, 11)]  # 9 before 10, file order ignored
    lon, lat = coords["coordinates"][0]
    assert -88.5 < lon < -87.3 and 41.5 < lat < 42.3  # [lon, lat], not [lat, lon]


def test_swapped_coordinates_are_rejected(feed):
    bad = SHAPES.replace(line("XS", 2), line("XS", 2, swap=True))
    with pytest.raises(ShapeError, match="outside the Chicago box"):
        build(feed, shapes=bad)


def test_unclear_inputs_are_rejected():
    base = pd.DataFrame({"route": ["1", "1"], "route_id": ["R1", "R1"], "trip_id": ["a", "b"],
                         "direction_id": ["0", "0"], "direction": ["South", "South"], "shape_id": ["s", "s"]},
                        dtype="string").assign(active_days=[1, 1])
    with pytest.raises(ShapeError, match="no shape_id"):
        choose_shapes(base.assign(shape_id=["s", ""]))
    with pytest.raises(ShapeError, match="no direction_id"):
        choose_shapes(base.assign(direction_id=["0", pd.NA]))
    with pytest.raises(ShapeError, match="several direction labels"):
        choose_shapes(base.assign(direction=["South", "North"]))
    assert len(choose_shapes(base)) == 1


def test_verify_requires_the_coverage_route_set(shapes):
    t = shapes.reset_index()
    assert all(verify(t, {"1", "X9"}).values())
    with pytest.raises(ShapeError, match="only in coverage \\['55'\\]"):
        verify(t, {"1", "X9", "55"})


def test_label_text():
    assert PATH_LABEL == "Most common path per direction"
