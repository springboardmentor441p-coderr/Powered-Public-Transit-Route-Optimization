"""Route Overlap API Router."""

from __future__ import annotations

from typing import List
from app.api.compat import APIRouter, HTTPException, Path, Query, status
from app.schemas.overlap import OverlapPairItem, RouteOverlapDetailResponse
from app.services.overlap_service import OverlapService

router = APIRouter(prefix="/overlap", tags=["Overlap"])


@router.get("", response_model=List[OverlapPairItem])
def get_top_overlaps(
    limit: int = Query(default=50, ge=1, le=500, description="Max pairs to return"),
    min_overlap_pct: float = 20.0,
) -> List[OverlapPairItem]:
    """Fetch highest overlapping route pairs in the network."""
    if not 0.0 <= min_overlap_pct <= 100.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="min_overlap_pct must be between 0 and 100.",
        )
    return OverlapService.get_top_overlaps(limit=limit, min_overlap_pct=min_overlap_pct)


@router.get("/{route_id}", response_model=RouteOverlapDetailResponse)
def get_route_overlap(
    route_id: str = Path(..., description="Unique GTFS route_id"),
) -> RouteOverlapDetailResponse:
    """Fetch all routes that overlap with a specific route."""
    res = OverlapService.get_route_overlap(route_id)
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '{route_id}' overlap details not found.",
        )
    return res

