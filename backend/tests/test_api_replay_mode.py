"""Stage 7: every endpoint in replay mode shows nothing after the session's cutoff (spec 9.16.3, 9.17.3).

A session on replay day 5 Jun 2026 has rides revealed through 4 Jun. In the raw JSON of every endpoint called with
that session: no ISO date after 5 Jun anywhere; the replay day itself (5 Jun) only as the replay day or as the target
of today's forecast (issued at its start), never as an observation; and no actual for a day not yet revealed.
"""
from __future__ import annotations

import json
import re
from datetime import date

import pytest

ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
REVEALED, TODAY = date(2026, 6, 4), date(2026, 6, 5)
TODAY_KEYS = {"virtual_date", "target_date", "start", "end"}   # the replay day as itself or a forecast range

REQUESTS = [
    ("/api/data/coverage", {}),
    ("/api/routes", {}),
    ("/api/routes/22/history", {}),
    ("/api/routes/22/history", {"start": "2001-01-01"}),
    ("/api/routes/169/history", {}),
    ("/api/rankings", {"metric": "rides_per_scheduled_hour", "daytype": "W"}),
    ("/api/rankings", {"metric": "observed_daily_demand", "daytype": "A"}),
    ("/api/rankings", {"metric": "rides_per_scheduled_trip", "daytype": "U", "period": "development"}),
    ("/api/rankings", {"metric": "route_overlap_review"}),
    ("/api/routes/compare", {"routes": "49,X49,22", "daytype": "W"}),
    ("/api/routes/compare", {"routes": "10,22", "daytype": "W", "same_days": "true"}),
    ("/api/route-groups", {}),
    ("/api/map/lines", {}),
    ("/api/network/trend", {}),
    ("/api/network/trend", {"start": "2026-05-01"}),
    ("/api/models/summary", {}),
    ("/api/forecasts", {}),
    ("/api/forecasts", {"route": "22"}),
]


@pytest.fixture
def session(client, stage7):
    r = client.post("/api/replays", json={"start_date": TODAY.isoformat()})
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


def walk(obj, key=None):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v, key)
    else:
        yield key, obj


@pytest.mark.parametrize("url, params", REQUESTS)
def test_no_date_after_the_cutoff_in_any_replay_response(client, session, url, params):
    r = client.get(url, params={**params, "session": session})
    assert r.status_code == 200, (url, r.text)
    body = r.json()
    later = sorted({d for d in ISO.findall(json.dumps(body)) if date.fromisoformat(d) > TODAY})
    assert not later, (url, later[:5])
    for key, value in walk(body):
        if isinstance(value, str) and ISO.fullmatch(value) and date.fromisoformat(value) == TODAY:
            assert key in TODAY_KEYS, (url, key, value)       # the replay day appears only as the replay day
    assert body["cutoff"]["permitted_through"] in (REVEALED.isoformat(), None) or url == "/api/forecasts"


def test_no_actual_for_a_day_not_yet_revealed(client, session):
    body = client.get("/api/forecasts", params={"session": session, "route": "22"}).json()
    by_day = {f["target_date"]: f for f in body["forecasts"] if f["method"] == "rf_demand"}
    assert max(by_day) == TODAY.isoformat()                                  # today's forecast is visible...
    assert by_day[TODAY.isoformat()]["actual"] == {"rides": None, "revealed": False,
                                                   "reason": by_day[TODAY.isoformat()]["actual"]["reason"]}
    assert "not revealed yet" in by_day[TODAY.isoformat()]["actual"]["reason"]  # ...its actual is not
    assert by_day[REVEALED.isoformat()]["actual"]["revealed"] is True and by_day[REVEALED.isoformat()]["actual"]["rides"]


def test_a_client_cutoff_with_a_session_is_refused(client, session):
    r = client.get("/api/rankings", params={"metric": "rides_per_scheduled_hour", "session": session,
                                            "cutoff": "2026-07-31"})
    assert r.status_code == 422 and "comes from the replay session" in r.json()["detail"]
    r = client.post("/api/forecasts", json={"route": "22", "target_date": "2026-07-01", "session": session})
    assert r.status_code == 422 and "has not been reached" in r.json()["detail"]   # no forecast for a later day


def test_a_later_range_is_clipped_to_the_session(client, session):
    h = client.get("/api/routes/22/history", params={"session": session, "end": "2026-07-31"})
    assert h.status_code in (200, 422)
    if h.status_code == 200:
        assert max(d["service_date"] for d in h.json()["days"]) <= REVEALED.isoformat()
    f = client.get("/api/forecasts", params={"session": session, "route": "22", "end": "2026-07-31"}).json()
    assert max(x["target_date"] for x in f["forecasts"]) == TODAY.isoformat()


def test_replay_rankings_use_revealed_history_only(client, session):
    body = client.get("/api/rankings", params={"metric": "rides_per_scheduled_hour", "daytype": "W",
                                               "session": session}).json()
    assert body["period"]["end"] == REVEALED.isoformat() and body["period"]["clipped_to_cutoff"] is True
    hist = client.get("/api/rankings", params={"metric": "rides_per_scheduled_hour", "daytype": "W"}).json()
    obs = {r["route"]: r["observed_days"] for r in body["rows"]}
    assert all(obs[r["route"]] <= r["observed_days"] for r in hist["rows"] if r["route"] in obs)
    assert sum(obs.values()) < sum(r["observed_days"] for r in hist["rows"])   # fewer days counted than in history


def test_unknown_session_is_404(client, stage7):
    assert client.get("/api/routes", params={"session": "nope"}).status_code == 404
