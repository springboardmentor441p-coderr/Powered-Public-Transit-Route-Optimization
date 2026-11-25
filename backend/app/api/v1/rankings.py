"""API v1 router for canonical multi-criteria route rankings, explanations, and sensitivity."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import get_ranking_service
from app.core.config import settings
from app.schemas.ranking import (
    RankingListResponse,
    RouteExplanationResponse,
    SensitivityListResponse,
)
from app.services.ranking_service import RankingService

router = APIRouter(prefix="/rankings", tags=["Rankings"])


@router.get(
    "/bus",
    response_model=RankingListResponse,
    status_code=status.HTTP_200_OK,
    summary="Bus Network Priority Rankings (Track 1)",
    description="Retrieve canonical multi-criteria rankings for the 125 CTA bus routes under Profile A.",
)
async def get_bus_rankings(
    partition: Optional[str] = Query(None, description="Filter by regional partition"),
    min_rank: Optional[int] = Query(None, ge=1, description="Minimum rank filter (inclusive)"),
    max_rank: Optional[int] = Query(None, ge=1, description="Maximum rank filter (inclusive)"),
    sort_by: str = Query("rank", description="Field to sort by"),
    order: str = Query("asc", description="Sort order ('asc' or 'desc')"),
    limit: int = Query(
        settings.DEFAULT_PAGE_LIMIT,
        ge=1,
        le=settings.MAX_PAGE_LIMIT,
        description="Maximum records per page (1-150)",
    ),
    offset: int = Query(0, ge=0, description="Zero-based pagination offset"),
    service: RankingService = Depends(get_ranking_service),
) -> RankingListResponse:
    """Serve Track 1: Bus Network Priority rankings."""
    return service.get_bus_rankings(
        partition=partition,
        min_rank=min_rank,
        max_rank=max_rank,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/rail",
    response_model=RankingListResponse,
    status_code=status.HTTP_200_OK,
    summary="Heavy Rail Operational Priority Rankings (Track 2)",
    description="Retrieve canonical operational priority rankings for all 8 CTA heavy rail lines.",
)
async def get_rail_rankings(
    sort_by: str = Query("rank", description="Field to sort by"),
    order: str = Query("asc", description="Sort order ('asc' or 'desc')"),
    service: RankingService = Depends(get_ranking_service),
) -> RankingListResponse:
    """Serve Track 2: Heavy Rail Operational Priority rankings."""
    return service.get_rail_rankings(sort_by=sort_by, order=order)


@router.get(
    "/unified",
    response_model=RankingListResponse,
    status_code=status.HTTP_200_OK,
    summary="Unified Network Operational Supply Rankings (Track 3)",
    description="Retrieve mode-agnostic operational supply rankings across all 133 CTA transit routes.",
)
async def get_unified_rankings(
    mode: Optional[str] = Query(None, description="Filter by transit mode ('bus' or 'rail')"),
    min_rank: Optional[int] = Query(None, ge=1, description="Minimum rank filter (inclusive)"),
    max_rank: Optional[int] = Query(None, ge=1, description="Maximum rank filter (inclusive)"),
    sort_by: str = Query("rank", description="Field to sort by"),
    order: str = Query("asc", description="Sort order ('asc' or 'desc')"),
    limit: int = Query(
        settings.DEFAULT_PAGE_LIMIT,
        ge=1,
        le=settings.MAX_PAGE_LIMIT,
        description="Maximum records per page (1-150)",
    ),
    offset: int = Query(0, ge=0, description="Zero-based pagination offset"),
    service: RankingService = Depends(get_ranking_service),
) -> RankingListResponse:
    """Serve Track 3: Unified Operational Supply rankings."""
    return service.get_unified_rankings(
        mode=mode,
        min_rank=min_rank,
        max_rank=max_rank,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/routes/{route_id}/explanation",
    response_model=RouteExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Route Ranking Explanation",
    description="Retrieve precomputed natural-language explanation, driver contributions, and effective weights.",
)
async def get_route_explanation(
    route_id: str,
    track: Optional[str] = Query(
        None,
        description="Ranking track ('BUS_PRIORITY', 'RAIL_PRIORITY', or 'UNIFIED_SUPPLY')",
    ),
    service: RankingService = Depends(get_ranking_service),
) -> RouteExplanationResponse:
    """Serve route-level ranking explanation and weight breakdown."""
    return service.get_route_explanation(route_id=route_id, track=track)


@router.get(
    "/sensitivity",
    response_model=SensitivityListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Ranking Sensitivity Analysis",
    description="Retrieve OAT weight perturbation sensitivity scenarios and rank stability metrics.",
)
async def get_sensitivity(
    track: Optional[str] = Query(
        None,
        description="Filter by track ('BUS_PRIORITY', 'RAIL_PRIORITY', or 'UNIFIED_SUPPLY')",
    ),
    target_criterion: Optional[str] = Query(None, max_length=64, description="Filter by target criterion"),
    service: RankingService = Depends(get_ranking_service),
) -> SensitivityListResponse:
    """Serve Phase 7 sensitivity analysis scenarios."""
    return service.get_sensitivity(track=track, target_criterion=target_criterion)
