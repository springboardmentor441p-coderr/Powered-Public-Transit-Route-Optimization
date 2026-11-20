"""Stage 6b: GET /api/map/lines on the real data version in routeranker_test."""
from __future__ import annotations

import json
import re
from datetime import date

import pytest

from analytics.geometry.route_shapes import BOUNDS, PATH_LABEL

ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
V0108, V0326, V0530, V0711 = ("mdb-389-202601080131", "mdb-389-202603260020", "mdb-389-202605300003",
                              "mdb-389-202607110020")


def get(client, **params):
    r = client.get("/api/map/lines", params=params)
    assert r.status_code == 200, r.text
    return r


def test_default_version_and_date_selection(client):
    assert get(client).json()["geometry_version"] == V0711
    assert get(client, cutoff="2026-05-31").json()["geometry_version"] == V0530
    assert get(client, date="2026-01-15").json()["geometry_version"] == V0108
    r = client.get("/api/map/lines", params={"date": "2025-11-01"})
    assert r.status_code == 422 and "no timetable version applies" in r.json()["detail"]


def test_exact_lines_equal_the_stored_lines(client, conn):
    body = get(client, geometry_version=V0326, routes="22,49", simplify_m=0).json()
    stored = {(r[0], r[1]): r[2] for r in conn.execute(
        """SELECT route, direction_id, line_geojson FROM route_shapes
           WHERE geometry_version = %s AND route IN ('22', '49')""", (V0326,)).fetchall()}
    assert len(body["lines"]) == len(stored) == 4
    for ln in body["lines"]:
        assert ln["line_geojson"] == stored[(ln["route"], ln["direction_id"])]
        assert ln["points_sent"] == ln["point_count"]
    assert body["display"]["note"] == "stored lines exactly"


def test_default_display_is_simplified_much_smaller_and_says_so(client):
    full = get(client, simplify_m=0)
    simple = get(client)
    body = simple.json()
    assert body["display"]["simplify_m"] == 10 and "within 10 m" in body["display"]["note"]
    assert body["display"]["points_sent"] < body["display"]["points_stored"] / 10
    assert len(simple.content) < len(full.content) / 10
    assert body["label"] == PATH_LABEL and body["count"] == 250


def test_lines_are_lon_lat_in_chicago_and_carry_tie_labels(client):
    body = get(client).json()
    for ln in body["lines"]:
        for lon, lat in ln["line_geojson"]["coordinates"]:
            assert BOUNDS["lon"][0] <= lon <= BOUNDS["lon"][1] and BOUNDS["lat"][0] <= lat <= BOUNDS["lat"][1]
    tied = [ln for ln in body["lines"] if ln["tie_label"]]
    assert [(ln["route"], ln["direction_id"]) for ln in tied] == [("125", 1)]  # the one remaining tie (Step 57)
    assert tied[0]["tie_label"] == "tied with 1 other path(s) this version"
    assert {ln["group_id"] for ln in body["lines"]} <= {0, 1, None}


def test_a_requested_route_not_in_the_version_has_no_lines_and_a_reason(client):
    body = get(client, geometry_version=V0326, routes="10,22").json()
    assert body["routes_without_lines"] == [{"route": "10", "reason": "not in this timetable version"}]
    assert {ln["route"] for ln in body["lines"]} == {"22"}


def test_a_cutoff_reveals_no_later_date_and_refuses_later_versions_and_dates(client):
    body = get(client, cutoff="2026-05-31").json()
    assert max(date.fromisoformat(s) for s in ISO.findall(json.dumps(body))) <= date(2026, 5, 31)
    assert body["applied"]["end"] == "2026-05-31"  # the 2026-05-30 version's range is clipped to the cutoff
    for params in [{"cutoff": "2026-05-31", "geometry_version": V0711},
                   {"cutoff": "2026-05-31", "date": "2026-06-15"}]:
        assert client.get("/api/map/lines", params=params).status_code == 422


@pytest.mark.parametrize("params", [{"geometry_version": V0326, "date": "2026-04-01"}, {"simplify_m": -1},
                                    {"simplify_m": 101}, {"geometry_version": "nope"}, {"date": "not-a-date"}])
def test_bad_requests_are_422(client, params):
    assert client.get("/api/map/lines", params=params).status_code == 422
