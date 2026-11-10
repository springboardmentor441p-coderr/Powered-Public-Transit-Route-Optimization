"""Network Coverage API Router."""

from __future__ import annotations

from typing import Optional
from app.api.compat import APIRouter, Query
from app.schemas.common import PaginatedResponse
from app.schemas.coverage import CoverageSummaryResponse
from app.schemas.stops import StopItem
from app.services.coverage_service import CoverageService

router = APIRouter(prefix="/coverage", tags=["Coverage"])


@router.get("/summary", response_model=CoverageSummaryResponse)
def get_coverage_summary() -> CoverageSummaryResponse:
    """Network-wide stop coverage, transfer hub distribution, and spatial bounds."""
    return CoverageService.get_coverage_summary()


@router.get("/stops", response_model=PaginatedResponse[StopItem])
def list_coverage_stops(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=50, ge=1, le=500, description="Items per page"),
    is_hub_only: bool = Query(default=False, description="Filter only transfer hubs (5+ routes)"),
    search: Optional[str] = None,
) -> PaginatedResponse[StopItem]:
    """Fetch paginated stops with route count and transfer hub indicators."""
    return CoverageService.get_coverage_stops(
        page=page,
        page_size=page_size,
        is_hub_only=is_hub_only,
        search=search,
    )

