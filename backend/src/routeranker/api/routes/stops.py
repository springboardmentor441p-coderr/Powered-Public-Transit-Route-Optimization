"""Stop catalog and stop-to-route relationships."""

from fastapi import APIRouter, Depends, Query

from ..schemas import Page, StopItem, StopRoute, StopRouteCount
from ..services import RouteRankerService
from .dependencies import get_service

router = APIRouter(prefix="/stops", tags=["stops"])


@router.get("", response_model=Page[StopItem], summary="List stops")
def list_stops(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
               q: str | None = Query(None, max_length=100), min_routes: int | None = Query(None, ge=0),
               service: RouteRankerService = Depends(get_service)):
    return service.list_stops(limit, offset, q, min_routes)


@router.get("/route-counts", response_model=Page[StopRouteCount], summary="Get route counts for each stop")
def stop_route_counts(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                      service: RouteRankerService = Depends(get_service)):
    return service.stop_route_counts(limit, offset)


@router.get("/{stop_id}/routes", response_model=list[StopRoute], summary="Find routes serving a stop")
def routes_at_stop(stop_id: str, service: RouteRankerService = Depends(get_service)):
    return service.routes_at_stop(stop_id)


@router.get("/{stop_id}", response_model=StopItem, summary="Get stop details")
def stop_detail(stop_id: str, service: RouteRankerService = Depends(get_service)):
    return service.stop(stop_id)
