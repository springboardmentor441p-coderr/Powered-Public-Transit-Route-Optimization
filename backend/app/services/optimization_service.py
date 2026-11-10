"""Schedule Optimization Service for RouteRanker."""

from __future__ import annotations

import logging
from typing import Optional

from app.core.database import db
from app.schemas.optimization import (
    OperationalMetricComparisonModel,
    OptimizationSimulateRequest,
    OptimizationSimulateResponse,
)
from ml.optimization import ScheduleSimulator, SimulationScenarioRequest

logger = logging.getLogger(__name__)


class OptimizationService:
    """Simulates schedule scenarios, frequency changes, and vehicle requirements."""

    @staticmethod
    def simulate(req: OptimizationSimulateRequest) -> OptimizationSimulateResponse:
        """Run scenario simulation for the specified route."""
        df = db.get_table("route_features")
        simulator = ScheduleSimulator(df)

        domain_req = SimulationScenarioRequest(
            route_id=req.route_id,
            scenario_name=req.scenario_name,
            frequency_multiplier=req.frequency_multiplier,
            target_headway_min=req.target_headway_min,
            stop_consolidation_pct=req.stop_consolidation_pct,
            span_extension_hours=req.span_extension_hours,
            layover_ratio=req.layover_ratio,
        )

        res = simulator.simulate(domain_req)

        comparisons = [
            OperationalMetricComparisonModel(
                metric_name=c.metric_name,
                baseline_value=c.baseline_value,
                simulated_value=c.simulated_value,
                absolute_change=c.absolute_change,
                percentage_change=c.percentage_change,
                unit=c.unit,
            )
            for c in res.comparisons
        ]

        return OptimizationSimulateResponse(
            route_id=res.route_id,
            route_short_name=res.route_short_name,
            scenario_name=res.scenario_name,
            baseline_trips=res.baseline_trips,
            simulated_trips=res.simulated_trips,
            baseline_headway_min=res.baseline_headway_min,
            simulated_headway_min=res.simulated_headway_min,
            baseline_trip_duration_min=res.baseline_trip_duration_min,
            simulated_trip_duration_min=res.simulated_trip_duration_min,
            baseline_vehicles_required=res.baseline_vehicles_required,
            simulated_vehicles_required=res.simulated_vehicles_required,
            baseline_vehicle_hours=res.baseline_vehicle_hours,
            simulated_vehicle_hours=res.simulated_vehicle_hours,
            baseline_vehicle_km=res.baseline_vehicle_km,
            simulated_vehicle_km=res.simulated_vehicle_km,
            baseline_speed_kmh=res.baseline_speed_kmh,
            simulated_speed_kmh=res.simulated_speed_kmh,
            comparisons=comparisons,
            schedule_derived_notes=res.schedule_derived_notes,
        )

