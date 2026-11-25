"""API v1 router for historical Random Forest evaluation predictions."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import get_forecast_service
from app.core.config import settings
from app.schemas.forecast import (
    HistoricalForecastResponse,
    HistoricalForecastSummaryResponse,
)
from app.services.forecast_service import ForecastService

router = APIRouter(prefix="/forecasting", tags=["Historical Forecasting Evaluation"])


@router.get(
    "/historical",
    response_model=HistoricalForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Historical Evaluation Predictions",
    description=(
        "Retrieve verified historical Random Forest validation, test, or August holdout "
        "predictions vs actual CTA ridership. Does not perform future-date forecasting."
    ),
)
async def get_historical_predictions(
    tier: str = Query("tier1", description="Model tier ('tier1' or 'tier2')"),
    period: str = Query(
        "august_holdout",
        description="Evaluation period ('validation', 'test', or 'august_holdout' [tier1 only])",
    ),
    route_id: Optional[str] = Query(None, description="Optional route ID filter"),
    start_date: Optional[date] = Query(None, description="Optional inclusive start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Optional inclusive end date (YYYY-MM-DD)"),
    limit: int = Query(
        settings.DEFAULT_PAGE_LIMIT,
        ge=1,
        le=settings.MAX_PAGE_LIMIT,
        description="Maximum records per page (1-150)",
    ),
    offset: int = Query(0, ge=0, description="Zero-based pagination offset"),
    service: ForecastService = Depends(get_forecast_service),
) -> HistoricalForecastResponse:
    """Serve verified historical Random Forest evaluation predictions."""
    return service.get_historical_predictions(
        tier=tier,
        period=period,
        route_id=route_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/historical/summary",
    response_model=HistoricalForecastSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Historical Evaluation Metrics Summary",
    description="Retrieve verified aggregate WAPE, MAE, RMSE, and R^2 metrics for historical evaluation periods.",
)
async def get_historical_summary(
    tier: Optional[str] = Query(None, description="Optional tier filter ('tier1' or 'tier2')"),
    period: Optional[str] = Query(None, description="Optional period filter"),
    service: ForecastService = Depends(get_forecast_service),
) -> HistoricalForecastSummaryResponse:
    """Serve verified aggregate historical evaluation metrics."""
    return service.get_historical_summary(tier=tier, period=period)
