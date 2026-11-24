"""Stage 8: the scenario API on routeranker_test (spec 9.15, 9.17.3, 9.19.1).

Every saved scenario here goes to the TEST database only (the client fixture); the app database is never touched.
"""
from __future__ import annotations

import json
import re
from datetime import date

import pytest

from backend.tests.test_api_visible_text import FIELD, SPEC

ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
TODAY, REVEALED = date(2026, 6, 5), date(2026, 6, 4)
TODAY_KEYS = {"virtual_date", "target_date", "start", "end"}
R49 = {"baseline": {"routes": ["49"], "period": "full_matched_window", "daytype": "W"},
       "service": [{"trips": {"how": "percent", "value": 20}}]}
GROUP_STRESS = {"baseline": {"group_id": 1, "period": "full_matched_window", "daytype": "U"},
                "demand_stress": {"percent": -15}}
TEXT_KEYS = {"text", "sentence", "ranking_sentence", "note", "label", "demand_label", "daytype_label", "reason"}


@pytest.fixture
def api(client, stage8):
    return client


def calc(api, body, **params):
    r = api.post("/api/scenarios/calculate", json=body, params=params)
    assert r.status_code == 200, r.text
    return r.json()["scenario"]


def row(s, route):
    return next(x for x in s["result"]["rows"] if x["route"] == route)


def texts(obj, key=None):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from texts(v, "reason" if key == "reasons" else k)
    elif isinstance(obj, list):
        for v in obj:
            yield from texts(v, key)
    elif isinstance(obj, str) and (key in TEXT_KEYS or (key or "").endswith("_reason")):
        yield key, obj


# --------------------------------------------------------------------------------------- calculation
def test_route_49_plus_20_percent_trips_matches_the_rankings_baseline(api):
    s = calc(api, R49)
    r = row(s, "49")
    rk = api.get("/api/rankings", params={"metric": "rides_per_scheduled_hour", "daytype": "W"}).json()
    ref = next(x for x in rk["rows"] if x["route"] == "49")
    assert r["baseline"]["rides_per_scheduled_hour"] == ref["value"]
    assert r["baseline"]["rank_rides_per_scheduled_hour"] == ref["rank"]
    assert r["scenario"]["rides_per_day"] == r["baseline"]["rides_per_day"]           # demand held fixed
    assert r["scenario"]["rides_per_scheduled_hour"] == pytest.approx(ref["value"] / 1.2, rel=1e-12)
    assert r["scenario"]["mean_trip_minutes"] == pytest.approx(r["baseline"]["mean_trip_minutes"], rel=1e-12)
    assert s["baseline"]["period"]["end"] == "2026-07-31" and s["saved"] is False
    kinds = [a["kind"] for a in s["assumptions"]]
    assert {"baseline", "demand", "service", "duration", "ranking", "interpretation"} <= set(kinds)


def test_a_zero_percent_change_returns_the_baseline_exactly(api):
    s = calc(api, {**R49, "service": [{"trips": {"how": "percent", "value": 0}}]})
    r = row(s, "49")
    assert {k: v for k, v in r["scenario"].items()} == {k: v for k, v in r["baseline"].items()}


def test_group_stress_minus_15_percent_scales_rides_by_0_85_and_keeps_missing_values_missing(api):
    s = calc(api, GROUP_STRESS)
    assert s["baseline"]["group"]["group_id"] == 1
    seen_zero = False
    for x in s["result"]["rows"]:
        b, z = x["baseline"], x["scenario"]
        if b["rides_sum"] is None:
            assert z["rides_sum"] is None and z["rides_per_scheduled_trip"] is None
            assert z["reasons"]["rides_per_trip"]
            seen_zero |= x["structural_zero"]
        else:
            assert z["rides_sum"] == b["rides_sum"] * 0.85
            assert z["scheduled_trips_sum"] == b["scheduled_trips_sum"]
    assert seen_zero, "group 1 has routes with no Sunday service: they must appear, unavailable, not 0"
    assert any(a["kind"] == "demand_stress" and "not a prediction" in a["text"] for a in s["assumptions"])


def test_route_1001_gets_no_service_change(api):
    r = api.post("/api/scenarios/calculate", json={"baseline": {"routes": ["1001"], "period": "full_matched_window",
                                                                "daytype": "W"},
                                                   "service": [{"trips": {"how": "per_day", "value": 10}}]})
    assert r.status_code == 422 and "no matching timetable" in r.json()["detail"]


