from fastapi import APIRouter, Request, status
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
async def health_check(request: Request) -> HealthCheckResponse:
    """Returns application health status, environment, and runtime data availability."""
    missing = sum(1 for p in settings.runtime_required_paths if not p.exists())
    hydrator = getattr(request.app.state, "hydrator", None)
    snap = hydrator.snapshot() if hydrator is not None else None
    hydration_status = snap.status if snap is not None else "disabled"
    hydration_progress = (
        f"{snap.verified_files}/{snap.total_files} files verified"
        if snap is not None and settings.HF_HYDRATION_ENABLED
        else None
    )
    hydration_error = snap.last_error if snap is not None else None
    data_ready = (missing == 0) and (
        not settings.HF_HYDRATION_ENABLED or hydration_status == "ready"
    )

    if data_ready:
        msg = "AI_RouteRanker backend is running successfully"
    elif settings.HF_HYDRATION_ENABLED and hydration_status in ("idle", "hydrating"):
        msg = f"AI_RouteRanker backend is warming up ({hydration_progress})"
    elif settings.HF_HYDRATION_ENABLED and hydration_status == "failed":
        msg = "AI_RouteRanker backend runtime data hydration failed"
    else:
        msg = f"AI_RouteRanker backend is running, but {missing} runtime artifact(s) are missing"

    return HealthCheckResponse(
        status="ok",
        message=msg,
        project=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        data_ready=data_ready,
        missing_artifacts_count=missing,
        hydration_status=hydration_status,
        hydration_progress=hydration_progress,
        hydration_error=hydration_error,
    )
