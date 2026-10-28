"""
tests/test_scenario_and_metrics.py
Unit tests for operational scenario simulation calculations and regression metrics.
"""

import pytest
import numpy as np
from pathlib import Path
from src.optimization.scenario_engine import simulate_frequency_adjustment
from analytics import train_evaluate_models
calculate_metrics = train_evaluate_models.calculate_metrics

def test_scenario_positive_expansion():
    res = simulate_frequency_adjustment(
        route_id="8",
        base_weekday_rides=15000.0,
        base_scheduled_trips=400,
        percent_trip_change=20.0,
        elasticity=0.42,
        cost_per_trip=85.0
    )
    assert res["simulated_scheduled_trips"] == 480
    assert res["delta_trips"] == 80
    assert res["simulated_weekday_rides"] > 15000.0
    assert res["daily_operating_cost_delta_usd"] == 80 * 85.0
    assert "Added capacity" in res["recommendation"] or "Highly viable" in res["recommendation"]

def test_scenario_negative_reduction():
    res = simulate_frequency_adjustment(
        route_id="120",
        base_weekday_rides=2000.0,
        base_scheduled_trips=100,
        percent_trip_change=-20.0,
        elasticity=0.42,
        cost_per_trip=85.0
    )
    assert res["simulated_scheduled_trips"] == 80
    assert res["delta_trips"] == -20
    assert res["simulated_weekday_rides"] < 2000.0
    assert res["daily_operating_cost_delta_usd"] == -20 * 85.0
    assert "Cost reduction" in res["recommendation"]

def test_metrics_calculation_accuracy():
    y_true = np.array([1000.0, 2000.0, 3000.0])
    y_pred = np.array([1100.0, 1900.0, 3000.0])

    # Absolute errors: 100, 100, 0 -> MAE = 200 / 3 = 66.67
    # Squared errors: 10000, 10000, 0 -> MSE = 20000 / 3 = 6666.67 -> RMSE = 81.65
    # WAPE = 200 / 6000 * 100 = 3.33%
    m = calculate_metrics(y_true, y_pred)
    assert m["MAE"] == 66.67
    assert m["RMSE"] == 81.65
    assert m["WAPE_pct"] == 3.33
