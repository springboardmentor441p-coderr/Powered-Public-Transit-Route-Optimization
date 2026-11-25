from fastapi import APIRouter, status
from app.schemas.health import HealthCheckResponse
from app.core.config import settings

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Backend Health Check",
    description="Check the operational health and status of the AI_RouteRanker backend.",
    tags=["Health"],
)
async def health_check() -> HealthCheckResponse:
    """Returns application health status and metadata."""
    return HealthCheckResponse(
        status="ok",
        message="AI_RouteRanker backend is running successfully",
        project=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )
