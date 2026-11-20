"""Stage 6b: GET /api/routes/{route}/history on the real data version in routeranker_test."""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

import pytest

CUT = date(2026, 5, 31)
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def get(client, route, **params):
    r = client.get(f"/api/routes/{route}/history", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def by_date(body) -> dict:
    return {d["service_date"]: d for d in body["days"]}


def sql_dates(conn, table, route, through=None) -> set[str]:
    rows = conn.execute(f"SELECT service_date::text FROM {table} WHERE route = %s "
                        "AND (%s::date IS NULL OR service_date <= %s::date)", (route, through, through)).fetchall()
    return {r[0] for r in rows}


def test_one_row_per_calendar_date_and_summary_adds_up(client):
    body = get(client, "22")
    a, b = (date.fromisoformat(body["range"][k]) for k in ("start", "end"))
    days = [date.fromisoformat(d["service_date"]) for d in body["days"]]
    assert days == [a + timedelta(days=i) for i in range((b - a).days + 1)]  # every date, once, in order
    assert body["count"] == len(days) == sum(body["summary"].values())
    assert body["range"]["start"] == body["range"]["schedule_window"]["start"]  # default = analysis window


def test_statuses_equal_the_stage2_tables(client, conn):
    for route in ["22", "169", "1001", "10"]:
        body = get(client, route)
        status = {d["service_date"]: d["status"] for d in body["days"]}
        assert {d for d, s in status.items() if s == "matched"} == sql_dates(conn, "matched_utilization", route)
        assert ({d for d, s in status.items() if s == "ridership_without_schedule"}
                == sql_dates(conn, "ridership_without_schedule", route))
        assert ({d for d, s in status.items() if s == "schedule_without_ridership"}
                == sql_dates(conn, "schedule_without_ridership", route))


def test_route_169_scheduled_days_without_a_record_keep_rides_null_and_their_reason(client, conn):
    days = by_date(get(client, "169"))
    missing = sql_dates(conn, "schedule_without_ridership", "169")
    assert {"2025-11-27", "2025-12-25"} <= missing  # Thanksgiving and Christmas (Stage 2)
    for d in missing:
        row = days[d]
        assert row["status"] == "schedule_without_ridership" and row["rides"] is None
        assert row["has_schedule"] and not row["has_record"] and row["scheduled_trips"] > 0
        assert row["reason"] == "no_ridership_record" and row["selected_snapshot_id"]


def test_route_1001_has_rides_but_never_scheduled_service(client):
    body = get(client, "1001")
    assert "matched" not in body["summary"] and body["summary"]["ridership_without_schedule"] > 0
    assert all(d["scheduled_trips"] is None for d in body["days"])
    assert all(d["reason"] for d in body["days"] if d["status"] == "ridership_without_schedule")


def test_missing_is_never_zero(client):
    for route in ["22", "169", "1001"]:
        for d in get(client, route)["days"]:
            assert (d["rides"] is None) == (not d["has_record"])
            assert (d["scheduled_trips"] is None) == (not d["has_schedule"])
            if d["status"] != "matched":
                assert d["rides_per_scheduled_trip"] is None and d["rides_per_scheduled_hour"] is None
            assert d["reason"] or d["status"] == "matched"


def test_dates_before_the_schedule_window(client):
    body = get(client, "22", start="2025-11-01")
    days = by_date(body)
    before = [d for k, d in days.items() if k < body["range"]["schedule_window"]["start"]]
    assert len(before) == 22  # 2025-11-01 .. 2025-11-22
    assert {d["status"] for d in before} <= {"recorded_rides_only", "no_record"}
    assert all(d["selected_snapshot_id"] is None and d["scheduled_trips"] is None for d in before)
    assert any(d["status"] == "recorded_rides_only" and d["rides"] is not None for d in before)


def test_a_cutoff_reveals_no_date_or_count_after_it(client, conn):
    full = get(client, "22")
    body = get(client, "22", end="2026-07-31", cutoff=str(CUT))
    assert max(date.fromisoformat(s) for s in ISO.findall(json.dumps(body))) <= CUT
    assert body["range"]["end"] == str(CUT) and body["range"]["clipped_to_cutoff"] is True
    assert body["cutoff"]["permitted_through"] == str(CUT)
    status = {d["service_date"]: d["status"] for d in body["days"]}
    assert {d for d, s in status.items() if s == "matched"} == sql_dates(conn, "matched_utilization", "22", CUT)
    assert body["count"] < full["count"]


def test_a_route_that_first_appears_after_an_early_cutoff_is_not_found(client, conn):
    route, first = conn.execute("""SELECT route, min(d) FROM (SELECT route, service_date AS d FROM daily_ridership
                                   UNION ALL SELECT route, service_date FROM daily_schedule) u
                                   GROUP BY route ORDER BY 2 DESC, 1 LIMIT 1""").fetchone()
    before = first - timedelta(days=1)
    r = client.get(f"/api/routes/{route}/history", params={"cutoff": str(before), "start": "2001-01-01"})
    assert r.status_code == 404 and str(before) in r.json()["detail"]
    assert client.get(f"/api/routes/{route}/history", params={"start": "2001-01-01"}).status_code == 200


@pytest.mark.parametrize("params, message", [
    ({"mode": "replay"}, None),
    ({"start": "2026-02-01", "end": "2026-01-01"}, "start must not be after end"),
    ({"start": "not-a-date"}, None),
    ({"start": "2026-06-01", "cutoff": "2026-05-31"}, "the requested range starts after the cutoff"),
    ({"start": "2026-08-01"}, "the requested range starts after the cutoff"),  # after the version's own cutoff
])
def test_bad_requests_are_422(client, params, message):
    r = client.get("/api/routes/22/history", params=params)
    assert r.status_code == 422
    if message:
        assert message in r.json()["detail"]


def test_unknown_route_is_404(client):
    assert client.get("/api/routes/NOPE/history").status_code == 404
