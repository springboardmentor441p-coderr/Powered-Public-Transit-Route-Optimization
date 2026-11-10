"""Insights and Strategic Findings API Router."""

from __future__ import annotations

from app.api.compat import APIRouter
from app.schemas.insights import InsightItem
from app.services.insights_service import InsightsService

router = APIRouter(prefix="", tags=["Insights"])


@router.get("/insights", response_model=list[InsightItem])
def get_insights() -> InsightsResponse:
    """Algorithmic strategic findings on corridor redundancy, headway bunching, and coverage gaps."""
    return InsightsService.generate_insights()

