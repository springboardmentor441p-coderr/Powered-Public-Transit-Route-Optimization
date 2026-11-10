"""Dashboard API Router."""

from __future__ import annotations

from app.api.compat import APIRouter
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary() -> DashboardSummaryResponse:
    """Executive overview of network capacity, vehicle-hours, and high-frequency corridors."""
    return DashboardService.get_dashboard_summary()

