"""Automated FastAPI TestClient suite for the Manhattan Bus Transit Optimization backend."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.routers import gtfs as gtfs_router

ROOT = Path(__file__).resolve().parents[2]
APP_DATA_DIR = ROOT / "app_data"


@pytest.fixture(scope="module")
def client():
    app = create_app(APP_DATA_DIR)
    with TestClient(app) as c:
        yield c


def _build_synthetic_gtfs_zip(*, include_evil_traversal: bool = False, missing_stops_file: bool = False) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "routes.txt",
            "route_id,route_short_name,route_long_name,route_type\n"
            "M1,M1,Fifth Ave / Madison Ave,3\n"
            "B44,B44,Nostrand Ave Brooklyn,3\n",
        )
        z.writestr(
            "calendar.txt",
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            "WK,1,1,1,1,1,0,0,20260101,20261231\n"
            "SAT,0,0,0,0,0,1,0,20260101,20261231\n",
        )
        z.writestr(
            "trips.txt",
            "route_id,service_id,trip_id,direction_id,shape_id\n"
            "M1,WK,T_M1_AM,0,SH_M1\n"
            "M1,WK,T_M1_OWL,0,SH_M1\n"
            "B44,WK,T_B44_AM,0,SH_B44\n"
            "B44,SAT,T_B44_SAT,0,SH_B44\n",
        )
        if not missing_stops_file:
            z.writestr(
                "stops.txt",
                "stop_id,stop_name,stop_lat,stop_lon\n"
                "S1,5 Ave / 42 St,40.7536,-73.9810\n"
                "S2,5 Ave / 14 St,40.7359,-73.9936\n"
                "S3,Nostrand Ave / Fulton St,40.6805,-73.9498\n",
            )
        z.writestr(
            "stop_times.txt",
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T_M1_AM,08:00:00,08:00:00,S1,1\n"
            "T_M1_AM,08:30:00,08:30:00,S2,2\n"
            "T_M1_OWL,25:10:00,25:10:00,S1,1\n"
            "T_M1_OWL,25:40:00,25:40:00,S2,2\n"
            "T_B44_AM,09:00:00,09:00:00,S2,1\n"
            "T_B44_AM,09:20:00,09:20:00,S3,2\n"
            "T_B44_SAT,10:00:00,10:00:00,S2,1\n"
            "T_B44_SAT,10:25:00,10:25:00,S3,2\n",
        )
        z.writestr(
            "shapes.txt",
            "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
            "SH_M1,40.7536,-73.9810,1\n"
            "SH_M1,40.7359,-73.9936,2\n"
            "SH_B44,40.7359,-73.9936,1\n"
            "SH_B44,40.6805,-73.9498,2\n",
        )
        if include_evil_traversal:
            z.writestr("../../evil_zip_slip_test.txt", "should never be extracted")
    return buf.getvalue()


def test_overview_and_network_endpoints(client: TestClient):
    res = client.get("/api/overview")
    assert res.status_code == 200
    body = res.json()
    assert body["version"]["official_test_runs_logged"] == 1
    assert body["overview"]["cleaning"]["routes_kept"] == 41
    assert len(body["overview"]["cleaning"]["dropped_routes"]) == 5

    daily = client.get("/api/network/daily")
    assert daily.status_code == 200
    rows = daily.json()["rows"]
    assert len(rows) >= 290
    jan10 = [r for r in rows if r["date"] == "2026-01-10"][0]
    assert jan10["is_missing"] is True
    assert jan10["total_ridership"] is None  # missing values stay null, never 0

    hourly = client.get("/api/network/hourly?period=jan_sep_typical")
    assert hourly.status_code == 200
    assert hourly.json()["count"] == 72  # 3 day types * 24 hours

    bad_period = client.get("/api/network/hourly?period=invalid")
    assert bad_period.status_code == 400


def test_routes_detail_forecast_and_groups(client: TestClient):
    res = client.get("/api/routes")
    assert res.status_code == 200
    assert res.json()["count"] == 41

    detail = client.get("/api/routes/M15+")
    assert detail.status_code == 200
    d_body = detail.json()
    assert d_body["route"] == "M15+"
    assert {t["day_type"] for t in d_body["thresholds"]} >= {
        "Typical Weekday",
        "Typical Saturday",
        "Typical Sunday",
    }
    assert len(d_body["geometry"]["polylines"]) >= 1
    assert any(o["overlap_category"] == "same_family" for o in d_body["overlaps"])

    missing = client.get("/api/routes/NON_EXISTENT")
    assert missing.status_code == 404

    fc = client.get("/api/routes/M1/forecast")
    assert fc.status_code == 200
    fc_body = fc.json()
    assert fc_body["test_summary"]["primary"] is not None
    assert len(fc_body["october_daily"]) == 14
    assert len(fc_body["october_hourly"]) > 0

    grp = client.get("/api/groups")
    assert grp.status_code == 200
    g_body = grp.json()
    assert g_body["metadata"]["outlier_route"] == "M35"
    assert len(g_body["routes"]) == 41
    assert {int(p["group_id"]) for p in g_body["group_profiles"]} >= {1, 2, 3, 0}


def test_review_evaluation_and_scenario_exact_math(client: TestClient):
    rev = client.get("/api/review?day_group=weekday&review_category=more_trips_candidate")
    assert rev.status_code == 200
    assert rev.json()["count"] > 0

    ev = client.get("/api/evaluation")
    assert ev.status_code == 200
    ev_body = ev.json()
    assert ev_body["official_test_runs_logged"] == 1
    assert "did not beat" in ev_body["october"]["headline"]
    assert len(ev_body["validation"]["forecast_comparison"]) == 6

    plan = client.get("/api/scenarios/plan")
    assert plan.status_code == 200
    assert plan.json()["count"] == 39

    # Compare POST /api/scenarios directly against Step 8 CSV output from src/recommend_adjustments.py
    step8_csv = pd.read_csv(APP_DATA_DIR / "step8_candidate_scenarios.csv")
    ref = step8_csv.iloc[0]

    resp = client.post(
        "/api/scenarios",
        json={
            "route": str(ref["route"]),
            "day_group": str(ref["day_group"]),
            "time_band": str(ref["time_band"]),
            "trip_change_pct": float(ref["scenario_trip_change_pct"]),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "riders stay the same when trips change" in body["assumption"].lower()
    sc = body["scenario"]
    assert sc["base_trips"] == int(ref["base_trips"])
    assert sc["new_trips"] == int(ref["new_trips"])
    assert sc["delta_service_hours"] == pytest.approx(float(ref["delta_service_hours"]), abs=0.01)
    assert sc["new_riders_per_trip"] == pytest.approx(float(ref["new_riders_per_trip"]), abs=0.01)
    assert sc["sim_high_demand_hours"] == int(ref["sim_high_demand_hours"])
    assert sc["guardrail_status"] == str(ref["guardrail_status"])

    # Validation check on bad route / invalid percent
    assert (
        client.post(
            "/api/scenarios",
            json={"route": "NOPE", "day_group": "weekday", "time_band": "midday", "trip_change_pct": 10},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/scenarios",
            json={"route": "M1", "day_group": "weekday", "time_band": "midday", "trip_change_pct": -150},
        ).status_code
        == 422
    )


def test_gtfs_upload_valid_zip_slip_and_limits(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    # 1. Valid GTFS upload containing both Manhattan M1 and non-Manhattan B44 + >=24h spillover
    valid_bytes = _build_synthetic_gtfs_zip()
    res = client.post(
        "/api/gtfs/upload",
        files={"file": ("sample_gtfs.zip", valid_bytes, "application/zip")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["integrity"]["referential_integrity_passed"] is True
    assert data["integrity"]["times_ge_24h"] == 2
    assert data["summary"]["study_routes_matched"] == 1
    assert data["summary"]["non_study_routes_schedule_only"] == 1

    routes_by_id = {r["route_id"]: r for r in data["routes"]}
    assert routes_by_id["M1"]["has_ridership_history"] is True
    assert routes_by_id["M1"]["study_avg_daily_riders"] is not None
    assert routes_by_id["B44"]["has_ridership_history"] is False
    assert routes_by_id["B44"]["study_avg_daily_riders"] is None
    assert routes_by_id["B44"]["status_note"] == "no ridership history, schedule analysis only"

    # 2. Zip Slip traversal entry must be rejected before extraction
    evil_bytes = _build_synthetic_gtfs_zip(include_evil_traversal=True)
    evil_res = client.post(
        "/api/gtfs/upload",
        files={"file": ("evil.zip", evil_bytes, "application/zip")},
    )
    assert evil_res.status_code == 400
    assert "zip slip" in evil_res.json()["detail"].lower()
    assert not (ROOT / "evil_zip_slip_test.txt").exists()

    # 3. Non-zip extension rejected
    non_zip = client.post(
        "/api/gtfs/upload",
        files={"file": ("routes.csv", b"route_id\nM1\n", "text/csv")},
    )
    assert non_zip.status_code == 400

    # 4. Missing required GTFS file rejected cleanly
    missing_stops = _build_synthetic_gtfs_zip(missing_stops_file=True)
    bad_gtfs = client.post(
        "/api/gtfs/upload",
        files={"file": ("incomplete.zip", missing_stops, "application/zip")},
    )
    assert bad_gtfs.status_code == 400
    assert "stops.txt" in bad_gtfs.json()["detail"]

    # 5. Enforce max upload size check (HTTP 413)
    monkeypatch.setattr(gtfs_router, "MAX_UPLOAD_BYTES", 50)
    too_large = client.post(
        "/api/gtfs/upload",
        files={"file": ("big.zip", valid_bytes, "application/zip")},
    )
    assert too_large.status_code == 413


def test_app_never_modifies_test_runs_log():
    log_path = ROOT / "reports" / "test_runs.log"
    lines = [l.strip() for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
