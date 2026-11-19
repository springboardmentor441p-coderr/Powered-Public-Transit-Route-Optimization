"""Tests for the replay clock, saved forecasts, history endpoints and day scenarios."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.forecasting import forecast_day
from backend.app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
APP_DATA_DIR = ROOT / "app_data"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    runtime = tmp_path_factory.mktemp("runtime")
    app = create_app(APP_DATA_DIR, runtime_dir=runtime)
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------- forecasting


def test_replay_forecasts_match_saved_october_predictions():
    """With every lag allowed, the replay must give the same numbers as the saved October check."""
    oc = pd.read_parquet(APP_DATA_DIR / "october_hourly_forecast_vs_actual.parquet")
    feats = pd.read_csv(APP_DATA_DIR / "model_route_features.csv")
    for day in ("2026-10-18", "2026-10-24", "2026-10-31"):
        out = forecast_day(oc, feats, day, delay_days=1)
        merged = out.merge(oc[["route", "date", "hour", "pred_ridership"]], on=["route", "date", "hour"],
                           suffixes=("", "_saved"))
        assert len(merged) == len(oc[oc["date"] == day])
        assert np.abs(merged["pred_boardings"] - merged["pred_ridership_saved"]).max() < 0.01


def test_longer_delay_hides_recent_lags():
    oc = pd.read_parquet(APP_DATA_DIR / "october_hourly_forecast_vs_actual.parquet")
    feats = pd.read_csv(APP_DATA_DIR / "model_route_features.csv")
    out = forecast_day(oc, feats, "2026-10-25", delay_days=14)
    assert out["lag_7d"].isna().all()
    assert out["lag_14d"].notna().any()
    assert (out["latest_ridership_date_used"] == "2026-10-11").all()
    assert (out["status"] == "normal_fewer_lags").all()


# ---------------------------------------------------------------- replay


def test_replay_hides_actuals_until_revealed(client):
    state = client.post("/api/replays", json={"start_date": "2026-10-18", "delay_days": 1}).json()
    sid = state["session"]["session_id"]
    assert state["virtual_date"] == "2026-10-18"
    assert state["forecast_record_count"] > 0
    assert all(d["actual_boardings"] is None for d in state["network_daily"])

    state = client.post(f"/api/replays/{sid}/control", json={"action": "advance"}, params={"route": "M15+"}).json()
    assert state["virtual_date"] == "2026-10-19"
    days = {d["date"]: d for d in state["network_daily"]}
    assert days["2026-10-18"]["actual_boardings"] is not None
    assert days["2026-10-19"]["actual_boardings"] is None
    hourly = state["route_detail"]["current_day_hourly"]
    assert hourly and all("actual_ridership" not in h for h in hourly)
    today = [d for d in state["route_detail"]["daily"] if d["date"] == "2026-10-19"][0]
    assert today["scheduled_departures"] > 0


def test_replay_never_duplicates_or_overwrites_forecasts(client):
    sid = client.post("/api/replays", json={"start_date": "2026-10-20"}).json()["session"]["session_id"]
    first = client.get(f"/api/replays/{sid}/forecasts", params={"target_date": "2026-10-20"}).json()["rows"]
    for _ in range(3):
        client.get(f"/api/replays/{sid}", params={"route": "M15+"})
    again = client.get(f"/api/replays/{sid}/forecasts", params={"target_date": "2026-10-20"}).json()["rows"]
    assert len(first) == len(again)
    keys = {(r["route"], r["hour"]) for r in again}
    assert len(keys) == len(again)
    assert [r["saved_at_wall"] for r in first] == [r["saved_at_wall"] for r in again]
    row = again[0]
    for field in ("issued_at", "model_version", "schedule_snapshot", "latest_ridership_date_used", "status"):
        assert row[field]


def test_replay_stops_at_end_and_reset_keeps_old_session(client):
    sid = client.post("/api/replays", json={"start_date": "2026-10-30"}).json()["session"]["session_id"]
    client.post(f"/api/replays/{sid}/control", json={"action": "advance"})
    done = client.post(f"/api/replays/{sid}/control", json={"action": "advance"}).json()
    assert done["completed"] is True
    assert done["virtual_date"] == "2026-10-31"
    assert client.post(f"/api/replays/{sid}/control", json={"action": "advance"}).status_code == 409

    new = client.post(f"/api/replays/{sid}/control", json={"action": "reset", "start_date": "2026-10-18"}).json()
    assert new["session"]["session_id"] != sid
    old = client.get(f"/api/replays/{sid}").json()
    assert old["session"]["replaced_by"] == new["session"]["session_id"]


def test_replay_rejects_test_period_and_bad_delay(client):
    assert client.post("/api/replays", json={"start_date": "2026-09-01"}).status_code == 422
    assert client.post("/api/replays", json={"delay_days": 3}).status_code == 422


def test_history_endpoint_respects_replay_reveal(client):
    sid = client.post("/api/replays", json={"start_date": "2026-10-18", "delay_days": 1}).json()["session"]["session_id"]
    res = client.get("/api/routes/M15+/daily", params={"replay_id": sid, "start": "2026-10-10"}).json()
    assert max(r["date"] for r in res["rows"]) == "2026-10-17"
    assert res["replay"]["latest_revealed_date"] == "2026-10-17"


# ---------------------------------------------------------------- history


def test_route_daily_lists_excluded_dates(client):
    res = client.get("/api/routes/M15+/daily", params={"start": "2026-10-01", "end": "2026-10-31"}).json()
    dates = [r["date"] for r in res["rows"]]
    assert "2026-10-12" not in dates
    assert {"date": "2026-10-12", "reason": res["excluded_dates"][0]["reason"]} in res["excluded_dates"]
    assert client.get("/api/routes/M15+/daily", params={"start": "2026-07-01"}).status_code == 422


def test_compare_routes(client):
    res = client.get("/api/compare", params={"routes": "M15,M15+"}).json()
    assert [r["route"] for r in res["routes"]] == ["M15", "M15+"]
    for r in res["routes"]:
        m = r["metrics"]
        assert m["riders_per_service_hour"] == pytest.approx(m["total_boardings"] / m["total_service_hours"], rel=1e-3)
    assert client.get("/api/compare", params={"routes": "M15"}).status_code == 422


def test_rankings_eligibility_and_ties(client):
    res = client.get("/api/rankings", params={"day_type": "Typical Saturday", "min_days": 15}).json()
    assert res["eligible_count"] == 0
    assert all(r["rank"] is None and r["ineligible_reason"] for r in res["rows"])

    res = client.get("/api/rankings", params={"day_type": "Typical Weekday"}).json()
    ranked = [r for r in res["rows"] if r["rank"] is not None]
    values = [r["riders_per_service_hour"] for r in ranked]
    assert values == sorted(values, reverse=True)
    assert ranked[0]["rank"] == 1
    assert res["resolved_config"]["min_observed_days"] == 10
    assert len(res["rows"]) == 41


# ---------------------------------------------------------------- day scenarios


def test_day_scenario_keeps_riders_fixed_and_saves(client):
    body = {"route": "M101", "date": "2026-10-20", "trip_change_pct": 10, "save": True, "label": "pytest"}
    res = client.post("/api/scenarios/day", json=body).json()
    base, scen = res["result"]["baseline"], res["result"]["scenario"]
    assert scen["boardings"] == base["boardings"]
    assert scen["trips_running"] == pytest.approx(base["trips_running"] * 1.10, rel=1e-3)
    assert scen["riders_per_trip"] < base["riders_per_trip"]
    assert res["scenario_id"]
    assert scen["scheduled_departures"] == pytest.approx(base["scheduled_departures"] * 1.10, rel=1e-3)
    sep = client.post("/api/scenarios/day", json={"route": "M101", "date": "2026-09-15"}).json()
    assert sep["result"]["baseline"]["scheduled_departures"] is None
    saved = client.get("/api/scenarios/saved").json()["rows"]
    assert any(s["scenario_id"] == res["scenario_id"] for s in saved)


def test_day_scenario_stress_and_forecast_source(client):
    res = client.post(
        "/api/scenarios/day",
        json={"route": "M101", "date": "2026-10-20", "demand_multiplier": 1.2, "demand_source": "forecast"},
    ).json()
    assert res["demand_label"].startswith("Predicted")
    assert res["result"]["stress_only"]["boardings"] == pytest.approx(res["result"]["baseline"]["boardings"] * 1.2, rel=1e-3)
    bad = client.post("/api/scenarios/day", json={"route": "M101", "date": "2026-09-15", "demand_source": "forecast"})
    assert bad.status_code == 422
