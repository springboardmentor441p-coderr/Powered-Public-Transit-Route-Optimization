"""Saved machine-learning assignments and fit diagnostics."""

from fastapi import APIRouter, Depends

from ..schemas import ClusterSummary, ModelMetadata, ModelMetric, RouteCluster
from ..services import RouteRankerService
from .dependencies import get_service

router = APIRouter(prefix="/ml", tags=["machine learning"])


@router.get("/models", response_model=list[ModelMetadata], summary="Saved model settings and supported behavior")
def model_metadata(service: RouteRankerService = Depends(get_service)):
    return service.model_metadata()


@router.get("/assignments/{route_id}", response_model=RouteCluster, summary="Existing Phase 4 cluster assignment for a route")
def assignment(route_id: str, service: RouteRankerService = Depends(get_service)):
    return service.route_cluster(route_id)


@router.get("/clusters", response_model=list[ClusterSummary], summary="Saved cluster sizes and profiles")
def clusters(service: RouteRankerService = Depends(get_service)):
    return service.cluster_summaries()


@router.get("/metrics", response_model=list[ModelMetric], summary="Saved model evaluation metrics")
def metrics(service: RouteRankerService = Depends(get_service)):
    return service.model_metrics()
