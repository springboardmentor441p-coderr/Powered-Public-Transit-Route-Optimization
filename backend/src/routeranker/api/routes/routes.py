"""Route catalog, feature, cluster, filter, and comparison endpoints."""

from fastapi import APIRouter, Depends, Query

from ..schemas import CompareResponse, Page, RouteCluster, RouteFeature, RouteItem
from ..services import RouteRankerService
from .dependencies import get_service

router = APIRouter(prefix="/routes", tags=["routes"])


@router.get("", response_model=Page[RouteItem], summary="List and filter routes")
def list_routes(
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=100), min_trips: int | None = Query(None, ge=0),
    max_trips: int | None = Query(None, ge=0), min_stops: int | None = Query(None, ge=0),
    min_headway_seconds: float | None = Query(None, ge=0), max_headway_seconds: float | None = Query(None, ge=0),
    algorithm: str | None = Query(None, pattern="^(kmeans|dbscan)$"), cluster_id: int | None = None,
    service: RouteRankerService = Depends(get_service),
):
    return service.list_routes(limit, offset, q, min_trips, max_trips, min_stops,
                               max_headway_seconds, min_headway_seconds, algorithm, cluster_id)


@router.get("/compare", response_model=CompareResponse, summary="Compare two or more routes")
def compare_routes(
    route_ids: list[str] = Query(..., min_length=2, max_length=20),
    service: RouteRankerService = Depends(get_service),
):
    return {"routes": service.compare_routes(route_ids), "compared_route_ids": route_ids}


@router.get("/{route_id}/features", response_model=RouteFeature, summary="Get raw analytical features for a route")
def route_features(route_id: str, service: RouteRankerService = Depends(get_service)):
    return service.route_features(route_id)


@router.get("/{route_id}/clusters", response_model=RouteCluster, summary="Get saved cluster assignments")
def route_clusters(route_id: str, service: RouteRankerService = Depends(get_service)):
    return service.route_cluster(route_id)


@router.get("/{route_id}", response_model=RouteItem, summary="Get route details")
def route_detail(route_id: str, service: RouteRankerService = Depends(get_service)):
    return service.route(route_id)