@pytest.mark.parametrize("body, words", [
    ({**R49, "service": [{"trips": {"how": "per_day", "value": -3}}]}, "cannot be negative"),
    ({**R49, "service": [{"trips": {"how": "percent", "value": 500}}]}, "between -100 and 200"),
    ({**R49, "demand_stress": {"percent": -99}}, "between -90 and 100"),
    ({"baseline": {"routes": ["49"], "start": "2026-07-01", "end": "2026-08-15", "daytype": "W"},
      "service": R49["service"]}, "after the last available date"),
    ({"baseline": {"routes": ["49"], "start": "2026-07-10", "end": "2026-07-01", "daytype": "W"},
      "service": R49["service"]}, "start must not be after end"),
    ({"baseline": {"routes": ["no-such-route"], "daytype": "W"}, "service": R49["service"]}, "no recorded rides"),
    ({"baseline": {"routes": ["49"], "group_id": 1, "daytype": "W"}, "service": R49["service"]}, "either routes or"),
    ({"baseline": {"routes": ["49"], "demand": "predicted"}, "service": R49["service"]}, "only in a replay"),
    ({"baseline": {"routes": ["49"], "daytype": "W"}}, "needs a service change or a demand assumption"),
])
def test_invalid_inputs_are_refused_with_a_reason(api, body, words):
    r = api.post("/api/scenarios/calculate", json=body)
    assert r.status_code == 422, r.text
    assert words in r.json()["detail"]


def test_an_unknown_field_is_refused(api):
    r = api.post("/api/scenarios/calculate", json={**R49, "elasticity": 0.4})
    assert r.status_code == 422


def test_visible_texts_are_plain_words(api):
    for body in (R49, GROUP_STRESS):
        s = api.post("/api/scenarios/calculate", json=body).json()
        found = list(texts(s))
        assert len(found) > 5
        for key, text in found:
            assert not SPEC.search(text) and not FIELD.search(text), (key, text)


# --------------------------------------------------------------------------------------- saving
def test_save_is_immutable_idempotent_and_recomputes_to_the_same_hash(api, stage8):
    body = {**R49, "name": "Route 49, 20 % more weekday trips"}
    r1 = api.post("/api/scenarios", json=body)
    assert r1.status_code == 201, r1.text
    s1 = r1.json()["scenario"]
    assert s1["version"] == 1 and s1["origin"] == "planner" and s1["saved_at"]
    assert s1["versions"]["data_version"] and s1["versions"]["group_version"]
    assert s1["result_sha256"] == calc(api, R49)["result_sha256"]
    r2 = api.post("/api/scenarios", json=body)                       # the same save again
    assert r2.status_code == 200 and r2.json()["scenario"]["scenario_id"] == s1["scenario_id"]
    assert r2.json()["scenario"]["saved_at"] == s1["saved_at"]       # nothing rewritten
    listed = api.get("/api/scenarios").json()["scenarios"]
    assert any(x["scenario_id"] == s1["scenario_id"] for x in listed)
    got = api.get(f"/api/scenarios/{s1['scenario_id']}").json()["scenario"]
    assert got["result"] == s1["result"] and got["assumptions"] == s1["assumptions"]
    chk = api.get(f"/api/scenarios/{s1['scenario_id']}/recompute").json()["check"]
    assert chk["identical"] is True and chk["recomputed_sha256"] == s1["result_sha256"] == chk["stored_json_sha256"]
    assert api.delete(f"/api/scenarios/{s1['scenario_id']}").status_code == 405  # no delete endpoint
    assert api.put(f"/api/scenarios/{s1['scenario_id']}", json=body).status_code == 405


def test_editing_makes_a_new_version_and_leaves_the_first_unchanged(api):
    v1 = api.post("/api/scenarios", json={**R49, "name": "Route 49 edit test"}).json()["scenario"]
    edited = {**R49, "service": [{"trips": {"how": "percent", "value": 30}}], "name": "Route 49 edit test",
              "revises": v1["scenario_id"]}
    r = api.post("/api/scenarios", json=edited)
    assert r.status_code == 201, r.text
    v2 = r.json()["scenario"]
    assert (v2["version"], v2["lineage_id"], v2["parent_scenario_id"]) == (2, v1["lineage_id"], v1["scenario_id"])
    assert v2["scenario_id"] != v1["scenario_id"] and v2["result_sha256"] != v1["result_sha256"]
    again = api.get(f"/api/scenarios/{v1['scenario_id']}").json()
    assert again["scenario"]["result_sha256"] == v1["result_sha256"]
    assert [x["version"] for x in again["lineage"]] == [1, 2]
    bad = api.post("/api/scenarios", json={**edited, "revises": "scn_does_not_exist"})
    assert bad.status_code == 422 and "cannot be revised" in bad.json()["detail"]


def test_a_name_is_required_to_save(api):
    r = api.post("/api/scenarios", json={**R49, "name": "   "})
    assert r.status_code == 422 and "name" in r.json()["detail"]


