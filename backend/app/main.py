from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.exceptions import _build_error_payload, register_exception_handlers
from app.core.hydration import RuntimeDataHydrator
from app.api.endpoints import router as health_router
from app.api.v1.router import api_v1_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Hydrate private runtime artifacts at startup when HF_HYDRATION_ENABLED is True."""
    hydrator: RuntimeDataHydrator = application.state.hydrator
    if settings.HF_HYDRATION_ENABLED:
        if settings.HYDRATION_STARTUP_MODE.lower() == "sync":
            hydrator.hydrate_sync()
        else:
            hydrator.start_background()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.state.hydrator = RuntimeDataHydrator(settings)

# Register global RFC 7807-style exception handlers
register_exception_handlers(app)

# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def guard_runtime_hydration(request: Request, call_next):
    """Block /api/v1/* requests while private runtime data hydration is incomplete or failed."""
    if request.url.path.startswith(settings.API_V1_PREFIX):
        hydrator: RuntimeDataHydrator = request.app.state.hydrator
        if hydrator.is_blocking_requests():
            snap = hydrator.snapshot()
            detail = (
                f"Runtime data hydration failed: {snap.last_error}"
                if snap.status == "failed"
                else f"Runtime data is warming up ({snap.verified_files}/{snap.total_files} files verified)."
            )
            payload = _build_error_payload(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="RUNTIME_DATA_NOT_READY",
                title="Service Unavailable",
                detail=detail,
                instance=str(request.url.path),
                details={"hydration_status": snap.status},
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=payload,
                headers={"Retry-After": "5"},
            )
    return await call_next(request)

# Register legacy health API routes with prefix /api
app.include_router(health_router, prefix="/api")

# Register modular API v1 routes with prefix /api/v1
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
async def root():
    """Root redirect / welcome endpoint."""
    return {
        "project": settings.PROJECT_NAME,
        "status": "online",
        "documentation": "/docs",
        "health_check": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
