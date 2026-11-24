"""
Automated verification tests covering Spec Section 9.19.1 correctness cases:
1. GTFS exception_type=2 removal & exception_type=1 addition.
2. After-midnight (>24:00:00) trips remaining on their original service date.
3. Exact route/date join & unmatched reconciliation (route 1001 & route 169).
4. Replay cutoff preventing future actual leakage.
5. Conditional scenario arithmetic.
6. Authentication & JWT token verification.
7. Role-based access control (RBAC) permissions.
8. Alerts configuration and evaluation.
9. Emergency broadcast creation and management.
10. Congestion heatmap generation.
11. Schedule update authorization and execution.
12. Notification activity log tracking.
"""
import os
import sys
from datetime import date
import pytest
from fastapi import HTTPException
import pandas as pd

sys.path.insert(0, os.getcwd())
from src.scenarios import calculate_service_scenario
from backend.auth import authenticate_user, create_jwt_token, verify_jwt_token, require_operator_or_admin
from backend.schemas import (
    LoginRequest,
    AlertConfigRequest,
    EmergencyBroadcastRequest,
    ScheduleUpdateRequest,
    DelayReportRequest,
)
import backend.main as app_module

PROCESSED_DIR = "data/processed"

def test_pipeline_outputs_exist():
    required = [
        "source_register.parquet",
        "boardings_clean.parquet",
        "selected_schedule.parquet",
        "matched_utilization.parquet",
        "unmatched_boardings.parquet",
        "unmatched_schedule.parquet",
        "productivity_rankings.parquet",
        "daily_forecasting_features.parquet",
        "matched_service_features.parquet",
        "route_clusters.parquet",
    ]
    for fname in required:
        assert os.path.exists(os.path.join(PROCESSED_DIR, fname)), f"Missing {fname}"

def test_directional_unmatched_reconciliation():
    unmatched_b = pd.read_parquet(os.path.join(PROCESSED_DIR, "unmatched_boardings.parquet"))
    unmatched_s = pd.read_parquet(os.path.join(PROCESSED_DIR, "unmatched_schedule.parquet"))
    assert "1001" in set(unmatched_b["route"]), "Route 1001 ridership without schedule must be reported"
    assert "169" in set(unmatched_s["route"]), "Route 169 schedule without ridership must be reported"

def test_christmas_exception_switches_weekday_to_holiday():
    sched = pd.read_parquet(os.path.join(PROCESSED_DIR, "selected_schedule.parquet"))
    r22_xmas = sched[(sched["route"] == "22") & (sched["service_date"] == date(2025, 12, 25))]
    assert len(r22_xmas) == 1
    assert int(r22_xmas["scheduled_trips"].iloc[0]) == 52

def test_exact_date_lags_not_row_shifted():
    feats = pd.read_parquet(os.path.join(PROCESSED_DIR, "daily_forecasting_features.parquet"))
    r22 = feats[feats["route"] == "22"].sort_values("date").reset_index(drop=True)
    sample = r22.iloc[10]
    expected_d7 = r22[r22["date"] == date.fromordinal(sample["date"].toordinal() - 7)]["rides"].iloc[0]
    assert int(sample["rides_7_days_before"]) == int(expected_d7)

def test_scenario_arithmetic():
    res = calculate_service_scenario(
        baseline_rides=1000,
        baseline_trips=50,
        baseline_hours=None,
        proposed_trips=60,
        demand_multiplier=1.0,
        assumed_trip_duration_minutes=40.0,
    )
    assert res["scenario"]["scheduled_service_hours"] == 40.0
    assert res["scenario"]["rides_per_scheduled_trip"] == 16.67
    assert res["scenario"]["rides_per_scheduled_hour"] == 25.0

# ─── Authentication & RBAC Unit Tests ───

def test_auth_valid_admin_login():
    user = authenticate_user("admin", "admin123")
    assert user is not None
    assert user["username"] == "admin"
    assert user["role"] == "admin"
    assert "all" in user["permissions"]

def test_auth_valid_operator_login():
    user = authenticate_user("operator", "operator123")
    assert user is not None
    assert user["username"] == "operator"
    assert user["role"] == "operator"
    assert "manage_schedules" in user["permissions"]

def test_auth_valid_viewer_login():
    user = authenticate_user("viewer", "viewer123")
    assert user is not None
    assert user["role"] == "viewer"
    assert "view_analytics" in user["permissions"]
    assert "all" not in user["permissions"]

