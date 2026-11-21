"""Stage 6b: GET /api/routes/compare on the real data version in routeranker_test."""
from __future__ import annotations

import json
import math
import re
from datetime import date

import pytest

from analytics.geometry.route_shapes import BOUNDS, PATH_LABEL

CUT = date(2026, 5, 31)
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
V0326, V0530, V0711 = "mdb-389-202603260020", "mdb-389-202605300003", "mdb-389-202607110020"


def get(client, **params):
    r = client.get("/api/routes/compare", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def by_route(body) -> dict:
    return {r["route"]: r for r in body["routes"]}


def test_values_and_ranks_equal_the_rankings_endpoint(client):
    body = get(client, routes="22,49,X49", daytype="W")
    assert body["configuration"]["gate_label"] == "reference gate: 20"
    assert body["configuration"]["min_observed_days"] == 20
    for metric in ["observed_daily_demand", "rides_per_scheduled_trip", "rides_per_scheduled_hour"]:
        ranking = {r["route"]: r for r in client.get("/api/rankings", params={"metric": metric}).json()["rows"]}
        for route, row in by_route(body).items():
            ind, ref = row["indicators"][metric], ranking[route]
            assert ind["network_rank"] == ref["rank"] and ind["reason"] == ref["reason"]
            for k in ("value", "numerator", "denominator"):
                assert ind[k] == ref[k] or math.isclose(ind[k], ref[k], rel_tol=1e-12)


def test_49_and_x49_overlap_and_lines(client):
    body = get(client, routes="49,X49", geometry_version=V0326)
    pair = body["overlap"]
    assert len(pair) == 1 and (pair[0]["route_a"], pair[0]["route_b"]) == ("49", "X49")
    assert pair[0]["smaller_route_stop_overlap"] == 1.0  # the express sits inside the local route (Stage 5)
    assert pair[0]["interpretation"].startswith("corridor review only")
    m = body["map"]
    assert m["geometry_version"] == V0326 and m["label"] == PATH_LABEL and m["routes_without_lines"] == []
    assert sorted((ln["route"], ln["direction_id"]) for ln in m["lines"]) == [("49", 0), ("49", 1), ("X49", 0),
                                                                              ("X49", 1)]
    for ln in m["lines"]:
        assert ln["line_geojson"]["type"] == "LineString"
        for lon, lat in ln["line_geojson"]["coordinates"]:  # [lon, lat], inside the Chicago box
            assert BOUNDS["lon"][0] <= lon <= BOUNDS["lon"][1] and BOUNDS["lat"][0] <= lat <= BOUNDS["lat"][1]
    assert all(r["map_lines"] == 2 for r in body["routes"])


def test_default_geometry_version_is_the_one_in_force_at_the_period_end(client):
    assert get(client, routes="22,49")["map"]["geometry_version"] == V0711  # full window ends 2026-07-31
    assert get(client, routes="22,49", cutoff=str(CUT))["map"]["geometry_version"] == V0530  # in force 2026-05-31


def test_a_route_not_in_the_geometry_version_has_no_lines_and_a_reason(client):
    body = get(client, routes="10,22", geometry_version=V0326)
    assert body["map"]["routes_without_lines"] == [{"route": "10", "reason": "not in this timetable version"}]
    rows = by_route(body)
    assert rows["10"]["map_lines"] == 0 and rows["22"]["map_lines"] == 2
    assert {ln["route"] for ln in body["map"]["lines"]} == {"22"}
    assert rows["10"]["indicators"] is not None  # its indicators are still compared (it has matched days)


def test_common_matched_days_and_the_comparability_note(client, conn):
    body = get(client, routes="10,22")
    want = conn.execute("""SELECT count(*) FROM (SELECT service_date FROM matched_utilization
                           WHERE route IN ('10', '22') AND daytype = 'W' GROUP BY service_date
                           HAVING count(DISTINCT route) = 2) s""").fetchone()[0]
    assert body["common_matched_days"] == want
    rows = by_route(body)
    assert rows["10"]["coverage"]["observed_days"] < rows["22"]["coverage"]["observed_days"]  # 10 starts in June
    assert body["comparable_note"] and "not all observed on the same dates" in body["comparable_note"]
    same = get(client, routes="49,X49")
    assert (same["comparable_note"] is None) == all(r["coverage"]["observed_days"] == same["common_matched_days"]
                                                    for r in same["routes"])


def test_missing_values_are_null_with_a_reason_never_zero(client, conn):
    weekday_only = conn.execute("""SELECT route FROM route_profiles
                                   WHERE saturday_service_status = 'no_scheduled_service'
                                   ORDER BY route LIMIT 1""").fetchone()[0]
    body = get(client, routes=f"{weekday_only},22,1001", daytype="A")
    rows = by_route(body)
    w = rows[weekday_only]
    assert w["coverage"]["observed_days"] == 0
    for ind in w["indicators"].values():
        assert ind["value"] is None and ind["network_rank"] is None and ind["eligible"] is False and ind["reason"]
    assert w["service"]["mean_scheduled_trips"] is None
    r1001 = rows["1001"]  # no matched days at all: no indicators, a reason, no zeros
    assert r1001["indicators"] is None and r1001["service"] is None and r1001["no_matched_days_reason"]
    assert r1001["coverage"]["recorded_days_without_schedule"] > 0


def test_a_cutoff_reveals_no_date_or_count_after_it(client):
    body = get(client, routes="22,49", cutoff=str(CUT))
    assert max(date.fromisoformat(s) for s in ISO.findall(json.dumps(body))) <= CUT
    assert body["period"]["end"] == str(CUT) and body["period"]["clipped_to_cutoff"] is True
    ranking = {r["route"]: r for r in client.get("/api/rankings", params={"cutoff": str(CUT)}).json()["rows"]}
    for route, row in by_route(body).items():
        ind = row["indicators"]["rides_per_scheduled_hour"]
        assert ind["network_rank"] == ranking[route]["rank"]
        assert row["coverage"]["observed_days"] == ranking[route]["observed_days"]
    full = by_route(get(client, routes="22,49"))
    assert by_route(body)["22"]["coverage"]["observed_days"] < full["22"]["coverage"]["observed_days"]
    r = client.get("/api/routes/compare", params={"routes": "22,49", "cutoff": str(CUT), "geometry_version": V0711})
    assert r.status_code == 422 and "captured after the cutoff" in r.json()["detail"]


@pytest.mark.parametrize("params", [
    {"routes": "22"}, {"routes": "1,2,3,4,6,7,8,9,12"}, {"routes": "22,22"},
    {"routes": "22,49", "period": "development", "start": "2026-01-01", "end": "2026-02-01"},
    {"routes": "22,49", "start": "2026-06-01", "end": "2026-07-31", "cutoff": "2026-05-31"},
    {"routes": "22,49", "daytype": "X"}, {"routes": "22,49", "geometry_version": "nope"},
])
def test_bad_requests_are_422(client, params):
    assert client.get("/api/routes/compare", params=params).status_code == 422


def test_unknown_route_is_404_and_named(client):
    r = client.get("/api/routes/compare", params={"routes": "22,NOPE"})
    assert r.status_code == 404 and "NOPE" in r.json()["detail"]


def test_same_days_only_uses_the_shared_dates(client, conn):
    """Compare's "same days only": every value is computed on the dates ALL routes were observed (route 10 starts in
    June, so route 22 is cut to those dates); ranks are left out with a note, and no comparability warning remains."""
    body = get(client, routes="10,22", same_days="true")
    n = body["common_matched_days"]
    assert body["same_days"] is True and str(n) in body["basis_label"] and body["rank_note"]
    assert body["comparable_note"] is None
    shared = conn.execute("""SELECT route, avg(rides) FROM matched_utilization
                             WHERE route IN ('10', '22') AND daytype = 'W' AND service_date IN (
                                 SELECT service_date FROM matched_utilization WHERE route IN ('10', '22') AND daytype = 'W'
                                 GROUP BY service_date HAVING count(DISTINCT route) = 2)
                             GROUP BY route""").fetchall()
    for route, mean in shared:
        r = by_route(body)[route]
        assert r["coverage"]["observed_days"] == n
        assert math.isclose(r["indicators"]["observed_daily_demand"]["value"], float(mean), rel_tol=1e-9)
        assert all(ind["network_rank"] is None for ind in r["indicators"].values())
    default = get(client, routes="10,22")
    assert default["same_days"] is False and default["rank_note"] is None
    assert by_route(default)["22"]["coverage"]["observed_days"] > n                 # the switch really changes the basis
