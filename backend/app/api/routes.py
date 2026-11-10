"""Routes API Router."""

from __future__ import annotations

from typing import Optional
from app.api.compat import APIRouter, HTTPException, Path, Query, status
from app.schemas.common import PaginatedResponse
from app.schemas.routes import (
    RouteDetailResponse,
    RouteItem,
    RouteScheduleResponse,
    RouteStopItem,
    RouteStopsResponse,
    RouteTripItem,
    RouteTripsResponse,
    ScheduleEntry,
)
from app.services.route_service import RouteService

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.get("", response_model=PaginatedResponse[RouteItem])
def list_routes(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=50, ge=1, le=500, description="Items per page"),
    search: Optional[str] = None,
    min_trips: Optional[int] = None,
    sort_by: str = Query(default="total_trips", description="Sort field (total_trips, avg_headway_min, etc.)"),
    sort_order: str = Query(default="desc", regex="^(asc|desc)$", description="Sort order asc or desc"),
) -> PaginatedResponse[RouteItem]:
    """Fetch paginated transit routes with searching, filtering, and sorting."""
    return RouteService.get_routes(
        page=page,
        page_size=page_size,
        search=search,
        min_trips=min_trips,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{route_id}", response_model=RouteDetailResponse)
def get_route(
    route_id: str = Path(..., description="Unique GTFS route_id"),
) -> RouteDetailResponse:
    """Fetch comprehensive operational statistics for a specific route."""
    res = RouteService.get_route_by_id(route_id)
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '{route_id}' not found.",
        )
    return res


@router.get("/{route_id}/stops", response_model=list[RouteStopItem])
def get_route_stops(
    route_id: str = Path(..., description="Unique GTFS route_id"),
) -> RouteStopsResponse:
    """Fetch the ordered sequence of scheduled stops for a route."""
    res = RouteService.get_route_stops(route_id)
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '{route_id}' stops not found.",
        )
    return res


@router.get("/{route_id}/trips", response_model=list[RouteTripItem])
def get_route_trips(
    route_id: str = Path(..., description="Unique GTFS route_id"),
    limit: int = Query(default=100, ge=1, le=500, description="Max trips to return"),
) -> RouteTripsResponse:
    """Fetch scheduled trips for a route."""
    res = RouteService.get_route_trips(route_id, limit=limit)
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trips for route '{route_id}' not found.",
        )
    return res


@router.get("/{route_id}/schedule", response_model=list[ScheduleEntry])
def get_route_schedule(
    route_id: str = Path(..., description="Unique GTFS route_id"),
) -> RouteScheduleResponse:
    """Fetch hourly timetable departure distribution for a route."""
    res = RouteService.get_route_schedule(route_id)
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule for route '{route_id}' not found.",
        )
    return res

