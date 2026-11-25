"""API v1 router for canonical CTA route directory and feature profiles."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import get_route_service
from app.core.config import settings
from app.schemas.route import RouteDetailResponse, RouteListResponse
from app.services.route_service import RouteService

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.get(
    "",
    response_model=RouteListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Canonical Transit Routes",
    description="Retrieve a paginated, filterable, deterministically sorted directory of canonical CTA routes.",
)
async def list_routes(
    mode: Optional[str] = Query(None, description="Filter by transit mode ('bus' or 'rail')"),
    cluster: Optional[str] = Query(None, description="Filter by operational cluster label"),
    partition: Optional[str] = Query(None, description="Filter by regional partition"),
    search: Optional[str] = Query(None, max_length=64, description="Search by route ID or name"),
    sort_by: str = Query("route_id", description="Field to sort by"),
    order: str = Query("asc", description="Sort order ('asc' or 'desc')"),
    limit: int = Query(
        settings.DEFAULT_PAGE_LIMIT,
        ge=1,
        le=settings.MAX_PAGE_LIMIT,
        description="Maximum records per page (1-150)",
    ),
    offset: int = Query(0, ge=0, description="Zero-based pagination offset"),
    service: RouteService = Depends(get_route_service),
) -> RouteListResponse:
    """List canonical CTA routes with filtering, search, and pagination."""
    return service.list_routes(
        mode=mode,
        cluster=cluster,
        partition=partition,
        search=search,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{route_id}",
    response_model=RouteDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Route Feature Details",
    description="Retrieve verified operational, demand, hub, and corridor features for a single CTA route.",
)
async def get_route_detail(
    route_id: str,
    service: RouteService = Depends(get_route_service),
) -> RouteDetailResponse:
    """Get detailed feature profile for a single route by ID."""
    return service.get_route_detail(route_id=route_id)
