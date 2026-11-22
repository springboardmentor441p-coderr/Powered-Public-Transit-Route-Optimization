"""Stage 7: the forecast review of a replay session (revealed days only)."""
from __future__ import annotations

import math


def session(client, **body):
    r = client.post("/api/replays", json=body)
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


def review(client, sid):
    r = client.get("/api/forecasts/review", params={"session": sid})
    assert r.status_code == 200, r.text
    return r.json()


def test_on_the_first_day_nothing_is_scored_and_no_route_is_ranked_on_misses(client, stage7):
    b = review(client, session(client))
    assert b["running"] == [] and b["yesterday"] == [] and b["coverage"]["route_days_scored"] == 0
    assert b["review"]["date"] == "2026-06-01" and b["review"]["counts"]["routes"] > 100   # today's forecasts exist
    assert b["misses"]["counts"]["ranked"] == 0
    assert all(m["rank"] is None and m["reason"] == "fewer than 20 scored days (0)" for m in b["misses"]["rows"])


def test_after_a_week_the_running_error_equals_an_independent_sql_computation(client, stage7, conn):
    sid = session(client)
    client.post(f"/api/replays/{sid}/control", json={"action": "next_week"})
    b = review(client, sid)
    assert [r["date"] for r in b["running"]] == [f"2026-06-0{d}" for d in range(1, 8)]
    want = conn.execute("""
        SELECT count(*), avg(abs(d.rides - m.prediction)), avg(abs(d.rides - s.prediction))
        FROM forecasts m JOIN forecasts s ON s.run_id = m.run_id AND s.route = m.route AND s.target_date = m.target_date
                                         AND s.method = 'seasonal_mean'
        JOIN daily_ridership d ON d.route = m.route AND d.service_date = m.target_date
        WHERE m.method = 'rf_demand' AND m.status = 'forecast' AND m.target_date BETWEEN '2026-06-01' AND '2026-06-07'""").fetchone()
    last = b["running"][-1]
    assert last["rows_scored"] == sum(r["day_rows_scored"] for r in b["running"]) == want[0]   # cumulative = sum of days
    assert math.isclose(last["model_mae"], float(want[1]), rel_tol=1e-12)
    assert math.isclose(last["baseline_mae"], float(want[2]), rel_tol=1e-12)
    assert b["yesterday"] and {y["route"] for y in b["yesterday"]} and b["review"]["date"] == "2026-06-08"


def test_at_the_end_the_running_error_reproduces_stage4a(client, stage7):
    sid = session(client)
    client.post(f"/api/replays/{sid}/control", json={"action": "jump_to_end"})
    b = review(client, sid)
    last = b["running"][-1]
    assert last["date"] == "2026-07-31" and last["rows_scored"] == 6542
    assert round(last["model_mae"], 4) == 398.0115 and round(last["baseline_mae"], 4) == 421.1546
    assert b["review"]["rows"] == []                       # complete: no replay day left to forecast
    ranked = [m for m in b["misses"]["rows"] if m["rank"] is not None]
    assert ranked and all(m["scored_days"] >= 20 for m in ranked)
    assert all(m["reason"].startswith("fewer than 20 scored days") for m in b["misses"]["rows"] if m["rank"] is None)
    ranks = [m["rank"] for m in ranked]
    assert ranks == sorted(ranks) and ranks[0] == 1


def test_the_review_ranks_predicted_rides_per_hour_and_lists_unavailable_rows_with_reasons(client, stage7):
    b = review(client, session(client, start_date="2026-06-10"))
    rows = b["review"]["rows"]
    ranked = [r for r in rows if r["rank_per_hour"] is not None]
    vals = [r["predicted_rides_per_scheduled_hour"] for r in ranked]
    assert vals == sorted(vals, reverse=True)
    assert all(r["reason"] for r in rows if r["rank_per_hour"] is None)
    assert all(r["predicted_rides"] is None for r in rows if r["status"] == "unavailable")   # never 0
    assert "candidate for planner inspection" in b["review"]["meaning"]


def test_the_review_needs_a_session(client, stage7):
    assert client.get("/api/forecasts/review").status_code == 422
