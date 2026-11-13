"""FastAPI application entry point for Manhattan Bus Transit Optimization."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.data import load_app_data
from backend.app.routers import evaluation, gtfs, overview, review, routes, scenarios


def create_app(app_data_dir: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = load_app_data(app_data_dir)
        yield

    app = FastAPI(
        title="Manhattan Bus Transit Optimization API",
        version="1.0.0",
        description="Read-only analytics, scenario calculation, and safe GTFS upload inspection API backed exclusively by app_data/.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(overview.router)
    app.include_router(routes.router)
    app.include_router(review.router)
    app.include_router(scenarios.router)
    app.include_router(evaluation.router)
    app.include_router(gtfs.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()