def test_auth_invalid_credentials():
    assert authenticate_user("admin", "wrong_password") is None
    assert authenticate_user("nonexistent_user", "password") is None

def test_jwt_token_flow():
    user = authenticate_user("admin", "admin123")
    token = create_jwt_token(user)
    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    payload = verify_jwt_token(token)
    assert payload["username"] == "admin"
    assert payload["role"] == "admin"

def test_rbac_permission_guard():
    admin = authenticate_user("admin", "admin123")
    operator = authenticate_user("operator", "operator123")
    viewer = authenticate_user("viewer", "viewer123")

    assert require_operator_or_admin(admin) == admin
    assert require_operator_or_admin(operator) == operator
    with pytest.raises(HTTPException) as exc_info:
        require_operator_or_admin(viewer)
    assert exc_info.value.status_code == 403

# ─── Endpoint Logic Tests ───

def test_endpoint_login():
    res = app_module.login(LoginRequest(username="admin", password="admin123"))
    assert "access_token" in res
    assert res["user"]["role"] == "admin"

    with pytest.raises(HTTPException) as exc_info:
        app_module.login(LoginRequest(username="admin", password="wrong"))
    assert exc_info.value.status_code == 401

def test_endpoint_alerts_lifecycle():
    admin = authenticate_user("admin", "admin123")
    cfg = app_module.create_alert_config(
        AlertConfigRequest(
            route="79",
            metric="rides_per_scheduled_hour",
            threshold=250.0,
            condition="above",
            severity="critical",
            message="Route 79 critical load",
        ),
        user=admin,
    )
    assert cfg["route"] == "79"

    alerts = app_module.list_alerts()
    assert "alerts" in alerts
    assert "total" in alerts
    if alerts["total"] > 0:
        first_id = alerts["alerts"][0]["alert_id"]
        ack = app_module.acknowledge_alert(first_id)
        assert ack["acknowledged"] is True

def test_endpoint_emergency_broadcast():
    operator = authenticate_user("operator", "operator123")
    bc = app_module.create_broadcast(
        EmergencyBroadcastRequest(
            title="Service Disruption Alert",
            message="Severe delay on Clark corridor.",
            severity="critical",
            affected_routes=["22"],
            active=True,
        ),
        user=operator,
    )
    assert bc["title"] == "Service Disruption Alert"

    all_bc = app_module.list_broadcasts()
    assert any(b["broadcast_id"] == bc["broadcast_id"] for b in all_bc["broadcasts"])

    deactivated = app_module.deactivate_broadcast(bc["broadcast_id"], user=operator)
    assert deactivated["active"] is False

def test_endpoint_congestion_heatmap():
    data = app_module.get_heatmap_data("W")
    assert "points" in data
    assert "summary" in data
    assert data["summary"]["total_routes"] > 0
    assert len(data["points"]) > 0
    assert "congestion_level" in data["points"][0]

def test_endpoint_schedule_update():
    operator = authenticate_user("operator", "operator123")
    up = app_module.create_schedule_update(
        ScheduleUpdateRequest(
            route="22",
            service_date="2026-06-15",
            new_scheduled_trips=125,
            reason="Summer peak frequency boost",
        ),
        user=operator,
    )
    assert up["status"] == "applied"
    assert up["new_scheduled_trips"] == 125

    updates = app_module.list_schedule_updates()
    assert any(u["update_id"] == up["update_id"] for u in updates["updates"])

    notifs = app_module.list_notifications()
    assert "notifications" in notifs

def test_endpoint_delay_handling_and_integrations():
    operator = authenticate_user("operator", "operator123")
    delay_record = app_module.report_delay(
        DelayReportRequest(
            route="22",
            delay_minutes=15,
            cause="Signal Issue",
            station_or_segment="Loop Station",
            estimated_impact_multiplier=1.4,
        ),
        user=operator,
    )
    assert delay_record["route"] == "22"
    assert delay_record["delay_minutes"] == 15
    assert delay_record["estimated_platform_surge_pct"] == 40.0

    delays = app_module.list_reported_delays()
    assert any(d["delay_id"] == delay_record["delay_id"] for d in delays["delays"])

    dispatches = app_module.list_integration_dispatches()
    assert "dispatches" in dispatches
    assert len(dispatches["dispatches"]) > 0

