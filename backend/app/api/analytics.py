"""Transit Analytics API Router."""

from __future__ import annotations

from app.api.compat import APIRouter, Query
from app.schemas.analytics import FrequencyItem, ServiceStats
from app.schemas.common import PaginatedResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/frequency", response_model=PaginatedResponse[FrequencyItem])
def get_frequency_analytics(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=500, description="Items per page"),
    high_frequency_only: bool = Query(default=False, description="Filter only high-frequency routes"),
) -> PaginatedResponse[FrequencyItem]:
    """Fetch paginated frequency, headway consistency, and peak vs off-peak departure breakdowns."""
    return AnalyticsService.get_frequency_analytics(
        page=page,
        page_size=page_size,
        high_frequency_only=high_frequency_only,
    )


@router.get("/service", response_model=list[ServiceStats])
def get_service_analytics() -> ServiceSpanAnalyticsResponse:
    """Network-wide service span distribution and hourly departure volumes."""
    return AnalyticsService.get_service_span_analytics()

