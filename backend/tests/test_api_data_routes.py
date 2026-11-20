"""Stage 6b: GET /api/data/coverage and GET /api/routes on the real data version in routeranker_test."""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

import psycopg
import pytest

from backend.app.db import open_conn

CUT = date(2026, 5, 31)
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
UNGROUPED = {"10", "130", "1001", "128", "19"}


def one(conn, sql, **p):
    return conn.execute(sql, p).fetchone()[0]


def dates_in(obj) -> list[date]:
    """Every ISO date appearing anywhere in a JSON response (keys and values, any depth)."""
    return [date.fromisoformat(s) for s in ISO.findall(json.dumps(obj))]


def counts_through(conn, t: date) -> dict:
    """Independent SQL for every count the coverage endpoint reports, using only dates <= t."""
    q = lambda sql: one(conn, sql, t=t)  # noqa: E731
    return {
        "obs_rows": q("SELECT count(*) FROM daily_ridership WHERE service_date <= %(t)s"),
        "obs_routes": q("SELECT count(DISTINCT route) FROM daily_ridership WHERE service_date <= %(t)s"),
        "obs_zeros": q("SELECT count(*) FROM daily_ridership WHERE service_date <= %(t)s AND rides = 0"),
        "sched_rows": q("SELECT count(*) FROM daily_schedule WHERE service_date <= %(t)s"),
        "sched_dates": q("SELECT count(DISTINCT service_date) FROM daily_schedule WHERE service_date <= %(t)s"),
        "matched_rows": q("SELECT count(*) FROM matched_utilization WHERE service_date <= %(t)s"),
        "matched_dates": q("SELECT count(DISTINCT service_date) FROM matched_utilization WHERE service_date <= %(t)s"),
        "no_sched_rows": q("SELECT count(*) FROM ridership_without_schedule WHERE service_date <= %(t)s"),
        "no_rides_rows": q("SELECT count(*) FROM schedule_without_ridership WHERE service_date <= %(t)s"),
        "in_window": q("""SELECT count(*) FROM daily_ridership r JOIN dataset_versions d USING (data_version)
                          WHERE r.service_date BETWEEN d.analysis_start AND least(d.analysis_end, %(t)s)"""),
    }


def reported(body) -> dict:
    o, s, m = body["observations"], body["schedule"], body["matching"]
    return {"obs_rows": o["rows"], "obs_routes": o["route_identifiers"], "obs_zeros": o["recorded_zero_rows"],
            "sched_rows": s["rows"], "sched_dates": s["dates"], "matched_rows": m["matched_rows"],
            "matched_dates": m["matched_dates"],
            "no_sched_rows": sum(x["rows"] for x in m["ridership_without_schedule"]),
            "no_rides_rows": sum(x["rows"] for x in m["schedule_without_ridership"]),
            "in_window": m["ridership_rows_in_window"]}


# ------------------------------------------------------------------ coverage
def test_coverage_counts_equal_independent_sql_and_reconcile(client, conn):
    body = client.get("/api/data/coverage").json()
    t = date.fromisoformat(body["cutoff"]["permitted_through"])
    assert reported(body) == counts_through(conn, t)
    r = reported(body)
    assert r["matched_rows"] + r["no_sched_rows"] == r["in_window"]  # Stage 2 identities, now from the API
    assert r["matched_rows"] + r["no_rides_rows"] == r["sched_rows"]


def test_coverage_with_a_cutoff_reveals_no_date_or_count_after_it(client, conn):
    full = client.get("/api/data/coverage").json()
    cut = client.get(f"/api/data/coverage?cutoff={CUT}").json()
    assert cut["cutoff"] == {"requested": str(CUT), "applied": True, "permitted_through": str(CUT)}
    # no date anywhere in the response (any field, any depth) is after the cutoff
    assert max(dates_in(cut)) <= CUT < max(dates_in(full))
    # every count equals SQL restricted to dates <= cutoff, and the cutoff actually changed them
    assert reported(cut) == counts_through(conn, CUT)
    changed = [k for k in reported(cut) if reported(cut)[k] != reported(full)[k]]
    assert {"obs_rows", "sched_rows", "matched_rows", "matched_dates", "in_window"} <= set(changed)
    # archives captured after the cutoff are absent; applied ranges are clipped
    assert all(date.fromisoformat(a["captured_date"]) <= CUT for a in cut["archives"])
    assert len(cut["archives"]) < len(full["archives"])
    # version-level figures that describe later data are left out
    assert "excluded_after_ridership_cutoff" not in cut["observations"]
    assert "ridership_cutoff" not in cut["observations"]
    assert {"imported_at", "inputs"}.isdisjoint(cut["details"])


def test_coverage_archives_are_ordered_and_contiguous(client):
    a = client.get("/api/data/coverage").json()["archives"]
    assert len(a) == 8
    for prev, nxt in zip(a, a[1:]):
        assert date.fromisoformat(nxt["applied_start"]) == date.fromisoformat(prev["applied_end"]) + timedelta(days=1)


