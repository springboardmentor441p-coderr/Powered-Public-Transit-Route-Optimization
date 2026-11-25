"""API v1 router for Phase 6.1 spatial hub rankings and DBSCAN clusters."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import get_spatial_service
from app.core.config import settings
from app.schemas.spatial import (
    ClusterSummaryResponse,
    SpatialHubsListResponse,
    TopHubsResponse,
)
from app.services.spatial_service import SpatialService

router = APIRouter(prefix="/spatial", tags=["Spatial Hubs"])


@router.get(
    "/hubs/top",
    response_model=TopHubsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Top 100 Transit Hubs",
    description="Retrieve paginated top-100 CTA transit hubs with Leaflet-ready coordinates.",
)
async def get_top_hubs(
    config: str = Query("a", description="Hub scoring configuration ('a', 'b', or 'c')"),
    limit: int = Query(
        settings.DEFAULT_PAGE_LIMIT,
        ge=1,
        le=100,
        description="Maximum records per page (1-100)",
    ),
    offset: int = Query(0, ge=0, description="Zero-based pagination offset"),
    service: SpatialService = Depends(get_spatial_service),
) -> TopHubsResponse:
    """Serve top-100 ranked transit hubs."""
    return service.get_top_hubs(config=config, limit=limit, offset=offset)


@router.get(
    "/hubs",
    response_model=SpatialHubsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Spatial Stops and Transit Hubs",
    description=(
        "Retrieve paginated transit stops with DBSCAN cluster assignments, "
        "hub ranking eligibility, and bounding-box viewport filtering."
    ),
)
async def list_spatial_hubs(
    config: str = Query("a", description="Hub scoring configuration ('a', 'b', or 'c')"),
    min_routes: Optional[int] = Query(None, ge=1, description="Minimum routes served filter"),
    dbscan_cluster: Optional[int] = Query(
        None,
        ge=-1,
        description="DBSCAN cluster ID (-1 for noise stops, 0..116 for spatial clusters)",
    ),
    eligible_only: bool = Query(False, description="Return only hub-ranking-eligible stops"),
    min_lat: Optional[float] = Query(None, description="Bounding box minimum latitude"),
    min_lon: Optional[float] = Query(None, description="Bounding box minimum longitude"),
    max_lat: Optional[float] = Query(None, description="Bounding box maximum latitude"),
    max_lon: Optional[float] = Query(None, description="Bounding box maximum longitude"),
    sort_by: str = Query("rank", description="Sort field ('rank', 'score', 'total_visits', 'routes_served', 'stop_id')"),
    order: str = Query("asc", description="Sort order ('asc' or 'desc')"),
    limit: int = Query(
        settings.DEFAULT_PAGE_LIMIT,
        ge=1,
        le=settings.MAX_PAGE_LIMIT,
        description="Maximum records per page (1-150)",
    ),
    offset: int = Query(0, ge=0, description="Zero-based pagination offset"),
    service: SpatialService = Depends(get_spatial_service),
) -> SpatialHubsListResponse:
    """Serve bounded spatial stop/hub directory with viewport and cluster filtering."""
    return service.list_spatial_hubs(
        config=config,
        min_routes=min_routes,
        dbscan_cluster=dbscan_cluster,
        eligible_only=eligible_only,
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/clusters/summary",
    response_model=ClusterSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Spatial Clustering Summary",
    description="Retrieve Phase 6.1 DBSCAN and KMeans spatial clustering overview and coverage metrics.",
)
async def get_cluster_summary(
    service: SpatialService = Depends(get_spatial_service),
) -> ClusterSummaryResponse:
    """Serve Phase 6.1 spatial clustering summary."""
    return service.get_cluster_summary()
