"""Data Quality and Pipeline Status API Router."""

from __future__ import annotations

from app.api.compat import APIRouter
from app.schemas.common import StatusResponse
from app.schemas.dashboard import DataQualityReportResponse
from app.services.data_service import DataService

router = APIRouter(prefix="/data", tags=["Data Quality"])


@router.get("/quality", response_model=DataQualityReportResponse)
def get_data_quality() -> DataQualityReportResponse:
    """Detailed audit report on data quality, referential integrity, and sanitization fixes."""
    return DataService.get_quality_report()


@router.get("/status", response_model=StatusResponse)
def get_data_status() -> StatusResponse:
    """Current state of processed parquet tables and analytical database views."""
    return DataService.get_data_status()