def test_coverage_labels_mode_and_hashes_only_in_details(client):
    body = client.get("/api/data/coverage").json()
    assert body["mode"] == "historical_analysis" and body["mode_label"] == "Historical analysis"
    assert body["observations"]["label"] == "Recorded rides" and body["schedule"]["label"] == "Scheduled trips"
    outside = {k: v for k, v in body.items() if k != "details"}
    assert not re.search(r"\b[0-9a-f]{64}\b", json.dumps(outside))  # no sha256 outside the details panel
    assert len(body["details"]["archive_sha256"]) == 8


def test_unknown_data_version_is_404_never_a_fallback(client):
    for url in ["/api/data/coverage?data_version=nope", "/api/routes?data_version=nope"]:
        r = client.get(url)
        assert r.status_code == 404 and "not imported" in r.json()["detail"]


# ------------------------------------------------------------------ routes
def test_routes_one_row_per_ridership_identifier(client, conn):
    body = client.get("/api/routes").json()
    routes = [r["route"] for r in body["routes"]]
    assert len(routes) == len(set(routes)) == one(conn, "SELECT count(DISTINCT route) FROM daily_ridership")
    by = {r["route"]: r for r in body["routes"]}
    for rid in ["1001", "128", "19", "5"]:  # ridership-only identifiers (Stage 2)
        assert by[rid]["in_any_archive"] is False


def test_exactly_the_five_ungrouped_routes_have_null_group_id_and_a_reason(client):
    rows = client.get("/api/routes").json()["routes"]
    with_reason = {r["route"]: r for r in rows if r["ungrouped_reason"] is not None}
    assert set(with_reason) == UNGROUPED
    assert all(r["group_id"] is None and r["group_name"] is None and r["ungrouped_reason"]
               and r["in_group_population"] for r in with_reason.values())
    outside = [r for r in rows if not r["in_group_population"]]
    assert outside and all(r["group_id"] is None and r["ungrouped_reason"] is None for r in outside)
    assert len(rows) - len(outside) == 128  # the Stage 5 membership table: 123 grouped + 5 ungrouped


def test_route_filters(client, conn):
    g0 = client.get("/api/routes?group_id=0").json()
    assert g0["count"] == 67 and {r["group_id"] for r in g0["routes"]} == {0}
    no_sat = client.get("/api/routes?saturday_service=false").json()["routes"]
    assert no_sat and {r["saturday_service_status"] for r in no_sat} == {"no_scheduled_service"}
    sat = client.get("/api/routes?saturday_service=true").json()["routes"]
    assert {r["saturday_service_status"] for r in sat} <= {"available", "insufficient_observations"}
    ung = client.get("/api/routes?ungrouped=true").json()["routes"]
    assert {r["route"] for r in ung} == UNGROUPED
    act = client.get("/api/routes?active_start=2026-06-01&active_end=2026-06-30").json()["routes"]
    want = one(conn, """SELECT count(DISTINCT route) FROM daily_ridership
                        WHERE service_date BETWEEN '2026-06-01' AND '2026-06-30'""")
    assert len(act) == want


@pytest.mark.parametrize("url", ["/api/routes?active_start=2026-01-01",
                                 "/api/routes?active_start=2026-02-01&active_end=2026-01-01",
                                 "/api/routes?group_id=-1", "/api/routes?cutoff=not-a-date",
                                 "/api/routes?cutoff=2026-02-01&group_id=0"])
def test_invalid_route_requests_are_422(client, url):
    assert client.get(url).status_code == 422


def test_routes_with_a_cutoff_reveal_no_date_or_count_after_it(client, conn):
    full = {r["route"]: r for r in client.get("/api/routes").json()["routes"]}
    body = client.get(f"/api/routes?cutoff={CUT}").json()
    assert max(dates_in(body)) <= CUT
    rows = {r["route"]: r for r in body["routes"]}
    want = {r: (d, n) for r, d, n in conn.execute(
        """SELECT route, count(*), (SELECT count(*) FROM matched_utilization m WHERE m.route = r.route
                                    AND m.service_date <= %(t)s)
           FROM daily_ridership r WHERE service_date <= %(t)s GROUP BY route""", {"t": CUT}).fetchall()}
    assert set(rows) == set(want)
    assert all((rows[r]["recorded_days"], rows[r]["matched_days"]) == want[r] for r in rows)
    assert any(rows[r]["recorded_days"] < full[r]["recorded_days"] for r in rows)  # the cutoff changed something


def test_routes_before_the_group_period_ends_hide_groups(client):
    body = client.get("/api/routes?cutoff=2026-02-01").json()
    assert body["group_version"] is None and "after the cutoff" in body["groups_note"]
    assert all(r["group_id"] is None and r["saturday_service_status"] is None for r in body["routes"])


def test_the_api_connection_is_read_only(test_url, loaded):
    with open_conn(test_url) as c:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            c.execute("DELETE FROM model_versions")
