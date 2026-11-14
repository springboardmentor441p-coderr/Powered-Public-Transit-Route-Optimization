"""Automated FastAPI TestClient suite covering all 13 Manhattan Bus Optimization endpoints."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.routers import gtfs as gtfs_router

ROOT = Path(__file__).resolve().parents[2]
APP_DATA_DIR = ROOT / "app_data"
REAL_OCT_GTFS = ROOT / "data" / "raw" / "gtfs" / "manhattan" / "2026-10-17" / "original.zip"


@pytest.fixture(scope="module")
def client():
    app = create_app(APP_DATA_DIR)
    with TestClient(app) as c:
        yield c


def _build_synthetic_gtfs_zip(
    *,
    include_evil_traversal: bool = False,
    missing_stops_file: bool = False,
) -> bytes:
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


@pytest.mark.parametrize(
    ("endpoint", "expected_keys"),
    [
        ("/api/health", ["status"]),
        ("/api/overview", ["period", "source", "version", "overview"]),
        ("/api/network/daily", ["period", "source", "count", "rows", "metadata"]),
        ("/api/network/hourly?period=jan_sep_typical", ["period", "source", "count", "rows"]),
        ("/api/routes", ["period", "source", "count", "rows"]),
        (
            "/api/routes/M15+",
            ["period", "source", "route", "profile", "thresholds", "hourly_patterns", "overlaps", "geometry"],
        ),
        (
            "/api/routes/M1/forecast",
            ["period", "source", "route", "validation_summary", "test_summary", "october_daily", "october_hourly"],
        ),
        (
            "/api/groups",
            ["period", "source", "metadata", "pca_variance", "routes", "group_profiles", "k_selection", "geometries"],
        ),
        ("/api/review?day_group=weekday&review_category=more_trips_candidate", ["period", "source", "count", "rows", "metadata"]),
        ("/api/scenarios/plan", ["period", "source", "count", "rows", "metadata"]),
        (
            "/api/evaluation",
            ["period", "source", "validation", "test", "october", "official_test_runs_logged", "official_test_log"],
        ),
    ],
)
def test_get_endpoints_smoke_and_key_fields(client: TestClient, endpoint: str, expected_keys: list[str]):
    res = client.get(endpoint)
    assert res.status_code == 200
    body = res.json()
    for key in expected_keys:
        assert key in body, f"Missing '{key}' in response for {endpoint}"


def test_overview_network_and_null_handling(client: TestClient):
    ov = client.get("/api/overview").json()
    assert ov["version"]["official_test_runs_logged"] == 1
    assert ov["overview"]["cleaning"]["routes_kept"] == 41
    assert len(ov["overview"]["cleaning"]["dropped_routes"]) == 5

    daily_rows = client.get("/api/network/daily").json()["rows"]
    assert len(daily_rows) >= 290
    jan10 = [r for r in daily_rows if r["date"] == "2026-01-10"][0]
    assert jan10["is_missing"] is True
    assert jan10["total_ridership"] is None  # missing values stay null, never 0

    hourly = client.get("/api/network/hourly?period=jan_sep_typical").json()
    assert hourly["count"] == 72

    # M98 does not operate Saturday/Sunday service; verify missing thresholds stay null
    m98_detail = client.get("/api/routes/M98").json()
    assert m98_detail["profile"]["trips_per_saturday"] == 0
    assert m98_detail["profile"]["trips_per_sunday"] == 0
    assert m98_detail["profile"]["p75_saturday"] is None
    assert m98_detail["profile"]["p75_sunday"] is None


@pytest.mark.parametrize(
    ("bad_url", "expected_status"),
    [
        ("/api/network/daily?period_tag=invalid", 400),
        ("/api/network/hourly?period=invalid", 400),
        ("/api/routes/NON_EXISTENT", 404),
        ("/api/routes/NON_EXISTENT/forecast", 404),
        ("/api/review?day_group=holiday", 400),
        ("/api/review?sort_by=nonexistent_col", 400),
    ],
)
def test_get_endpoint_error_cases(client: TestClient, bad_url: str, expected_status: int):
    assert client.get(bad_url).status_code == expected_status


def test_evaluation_and_pca_match_reports(client: TestClient):
    # Check 5a: October baseline WAPE (11.69% on 12,270 active hours) matches report & summary CSV
    ev = client.get("/api/evaluation").json()
    assert ev["official_test_runs_logged"] == 1
    assert "11.69%" in ev["october"]["headline"]
    assert "12.28%" in ev["october"]["headline"]
    assert "11.70%" not in ev["october"]["headline"]
    assert "did not beat" in ev["october"]["headline"].lower()
    assert "not a model feature" in ev["october"]["limitations"][0].lower()
    assert len(ev["validation"]["forecast_comparison"]) == 6

    # Check 5b: 40-route PCA variance (36.1% / 23.1% -> 59.1%) matches exported report CSV & /api/groups
    grp = client.get("/api/groups").json()
    assert grp["metadata"]["outlier_route"] == "M35"
    assert len(grp["routes"]) == 41
    assert {int(p["group_id"]) for p in grp["group_profiles"]} >= {1, 2, 3, 0}

    pca_rows = grp["pca_variance"]
    assert len(pca_rows) == 2
    assert pca_rows[0]["component"] == "PC1"
    assert pca_rows[0]["explained_variance_pct"] == pytest.approx(36.1, abs=0.05)
    assert pca_rows[1]["component"] == "PC2"
    assert pca_rows[1]["explained_variance_pct"] == pytest.approx(23.1, abs=0.05)
    assert pca_rows[1]["cumulative_variance_pct"] == pytest.approx(59.1, abs=0.05)
    assert grp["metadata"]["pca_explained_variance_ratio"] == [
        pca_rows[0]["explained_variance_ratio"],
        pca_rows[1]["explained_variance_ratio"],
    ]

    report_pca_csv = ROOT / "reports" / "tables" / "m3_clustering_pca_variance.csv"
    if report_pca_csv.exists():
        ref_pca = pd.read_csv(report_pca_csv)
        assert ref_pca["explained_variance_pct"].tolist() == [
            pca_rows[0]["explained_variance_pct"],
            pca_rows[1]["explained_variance_pct"],
        ]


def test_scenarios_exact_math_and_exclusivity_cap(client: TestClient):
    plan = client.get("/api/scenarios/plan").json()
    assert plan["count"] == 39

    # 1. Exact Step 8 parity check against src/recommend_adjustments.py
    step8_csv = pd.read_csv(APP_DATA_DIR / "step8_candidate_scenarios.csv")
    ref = step8_csv.iloc[0]  # M1 weekday night (-20%, exclusive_stop_share=0.2687 < 0.60)
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

    # 2. Boundary checks at exact -50% and +50%
    for bound in (-50.0, 50.0):
        b_resp = client.post(
            "/api/scenarios",
            json={"route": "M1", "day_group": "weekday", "time_band": "midday", "trip_change_pct": bound},
        )
        assert b_resp.status_code == 200

    # 3. High-exclusivity route (>=60% exclusive stops) applies -10% cut cap + warning by default
    review_df = pd.read_csv(APP_DATA_DIR / "review_list.csv")
    excl_cell = review_df[review_df["exclusive_stop_share"] >= 0.60].iloc[0]

    capped = client.post(
        "/api/scenarios",
        json={
            "route": str(excl_cell["route"]),
            "day_group": str(excl_cell["day_group"]),
            "time_band": str(excl_cell["time_band"]),
            "trip_change_pct": -25.0,
        },
    )
    assert capped.status_code == 200
    c_sc = capped.json()["scenario"]
    assert c_sc["requested_trip_change_pct"] == -25.0
    assert c_sc["scenario_trip_change_pct"] == -10.0
    assert c_sc["guardrail_capped"] is True
    assert c_sc["max_recommended_cut_pct"] == -10.0
    assert c_sc["guardrail_status"] == "capped_at_10pct_exclusivity_guardrail"
    assert c_sc["guardrail_warning"] is not None
    assert "capped at -10%" in c_sc["guardrail_warning"].lower()

    # Optional uncapped simulation flag still warns while computing requested cut
    uncapped = client.post(
        "/api/scenarios",
        json={
            "route": str(excl_cell["route"]),
            "day_group": str(excl_cell["day_group"]),
            "time_band": str(excl_cell["time_band"]),
            "trip_change_pct": -25.0,
            "apply_guardrail_cap": False,
        },
    )
    assert uncapped.status_code == 200
    u_sc = uncapped.json()["scenario"]
    assert u_sc["scenario_trip_change_pct"] == -25.0
    assert u_sc["guardrail_capped"] is False
    assert u_sc["guardrail_status"] == "exceeds_10pct_exclusivity_guardrail"
    assert u_sc["guardrail_warning"] is not None


@pytest.mark.parametrize(
    ("payload", "expected_status", "detail_fragment"),
    [
        (
            {"route": "UNKNOWN_M999", "day_group": "weekday", "time_band": "midday", "trip_change_pct": 10},
            404,
            "not found",
        ),
        (
            {"route": "M98", "day_group": "weekend", "time_band": "midday", "trip_change_pct": 10},
            404,
            "no active scheduled cell",
        ),
        (
            {"route": "M1", "day_group": "holiday", "time_band": "midday", "trip_change_pct": 10},
            422,
            "day_group",
        ),
        (
            {"route": "M1", "day_group": "weekday", "time_band": "late_night", "trip_change_pct": 10},
            422,
            "time_band",
        ),
        (
            {"route": "M1", "day_group": "weekday", "time_band": "midday", "trip_change_pct": -55},
            422,
            "trip_change_pct",
        ),
        (
            {"route": "M1", "day_group": "weekday", "time_band": "midday", "trip_change_pct": 55},
            422,
            "trip_change_pct",
        ),
    ],
)
def test_scenarios_rejects_invalid_inputs(
    client: TestClient,
    payload: dict[str, object],
    expected_status: int,
    detail_fragment: str,
):
    resp = client.post("/api/scenarios", json=payload)
    assert resp.status_code == expected_status
    assert detail_fragment.lower() in resp.text.lower()


def test_gtfs_upload_valid_zip_slip_and_decompression_bomb(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    # 1. Valid GTFS upload containing Manhattan M1 and non-Manhattan B44 + >=24h spillover
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

    # 3. Non-zip extension & missing stops.txt rejected cleanly
    assert (
        client.post(
            "/api/gtfs/upload",
            files={"file": ("routes.csv", b"route_id\nM1\n", "text/csv")},
        ).status_code
        == 400
    )
    bad_gtfs = client.post(
        "/api/gtfs/upload",
        files={"file": ("incomplete.zip", _build_synthetic_gtfs_zip(missing_stops_file=True), "application/zip")},
    )
    assert bad_gtfs.status_code == 400
    assert "stops.txt" in bad_gtfs.json()["detail"]

    # 4. Small compressed zip expanding beyond 300 MB uncompressed limit rejected BEFORE extraction (413)
    bomb_buf = io.BytesIO()
    chunk_5mb = b"0" * (5 * 1024 * 1024)
    with zipfile.ZipFile(bomb_buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for i in range(62):  # 310 MB uncompressed -> < 1 MB compressed
            z.writestr(f"pad_{i:02d}.txt", chunk_5mb)
    bomb_bytes = bomb_buf.getvalue()
    assert len(bomb_bytes) < gtfs_router.MAX_UPLOAD_BYTES
    bomb_res = client.post(
        "/api/gtfs/upload",
        files={"file": ("bomb.zip", bomb_bytes, "application/zip")},
    )
    assert bomb_res.status_code == 413
    assert "300 mb" in bomb_res.json()["detail"].lower()

    # 5. Enforce compressed upload byte limit (413)
    monkeypatch.setattr(gtfs_router, "MAX_UPLOAD_BYTES", 50)
    too_large = client.post(
        "/api/gtfs/upload",
        files={"file": ("big.zip", valid_bytes, "application/zip")},
    )
    assert too_large.status_code == 413


@pytest.mark.skipif(not REAL_OCT_GTFS.exists(), reason="Local raw GTFS feed not present in fresh clone")
def test_gtfs_upload_real_manhattan_october_feed(client: TestClient):
    with open(REAL_OCT_GTFS, "rb") as fh:
        res = client.post(
            "/api/gtfs/upload",
            files={"file": ("2026-10-17_manhattan.zip", fh, "application/zip")},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["integrity"]["referential_integrity_passed"] is True
    assert body["summary"]["routes_with_trips"] == 41
    assert body["summary"]["study_routes_matched"] == 41
    assert body["summary"]["non_study_routes_schedule_only"] == 266


def test_app_never_modifies_test_runs_log():
    log_path = ROOT / "reports" / "test_runs.log"
    lines = [l.strip() for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
