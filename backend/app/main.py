"""RouteRanker FastAPI Backend Application.

Initializes the application, configures CORS, mounts API routers,
and executes the GTFS data preprocessing pipeline and ML model training on startup.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Add backend directory to path if executed directly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.api.compat import FastAPI, CORSMiddleware, HAS_FASTAPI
from app.api.analytics import router as analytics_router
from app.api.coverage import router as coverage_router
from app.api.dashboard import router as dashboard_router
from app.api.data import router as data_router
from app.api.health import router as health_router
from app.api.insights import router as insights_router
from app.api.ml import router as ml_router
from app.api.optimization import router as optimization_router
from app.api.overlap import router as overlap_router
from app.api.routes import router as routes_router
from app.core.config import settings
from app.core.database import db
from data_processing.feature_engineering import RouteFeatureEngineer
from data_processing.preprocessing import GTFSPreprocessor
from ml.clustering import RouteClusteringPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("routeranker")


def create_app() -> FastAPI:
    """Factory function to build and configure the RouteRanker application."""
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="High-performance GTFS analytical engine, route clustering, and schedule scenario simulation API.",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Configure CORS
    if HAS_FASTAPI:
        from fastapi.middleware.cors import CORSMiddleware as RealCORSMiddleware
        application.add_middleware(
            RealCORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Startup event: execute pipeline if data not ready
    @application.on_event("startup")
    def startup_event() -> None:
        logger.info("Initializing RouteRanker Backend Application...")
        settings.ensure_directories()

        if not db.is_data_ready():
            logger.info("Processed data not detected. Executing GTFS preprocessing pipeline...")
            preprocessor = GTFSPreprocessor()
            prep_result = preprocessor.run_pipeline()
            logger.info(f"Preprocessing completed: {prep_result.get('elapsed_seconds')}s, Quality Score={prep_result.get('quality_score')}%")

            logger.info("Computing schedule-derived route features...")
            engineer = RouteFeatureEngineer()
            engineer.build_features()
            logger.info("Route features successfully engineered.")

        # Train baseline clustering models if not already saved
        kmeans_path = settings.DATA_MODELS_DIR / "kmeans_model.joblib"
        if not kmeans_path.exists():
            logger.info("Training initial ML clustering models...")
            features_df = db.get_table("route_features")
            pipeline = RouteClusteringPipeline()
            pipeline.fit_kmeans(features_df, n_clusters=4)
            pipeline.fit_dbscan(features_df, eps=1.2, min_samples=5)
            logger.info("Initial ML models saved to data/models/")

        # Initialize analytical database views
        if db.is_duckdb_available():
            db.get_duckdb_conn()
            logger.info("DuckDB analytical database views active.")

        logger.info("RouteRanker Backend initialization complete. API is ready.")

    # Mount API routers
    application.include_router(health_router, prefix=settings.API_V1_PREFIX)
    application.include_router(dashboard_router, prefix=settings.API_V1_PREFIX)
    application.include_router(routes_router, prefix=settings.API_V1_PREFIX)
    application.include_router(coverage_router, prefix=settings.API_V1_PREFIX)
    application.include_router(overlap_router, prefix=settings.API_V1_PREFIX)
    application.include_router(analytics_router, prefix=settings.API_V1_PREFIX)
    application.include_router(ml_router, prefix=settings.API_V1_PREFIX)
    application.include_router(optimization_router, prefix=settings.API_V1_PREFIX)
    application.include_router(data_router, prefix=settings.API_V1_PREFIX)
    application.include_router(insights_router, prefix=settings.API_V1_PREFIX)

    @application.get("/")
    def root() -> dict:
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs": "/api/docs",
            "health": "/api/health",
        }

    return application


app = create_app()


if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
    except ImportError:
        logger.warning("Uvicorn not found. Running standalone pipeline verification...")
        preprocessor = GTFSPreprocessor()
        preprocessor.run_pipeline()
        engineer = RouteFeatureEngineer()
        engineer.build_features()
        print("Pipeline verified successfully.")

