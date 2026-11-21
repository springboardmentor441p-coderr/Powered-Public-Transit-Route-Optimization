"""Stage 6c: GET /api/network/trend on the real data version in routeranker_test."""
from __future__ import annotations

import json
import re
import statistics
from datetime import date, timedelta

import pytest

CUT = date(2026, 5, 31)
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def get(client, **params):
    r = client.get("/api/network/trend", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_one_row_per_calendar_date_and_counts_add_up(client):
    body = get(client)
    a, b = (date.fromisoformat(body["range"][k]) for k in ("start", "end"))
    days = [date.fromisoformat(d["service_date"]) for d in body["days"]]
    assert days == [a + timedelta(days=i) for i in range((b - a).days + 1)]
    assert body["count"] == len(days) == sum(body["status_counts"].values())
    assert body["range"]["start"] == body["range"]["schedule_window"]["start"]  # default = analysis window
    assert body["units"]["rides"] == "rides/day" and body["labels"]["rides"] == "Recorded rides"


def test_daily_totals_equal_an_independent_sum(client, conn):
    body = get(client)
    want = {str(d): (int(r), int(n)) for d, r, n in conn.execute(
        """SELECT service_date, sum(rides), count(*) FROM daily_ridership
           WHERE service_date BETWEEN %s AND %s GROUP BY 1""",
        (body["range"]["start"], body["range"]["end"])).fetchall()}
    sched = {str(d): int(t) for d, t in conn.execute(
        """SELECT service_date, sum(scheduled_trips) FROM daily_schedule
           WHERE service_date BETWEEN %s AND %s GROUP BY 1""",
        (body["range"]["start"], body["range"]["end"])).fetchall()}
    for d in body["days"]:
        if d["status"] == "no_record":
            assert d["service_date"] not in want
        else:
            assert (d["rides"], d["routes_reporting"]) == want[d["service_date"]], d["service_date"]
        assert d["scheduled_trips"] == sched.get(d["service_date"]), d["service_date"]


def test_before_the_schedule_window_rides_only_and_no_schedule_totals(client):
    body = get(client, start="2025-11-01", end="2025-11-30")
    w0 = body["range"]["schedule_window"]["start"]
    for d in body["days"]:
        if d["service_date"] < w0 and d["status"] != "no_record":
            assert d["status"] == "recorded_rides_only" and d["scheduled_trips"] is None and d["reason"]
        if d["service_date"] >= w0 and d["status"] != "no_record":
            assert d["status"] == "recorded" and d["scheduled_trips"] > 0


def test_a_date_without_any_record_is_null_with_a_reason_never_zero(client):
    """The gap rule is checked on a range that starts before the first recorded date (2001-01-01); dates after the
    version's cutoff cannot be asked for."""
    body = get(client, start="2000-12-30", end="2001-01-02")
    gaps = [d for d in body["days"] if d["status"] == "no_record"]
    assert [d["service_date"] for d in gaps] == ["2000-12-30", "2000-12-31"]
    for d in gaps:
        assert d["rides"] is None and d["routes_reporting"] == 0 and d["reason"] and d["daytype"] is None
    assert all(d["rides"] > 0 for d in body["days"] if d["status"] != "no_record")


def test_summary_equals_the_rows(client):
    body = get(client)
    for s in body["summary"]:
        vals = [d["rides"] for d in body["days"] if d["daytype"] == s["daytype"] and d["rides"] is not None]
        assert s["days"] == len(vals) > 0
        assert s["mean_rides"] == pytest.approx(statistics.fmean(vals))
        assert s["median_rides"] == pytest.approx(statistics.median(vals))


def test_a_cutoff_reveals_no_date_or_count_after_it(client):
    full = get(client)
    cut = get(client, cutoff=str(CUT), end="2026-07-31")
    assert cut["range"]["end"] == str(CUT) and cut["range"]["clipped_to_cutoff"] is True
    assert max(date.fromisoformat(s) for s in ISO.findall(json.dumps(cut))) <= CUT
    earlier = {d["service_date"]: d for d in full["days"] if d["service_date"] <= str(CUT)}
    assert {d["service_date"]: d for d in cut["days"]} == earlier  # same rows, just fewer
    assert sum(s["days"] for s in cut["summary"]) < sum(s["days"] for s in full["summary"])


@pytest.mark.parametrize("params, message", [
    ({"start": "2026-02-01", "end": "2026-01-01"}, "start must not be after end"),
    ({"start": "not-a-date"}, None),
    ({"start": "2026-06-01", "cutoff": "2026-05-31"}, "the requested range starts after the cutoff"),
    ({"start": "2026-08-01"}, "the requested range starts after the cutoff"),
])
def test_bad_requests_are_422(client, params, message):
    r = client.get("/api/network/trend", params=params)
    assert r.status_code == 422
    if message:
        assert message in r.json()["detail"]
