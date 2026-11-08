"""Scheduling Optimization & Frequency Adjustment Module for MetroFlow.
Provides algorithmic train headway optimization, peak-hour frequency adjustments,
and schedule scenario simulation.
"""

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from ..db import get_db
from ..models import Route, Trip, ScheduleScenario, User
from .auth import get_current_user

router = APIRouter()

class FrequencyOptimizationResponse(BaseModel):
    route_id: str
    route_name: str
    current_avg_headway_minutes: int
    peak_hours: str
    recommended_peak_headway_minutes: int
    recommended_offpeak_headway_minutes: int
    additional_trains_needed: int
    projected_overcrowding_reduction_percent: float
    optimization_summary: str

class ScenarioCreateRequest(BaseModel):
    scenario_name: str
    route_id: str
    target_headway_minutes: int
    peak_start_time: Optional[str] = "08:00:00"
    peak_end_time: Optional[str] = "10:00:00"

class ScenarioResponse(BaseModel):
    id: int
    scenario_name: str
    route_id: str
    target_headway_minutes: int
    peak_start_time: str
    peak_end_time: str
    additional_trains_recommended: int
    status: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)

@router.get("/frequency/recommendations", response_model=List[FrequencyOptimizationResponse])
def get_frequency_recommendations(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate intelligent train frequency and headway adjustment recommendations per route."""
    routes = db.query(Route).limit(limit).all()
    recommendations = []

    for route in routes:
        trip_count = db.query(Trip).filter(Trip.route_id == route.route_id).count()
        # Estimate headway from trip count across service hours (~16h daily)
        current_headway = max(5, int(round((16 * 60) / max(1, trip_count)))) if trip_count > 0 else 12
        
        # Optimization logic:
        # Peak target: 3-5 mins, Off-peak: 8-12 mins
        recommended_peak = min(4, max(3, int(current_headway * 0.4)))
        recommended_offpeak = min(10, max(6, int(current_headway * 0.8)))
        
        # Calculate extra train sets needed to achieve peak headway
        extra_trains = max(1, int(round((current_headway - recommended_peak) / 3.0)))
        projected_reduction = round(min(45.0, 18.0 + extra_trains * 8.5), 1)

        summary = (
            f"Increase train dispatch frequency on Route {route.route_id} during 07:30-09:30 & 17:30-19:30. "
            f"Reducing headway from {current_headway}m to {recommended_peak}m requires {extra_trains} supplemental train set(s) "
            f"and is projected to relieve platform congestion by {projected_reduction}%."
        )

        recommendations.append(FrequencyOptimizationResponse(
            route_id=route.route_id,
            route_name=route.route_long_name or route.route_short_name or f"Route {route.route_id}",
            current_avg_headway_minutes=current_headway,
            peak_hours="07:30 - 09:30 & 17:30 - 19:30",
            recommended_peak_headway_minutes=recommended_peak,
            recommended_offpeak_headway_minutes=recommended_offpeak,
            additional_trains_needed=extra_trains,
            projected_overcrowding_reduction_percent=projected_reduction,
            optimization_summary=summary
        ))

    return recommendations

@router.post("/scenarios", response_model=ScenarioResponse)
def create_schedule_scenario(
    request: ScenarioCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new frequency adjustment scenario to simulate schedule optimization."""
    route = db.query(Route).filter(Route.route_id == request.route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail=f"Route '{request.route_id}' not found")

    # Calculate additional trains for target headway
    additional_trains = max(1, int(round(12 / max(1, request.target_headway_minutes))))

    now_iso = datetime.now(timezone.utc).isoformat()
    scenario = ScheduleScenario(
        scenario_name=request.scenario_name,
        route_id=request.route_id,
        target_headway_minutes=request.target_headway_minutes,
        peak_start_time=request.peak_start_time or "08:00:00",
        peak_end_time=request.peak_end_time or "10:00:00",
        additional_trains_recommended=additional_trains,
        status="PROPOSED",
        created_at=now_iso
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario

@router.get("/scenarios", response_model=List[ScenarioResponse])
def list_schedule_scenarios(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all proposed and active schedule adjustment scenarios."""
    return db.query(ScheduleScenario).order_by(ScheduleScenario.id.desc()).all()

