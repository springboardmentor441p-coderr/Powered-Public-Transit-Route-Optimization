"""Optimization Simulator API Router."""

from __future__ import annotations

from app.api.compat import APIRouter, HTTPException, status
from app.schemas.optimization import (
    OptimizationSimulateRequest,
    OptimizationSimulateResponse,
)
from app.services.optimization_service import OptimizationService

router = APIRouter(prefix="/optimization", tags=["Optimization"])


@router.post("/simulate", response_model=OptimizationSimulateResponse)
def simulate_schedule_scenario(req: OptimizationSimulateRequest) -> OptimizationSimulateResponse:
    """Simulate frequency retiming, stop consolidation, and vehicle requirement impacts."""
    try:
        return OptimizationService.simulate(req)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

