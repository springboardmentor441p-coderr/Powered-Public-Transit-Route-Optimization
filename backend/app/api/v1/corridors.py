"""API v1 router for Phase 6.2 & 6.3 corridor clusters and co-routing topology."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import get_corridor_service
from app.core.config import settings
from app.schemas.corridor import CorridorClusterListResponse, RouteCoRoutingResponse
from app.services.corridor_service import CorridorService

router = APIRouter(prefix="/corridors", tags=["Corridors"])


@router.get(
    "/clusters",
    response_model=CorridorClusterListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Corridor Cluster Assignments",
    description=(
        "Retrieve paginated route-direction corridor cluster assignments preserving "
        "geographic buffer overlap vs geometric Frechet shape distinctions."
    ),
)
async def list_corridor_clusters(
    k: int = Query(3, ge=2, le=12, description="Number of clusters (2-12)"),
    cluster_type: str = Query("buffer", description="Clustering method ('buffer' or 'frechet')"),
    cluster_id: Optional[int] = Query(None, ge=0, description="Filter by cluster ID"),
    mode: Optional[str] = Query(None, description="Filter by transit mode ('bus' or 'rail')"),
    route_id: Optional[str] = Query(None, description="Filter by canonical route ID"),
    direction_id: Optional[int] = Query(None, description="Filter by direction ID (0 or 1)"),
    sort_by: str = Query("pattern_id", description="Sort field"),
    order: str = Query("asc", description="Sort order ('asc' or 'desc')"),
    limit: int = Query(
        settings.DEFAULT_PAGE_LIMIT,
        ge=1,
        le=settings.MAX_PAGE_LIMIT,
        description="Maximum records per page (1-150)",
    ),
    offset: int = Query(0, ge=0, description="Zero-based pagination offset"),
    service: CorridorService = Depends(get_corridor_service),
) -> CorridorClusterListResponse:
    """Serve paginated corridor cluster assignments."""
    return service.list_corridor_clusters(
        k=k,
        cluster_type=cluster_type,
        cluster_id=cluster_id,
        mode=mode,
        route_id=route_id,
        direction_id=direction_id,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/routes/{route_id}/co-routing",
    response_model=RouteCoRoutingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Route Co-Routing & Overlap Profile",
    description=(
        "Retrieve directional geographic buffer overlap peers, stop-set Jaccard peers, "
        "and shared consecutive stop sequences for a canonical CTA route."
    ),
)
async def get_route_co_routing(
    route_id: str,
    direction_id: Optional[int] = Query(None, description="Optional direction filter (0 or 1)"),
    min_similarity: float = Query(
        0.0,
        ge=0.0,
        le=1.0,
        description="Minimum similarity/overlap threshold (0.0-1.0)",
    ),
    top_n: int = Query(10, ge=1, le=25, description="Maximum peer relationships per metric (1-25)"),
    service: CorridorService = Depends(get_corridor_service),
) -> RouteCoRoutingResponse:
    """Serve directional co-routing profile for a canonical route."""
    return service.get_route_co_routing(
        route_id=route_id,
        direction_id=direction_id,
        min_similarity=min_similarity,
        top_n=top_n,
    )
