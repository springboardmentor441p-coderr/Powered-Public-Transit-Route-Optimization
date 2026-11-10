"""Machine Learning API Router."""

from __future__ import annotations

from app.api.compat import APIRouter
from app.schemas.ml import ClusterRequest, ClusterResponse
from app.services.ml_service import MLService

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


@router.post("/cluster", response_model=ClusterResponse)
def run_clustering(req: ClusterRequest) -> ClusterResponse:
    """Run unsupervised clustering on route schedule features with evaluation metrics."""
    return MLService.cluster_routes(req)


@router.get("/clusters", response_model=ClusterResponse)
def get_clusters() -> ClusterResponse:
    """Get active clustering results, cluster profiles, and 2D visualization points."""
    return MLService.get_clusters()

