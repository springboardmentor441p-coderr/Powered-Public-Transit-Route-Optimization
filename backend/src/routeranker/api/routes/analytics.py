"""Read-only descriptive analytics endpoints."""

from fastapi import APIRouter, Depends, Query

from ..schemas import (ClusterSummary, DatasetStatistics, HeadwaySummary, RouteStatistics,
                       ScheduledHour, SimilarityItem, StopStatistics)
from ..services import RouteRankerService
from .dependencies import get_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/statistics", response_model=DatasetStatistics, summary="Overall dataset statistics")
def dataset_statistics(service: RouteRankerService = Depends(get_service)):
    return service.dataset_statistics()


@router.get("/routes/statistics", response_model=RouteStatistics, summary="Route statistics")
def route_statistics(service: RouteRankerService = Depends(get_service)):
    return service.route_statistics()


@router.get("/stops/statistics", response_model=StopStatistics, summary="Stop statistics")
def stop_statistics(service: RouteRankerService = Depends(get_service)):
    return service.stop_statistics()


@router.get("/scheduled-trips/by-hour", response_model=list[ScheduledHour], summary="Scheduled trip records by service hour")
def scheduled_by_hour(service: RouteRankerService = Depends(get_service)):
    return service.scheduled_by_hour()


@router.get("/headways", response_model=HeadwaySummary, summary="Estimated scheduled headway summary")
def headway_summary(route_id: str | None = Query(None), service: RouteRankerService = Depends(get_service)):
    return service.headway_summary(route_id)


@router.get("/route-similarity", response_model=list[SimilarityItem], summary="Route pair shared-stop similarity")
def route_similarity(route_id: str | None = Query(None), limit: int = Query(100, ge=1, le=500),
                     service: RouteRankerService = Depends(get_service)):
    return service.similarities(route_id, limit)


@router.get("/clusters", response_model=list[ClusterSummary], summary="Cluster distributions and raw-feature profiles")
def cluster_summaries(service: RouteRankerService = Depends(get_service)):
    return service.cluster_summaries()
