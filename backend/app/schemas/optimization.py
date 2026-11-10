"""Pydantic Schemas for Schedule Optimization Endpoints."""

from __future__ import annotations

from typing import Any, List, Optional
from app.schemas.common import BaseModel, Field


class OptimizationSimulateRequest(BaseModel):
    """Scenario simulation input."""
    route_id: str
    scenario_name: str = "Schedule Adjustment Scenario"
    frequency_multiplier: float = Field(default=1.0, ge=0.1, le=5.0)
    frequency_change_pct: Optional[float] = None
    target_headway_min: Optional[float] = Field(default=None, ge=1.0, le=240.0)
    stop_consolidation_pct: float = Field(default=0.0, ge=0.0, le=50.0)
    span_extension_hours: float = Field(default=0.0, ge=0.0, le=8.0)
    layover_ratio: float = Field(default=0.15, ge=0.05, le=0.5)

    def __init__(self, **data: Any) -> None:
        if "frequency_change_pct" in data and data["frequency_change_pct"] is not None:
            pct = float(data["frequency_change_pct"])
            data["frequency_multiplier"] = max(0.1, round(1.0 + pct / 100.0, 2))
        super().__init__(**data)


class OperationalMetricComparisonModel(BaseModel):
    """Comparison entry between baseline and simulated schedule."""
    metric_name: str
    baseline_value: float
    simulated_value: float
    absolute_change: float
    percentage_change: float
    unit: str


class OptimizationSimulateResponse(BaseModel):
    """Simulation results comparing before vs after schedule."""
    route_id: str
    route_short_name: str
    scenario_name: str
    baseline_trips: int
    simulated_trips: int
    baseline_headway_min: float
    simulated_headway_min: float
    baseline_trip_duration_min: float
    simulated_trip_duration_min: float
    baseline_vehicles_required: int
    simulated_vehicles_required: int
    baseline_vehicle_hours: float
    simulated_vehicle_hours: float
    baseline_vehicle_km: float
    simulated_vehicle_km: float
    baseline_speed_kmh: float
    simulated_speed_kmh: float
    comparisons: List[OperationalMetricComparisonModel] = []
    schedule_derived_notes: List[str] = []

    # Frontend compatibility fields
    route_name: str = ""
    current_trips: int = 0
    proposed_trips: int = 0
    current_avg_headway: Optional[float] = None
    proposed_avg_headway: Optional[float] = None
    trip_change_pct: float = 0.0
    headway_change_pct: Optional[float] = None
    is_hypothetical: bool = True
    notes: str = ""

    def __init__(self, **data: Any) -> None:
        if "route_short_name" in data and "route_name" not in data:
            data["route_name"] = str(data["route_short_name"])
        if "baseline_trips" in data and "current_trips" not in data:
            data["current_trips"] = int(data["baseline_trips"])
        if "simulated_trips" in data and "proposed_trips" not in data:
            data["proposed_trips"] = int(data["simulated_trips"])
        if "baseline_headway_min" in data and "current_avg_headway" not in data:
            data["current_avg_headway"] = float(data["baseline_headway_min"])
        if "simulated_headway_min" in data and "proposed_avg_headway" not in data:
            data["proposed_avg_headway"] = float(data["simulated_headway_min"])
        if "current_trips" in data and "proposed_trips" in data and "trip_change_pct" not in data:
            c = data["current_trips"]
            p = data["proposed_trips"]
            data["trip_change_pct"] = round(((p - c) / max(1, c)) * 100.0, 1)
        if "current_avg_headway" in data and "proposed_avg_headway" in data and "headway_change_pct" not in data:
            c = data.get("current_avg_headway")
            p = data.get("proposed_avg_headway")
            if c and p:
                data["headway_change_pct"] = round(((p - c) / max(0.1, c)) * 100.0, 1)
        if "schedule_derived_notes" in data and "notes" not in data:
            data["notes"] = " ".join(data.get("schedule_derived_notes", []))
        super().__init__(**data)
