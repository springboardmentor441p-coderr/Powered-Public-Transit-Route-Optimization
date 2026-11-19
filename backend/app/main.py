"""FastAPI application entry point for Manhattan Bus Transit Optimization."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.data import load_app_data
from backend.app.routers import evaluation, gtfs, history, overview, replay, review, routes, scenarios
from backend.app.runtime_store import RuntimeStore


def create_app(app_data_dir: Path | None = None, runtime_dir: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = load_app_data(app_data_dir)
        app.state.runtime = RuntimeStore(runtime_dir)
        yield
        app.state.runtime.close()

    app = FastAPI(
        title="Manhattan Bus Transit Optimization API",
        version="1.0.0",
        description="Analytics, historical replay, scenario calculation and safe GTFS upload inspection. Reads app_data/ and the frozen model; writes only replay sessions and saved scenarios to backend/runtime/.",
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
    app.include_router(history.router)
    app.include_router(replay.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()

