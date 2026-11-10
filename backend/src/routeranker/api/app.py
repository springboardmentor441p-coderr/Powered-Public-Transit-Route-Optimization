"""FastAPI application factory and consistent API error handling."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .data_access import DataRepository, DatasetUnavailable
from .routes import analytics, machine_learning, routes, stops
from .schemas import ErrorResponse
from .services import InvalidFilter, RecordNotFound, RouteRankerService


def create_app(settings: Settings | None = None, repository: DataRepository | None = None) -> FastAPI:
    """Build app; datasets are read lazily and cached when endpoints request them."""
    settings = settings or Settings.from_environment()
    app = FastAPI(
        title="RouteRanker API", version="1.0.0",
        description=("REST access to processed Chennai MTC GTFS schedules, derived analytics, "
                     "and saved unsupervised cluster results. Values describe scheduled service only."),
        docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.state.repository = repository or DataRepository(settings.processed_dir)
    app.state.service = RouteRankerService(app.state.repository)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_credentials=False, allow_methods=["GET"], allow_headers=["*"])

    @app.exception_handler(RecordNotFound)
    async def not_found_handler(_: Request, exc: RecordNotFound):
        return JSONResponse(status_code=404, content=ErrorResponse(detail=str(exc), code="not_found").model_dump())

    @app.exception_handler(DatasetUnavailable)
    async def unavailable_handler(_: Request, _exc: DatasetUnavailable):
        # Dataset paths and operating-system details stay in server diagnostics.
        return JSONResponse(status_code=503, content=ErrorResponse(detail="A required processed dataset is unavailable.", code="dataset_unavailable").model_dump())

    @app.exception_handler(InvalidFilter)
    async def invalid_filter_handler(_: Request, exc: InvalidFilter):
        return JSONResponse(status_code=422, content=ErrorResponse(detail=str(exc), code="invalid_filter").model_dump())

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_: Request, exc: RequestValidationError):
        errors = [{"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors, "code": "validation_error"})

    prefix = settings.api_prefix
    for group in (routes.router, stops.router, analytics.router, machine_learning.router):
        app.include_router(group, prefix=prefix)

    @app.get("/health", tags=["system"], summary="API process health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
