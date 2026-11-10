"""Schedule Scenario Simulator and Optimization Module for RouteRanker.

Simulates transit schedule adjustments, headway retiming, stop consolidation,
and fleet/vehicle requirement impacts purely using operational schedule formulas.
Never fabricates ridership, ticket revenue, or passenger demand data.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Standard transit scheduling constants
DEFAULT_LAYOVER_RATIO = 0.15  # 15% recovery/layover at terminals
DEFAULT_STOP_DWELL_SECONDS = 45.0  # seconds saved per consolidated stop (dwell + accel/decel)


@dataclass
class SimulationScenarioRequest:
    """User input for schedule scenario simulation."""
    route_id: str
    scenario_name: str = "Schedule Adjustment"
    frequency_multiplier: float = 1.0  # e.g. 1.25 for +25% more trips
    target_headway_min: Optional[float] = None  # Explicit target headway in minutes
    stop_consolidation_pct: float = 0.0  # e.g. 15.0 for 15% fewer stops
    span_extension_hours: float = 0.0  # additional operating span in hours
    layover_ratio: float = DEFAULT_LAYOVER_RATIO


@dataclass
class OperationalMetricComparison:
    """Comparison between baseline schedule and simulated scenario."""
    metric_name: str
    baseline_value: float
    simulated_value: float
    absolute_change: float
    percentage_change: float
    unit: str


@dataclass
class SimulationScenarioResponse:
    """Detailed output comparing baseline vs simulated schedule."""
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
    comparisons: List[OperationalMetricComparison] = field(default_factory=list)
    schedule_derived_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["comparisons"] = [asdict(c) for c in self.comparisons]
        return res


class ScheduleSimulator:
    """Simulates schedule scenarios using deterministic operational transit modeling."""

    def __init__(self, route_features_df: pd.DataFrame) -> None:
        self.features_df = route_features_df.set_index("route_id")

    def simulate(self, req: SimulationScenarioRequest) -> SimulationScenarioResponse:
        """Simulate the operational impacts of schedule adjustments."""
        if req.route_id not in self.features_df.index:
            raise ValueError(f"Route ID '{req.route_id}' not found in route features.")

        row = self.features_df.loc[req.route_id]
        short_name = str(row.get("route_short_name", req.route_id))

        # Baseline metrics
        base_trips = int(row.get("total_trips", 10))
        base_headway = float(row.get("avg_headway_min", 30.0))
        base_duration = float(row.get("avg_trip_duration_min", 45.0))
        base_distance = float(row.get("estimated_distance_km", 15.0))
        base_span = float(row.get("service_span_hours", 14.0))
        base_stops = int(row.get("stop_count", 30))

        # 1. Stop consolidation effect
        # Each consolidated stop reduces round-trip runtime by dwell + accel/decel
        dwell_reduction_pct = max(0.0, min(50.0, req.stop_consolidation_pct))
        stops_removed = int(round(base_stops * (dwell_reduction_pct / 100.0)))
        time_saved_min = round((stops_removed * DEFAULT_STOP_DWELL_SECONDS) / 60.0, 1)

        sim_duration = max(10.0, base_duration - time_saved_min)

        # 2. Operating speed
        sim_speed = round(base_distance / (sim_duration / 60.0), 1)
        base_speed = round(base_distance / (max(10.0, base_duration) / 60.0), 1)

        # 3. Headway and trips
        sim_span = base_span + max(0.0, req.span_extension_hours)

        if req.target_headway_min is not None and req.target_headway_min > 0:
            sim_headway = float(req.target_headway_min)
            # Active hours converted to trips
            sim_trips = int(round((sim_span * 60.0) / sim_headway))
        else:
            mult = max(0.2, min(5.0, req.frequency_multiplier))
            sim_trips = int(round(base_trips * mult))
            # New headway = span / trips
            sim_headway = round((sim_span * 60.0) / max(1, sim_trips), 1)

        # 4. Cycle time & Fleet requirement (Vehicles needed)
        # Cycle time = (2 * one-way duration) * (1 + layover_ratio)
        base_cycle_time = (base_duration * 2.0) * (1.0 + req.layover_ratio)
        sim_cycle_time = (sim_duration * 2.0) * (1.0 + req.layover_ratio)

        # Standard transit formula: N_buses = ceil(cycle_time / headway)
        base_vehicles = max(1, math.ceil(base_cycle_time / max(1.0, base_headway)))
        sim_vehicles = max(1, math.ceil(sim_cycle_time / max(1.0, sim_headway)))

        # 5. Vehicle-Hours & Vehicle-Kilometers
        base_veh_hours = round(base_trips * (base_duration / 60.0), 1)
        sim_veh_hours = round(sim_trips * (sim_duration / 60.0), 1)

        base_veh_km = round(base_trips * base_distance, 1)
        sim_veh_km = round(sim_trips * base_distance, 1)

        # Metrics comparison builder
        def make_comp(name: str, b_val: float, s_val: float, unit: str) -> OperationalMetricComparison:
            diff = round(s_val - b_val, 2)
            pct = round((diff / max(0.001, abs(b_val))) * 100.0, 1) if b_val != 0 else 0.0
            return OperationalMetricComparison(
                metric_name=name,
                baseline_value=round(b_val, 2),
                simulated_value=round(s_val, 2),
                absolute_change=diff,
                percentage_change=pct,
                unit=unit,
            )

        comparisons = [
            make_comp("Scheduled Trips", base_trips, sim_trips, "trips/day"),
            make_comp("Average Headway", base_headway, sim_headway, "minutes"),
            make_comp("One-Way Trip Duration", base_duration, sim_duration, "minutes"),
            make_comp("Estimated Fleet Requirement", base_vehicles, sim_vehicles, "buses"),
            make_comp("Scheduled Vehicle-Hours", base_veh_hours, sim_veh_hours, "veh-hours/day"),
            make_comp("Scheduled Vehicle-Kilometers", base_veh_km, sim_veh_km, "veh-km/day"),
            make_comp("Estimated Commercial Speed", base_speed, sim_speed, "km/h"),
        ]

        notes = [
            "All calculations are derived deterministically from GTFS timetables and transit scheduling equations.",
            f"Fleet requirement is calculated as ceil(cycle_time / headway) with a {int(req.layover_ratio*100)}% recovery layover factor.",
            f"Stop consolidation simulated {stops_removed} consolidated stops at {int(DEFAULT_STOP_DWELL_SECONDS)}s estimated dwell/decel per stop.",
            "Never fabricates passenger counts, revenue, or congestion. Values represent scheduled service capacity.",
        ]

        return SimulationScenarioResponse(
            route_id=req.route_id,
            route_short_name=short_name,
            scenario_name=req.scenario_name,
            baseline_trips=base_trips,
            simulated_trips=sim_trips,
            baseline_headway_min=base_headway,
            simulated_headway_min=sim_headway,
            baseline_trip_duration_min=base_duration,
            simulated_trip_duration_min=sim_duration,
            baseline_vehicles_required=base_vehicles,
            simulated_vehicles_required=sim_vehicles,
            baseline_vehicle_hours=base_veh_hours,
            simulated_vehicle_hours=sim_veh_hours,
            baseline_vehicle_km=base_veh_km,
            simulated_vehicle_km=sim_veh_km,
            baseline_speed_kmh=base_speed,
            simulated_speed_kmh=sim_speed,
            comparisons=comparisons,
            schedule_derived_notes=notes,
        )

