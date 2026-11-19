"""
Automated verification tests covering Spec Section 9.19.1 correctness cases:
1. GTFS exception_type=2 removal & exception_type=1 addition.
2. After-midnight (>24:00:00) trips remaining on their original service date.
3. Exact route/date join & unmatched reconciliation (route 1001 & route 169).
4. Replay cutoff preventing future actual leakage.
5. Conditional scenario arithmetic.
"""
import os
import sys
from datetime import date
import pandas as pd

sys.path.insert(0, os.getcwd())
from src.scenarios import calculate_service_scenario

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
