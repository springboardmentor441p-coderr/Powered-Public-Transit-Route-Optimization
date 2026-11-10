"""Health Check API Router."""

from __future__ import annotations

from datetime import datetime
from app.api.compat import APIRouter
from app.core.database import db
from app.schemas.common import HealthResponse

router = APIRouter(prefix="", tags=["System"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """System health check and database status."""
    ready = db.is_data_ready()
    tables = db.get_registered_tables()
    return HealthResponse(
        status="healthy" if ready else "initializing",
        version="1.0.0",
        data_loaded=ready,
        duckdb_available=db.is_duckdb_available(),
        timestamp=datetime.utcnow().isoformat() + "Z",
        tables_registered=tables,
    )