# --------------------------------------------------------------------------------------- replay
@pytest.fixture
def session(api, stage7):
    r = api.post("/api/replays", json={"start_date": TODAY.isoformat()})
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


def no_later_dates(body, today=TODAY):
    later = sorted({d for d in ISO.findall(json.dumps(body)) if date.fromisoformat(d) > today})
    assert not later, later[:5]

    def walk(o, key=None):
        if isinstance(o, dict):
            for k, v in o.items():
                yield from walk(v, k)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v, key)
        else:
            yield key, o
    for key, value in walk(body):
        if isinstance(value, str) and ISO.fullmatch(value) and date.fromisoformat(value) == today:
            assert key in TODAY_KEYS, (key, value)


def test_replay_scenarios_use_revealed_rides_only_and_show_no_later_date(api, session):
    r = api.post("/api/scenarios/calculate", json=R49, params={"session": session})
    assert r.status_code == 200, r.text
    body = r.json()
    no_later_dates(body)
    assert body["mode_label"] == "Historical replay" and body["cutoff"]["source"] == "replay session"
    s = body["scenario"]
    assert s["baseline"]["period"]["end"] == REVEALED.isoformat() and s["baseline"]["period"]["clipped_to_cutoff"]
    hist = calc(api, R49)
    assert row(s, "49")["baseline"]["days"] < row(hist, "49")["baseline"]["days"]
    late = api.post("/api/scenarios/calculate", params={"session": session},
                    json={**R49, "baseline": {"routes": ["49"], "start": "2026-05-01", "end": "2026-06-10",
                                              "daytype": "W"}})
    assert late.status_code == 422 and "after the last available date" in late.json()["detail"]
    assert api.post("/api/scenarios/calculate", json=R49,
                    params={"session": session, "cutoff": "2026-07-01"}).status_code == 422


def test_a_replay_save_is_hidden_from_earlier_sessions_and_recomputes_identically_later(api, session):
    saved = api.post("/api/scenarios", json={**R49, "name": "Replay save"}, params={"session": session})
    assert saved.status_code == 201, saved.text
    body = saved.json()
    no_later_dates(body)
    s = body["scenario"]
    assert s["mode"] == "historical_replay" and s["session_id"] == session and s["saved_at"] is None
    assert s["cutoff"] == REVEALED.isoformat()
    listed = api.get("/api/scenarios", params={"session": session}).json()
    no_later_dates(listed)
    assert [x["scenario_id"] for x in listed["scenarios"]] == [s["scenario_id"]] or \
        s["scenario_id"] in [x["scenario_id"] for x in listed["scenarios"]]
    assert all(x["mode"] == "historical_replay" for x in listed["scenarios"])  # historical saves are hidden
    earlier = api.post("/api/replays", json={"start_date": "2026-06-03"}).json()["session_id"]
    assert api.get(f"/api/scenarios/{s['scenario_id']}", params={"session": earlier}).status_code == 404
    assert s["scenario_id"] not in [x["scenario_id"] for x in
                                    api.get("/api/scenarios", params={"session": earlier}).json()["scenarios"]]
    api.post(f"/api/replays/{session}/control", json={"action": "next_week"})
    chk = api.get(f"/api/scenarios/{s['scenario_id']}/recompute", params={"session": session}).json()
    assert chk["check"]["identical"] is True
    assert api.get(f"/api/scenarios/{s['scenario_id']}").status_code == 200  # historical analysis lists everything


def test_predicted_demand_uses_the_stored_forecast_and_keeps_it(api, session):
    fc = api.get("/api/forecasts", params={"session": session, "route": "22"}).json()["forecasts"]
    today = next(f for f in fc if f["target_date"] == TODAY.isoformat() and f["method"] == "rf_demand")
    body = {"baseline": {"routes": ["22"], "demand": "predicted"},
            "service": [{"trips": {"how": "percent", "value": 20}}], "demand_stress": {"percent": 20}}
    r = api.post("/api/scenarios/calculate", json=body, params={"session": session})
    assert r.status_code == 200, r.text
    no_later_dates(r.json())
    s = r.json()["scenario"]
    x = row(s, "22")
    assert x["baseline"]["rides_per_day"] == today["prediction"]           # the model's prediction, preserved
    assert x["scenario"]["rides_per_day"] == today["prediction"] * 1.2     # the stated assumption, separately
    assert x["baseline"]["trips_per_day"] == today["scheduled_trips"]
    assert s["versions"]["forecast_run_id"] and s["versions"]["model_version"]
    assert s["virtual_date"] == TODAY.isoformat() and s["baseline"]["daytype"] is None
