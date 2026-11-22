"""Stage 7: replay session endpoints on routeranker_test (POST /api/replays, GET /api/replays/{id}, control)."""
from __future__ import annotations

import pytest


def create(client, **body):
    r = client.post("/api/replays", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def ctl(client, sid, **body):
    r = client.post(f"/api/replays/{sid}/control", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_create_defaults_to_1_june_with_versions_delay_and_cutoffs(client, stage7):
    s = create(client)
    assert (s["virtual_date"], s["revealed_through"], s["status"]) == ("2026-06-01", "2026-05-31", "paused")
    assert s["mode_label"] == "Historical replay" and s["reporting_delay_days"] == 1 and s["delay_assumption"]
    assert s["run"]["model_version"] and len(s["run"]["model_sha256"]) == 64 and s["run"]["data_version"]
    assert s["model"]["trained_through"] == "2026-03-31" and s["model"]["retrained_in_replay"] is False
    assert client.get(f"/api/replays/{s['session_id']}").json()["virtual_date"] == "2026-06-01"   # refresh = same state


@pytest.mark.parametrize("body, msg", [({"start_date": "2026-05-31"}, "between"), ({"start_date": "2026-08-01"}, "between"),
                                       ({"reporting_delay_days": 2}, "one-day reporting delay")])
def test_bad_sessions_are_refused_with_a_reason(client, stage7, body, msg):
    r = client.post("/api/replays", json=body)
    assert r.status_code == 422 and msg in r.json()["detail"]


def test_controls_move_forward_and_stop_at_completion(client, stage7):
    sid = create(client)["session_id"]
    assert ctl(client, sid, action="advance")["revealed_through"] == "2026-06-01"
    assert ctl(client, sid, action="next_week")["virtual_date"] == "2026-06-09"
    end = ctl(client, sid, action="jump_to_end")
    assert end["complete"] and end["virtual_date"] is None and end["revealed_through"] == "2026-07-31"
    r = client.post(f"/api/replays/{sid}/control", json={"action": "advance"})
    assert r.status_code == 422 and "complete" in r.json()["detail"]
    assert client.post(f"/api/replays/{sid}/control", json={"action": "fly"}).status_code == 422


def test_reset_creates_a_new_session_and_keeps_the_old_one(client, stage7, conn):
    old = create(client)["session_id"]
    ctl(client, old, action="next_week")
    new = ctl(client, old, action="reset")
    assert new["session_id"] != old and new["parent_session_id"] == old and new["virtual_date"] == "2026-06-01"
    assert client.get(f"/api/replays/{old}").json()["virtual_date"] == "2026-06-08"     # audit kept, untouched
    assert ctl(client, old, action="reset", start_date="2026-07-01")["virtual_date"] == "2026-07-01"


def test_unknown_session_is_404(client, stage7):
    assert client.get("/api/replays/nope").status_code == 404
