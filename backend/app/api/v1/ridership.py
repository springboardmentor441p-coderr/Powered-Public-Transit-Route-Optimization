"""API v1 router for historical CTA route ridership time series."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import get_ridership_service
from app.schemas.ridership import RidershipTimeseriesResponse
from app.services.ridership_service import RidershipService

router = APIRouter(prefix="/ridership", tags=["Ridership"])


@router.get(
    "/routes/{route_id}/timeseries",
    response_model=RidershipTimeseriesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Historical Route Ridership Time Series",
    description=(
        "Retrieve bounded historical unlinked route boardings from DuckDB "
        "(analytical.daily_ridership) with monthly or daily granularity."
    ),
)
async def get_route_ridership_timeseries(
    route_id: str,
    start_date: Optional[date] = Query(
        None,
        description="Inclusive start date (YYYY-MM-DD, default 2024-01-01)",
    ),
    end_date: Optional[date] = Query(
        None,
        description="Inclusive end date (YYYY-MM-DD, default 2026-08-31)",
    ),
    granularity: str = Query(
        "monthly",
        description="Aggregation granularity ('monthly' or 'daily')",
    ),
    daytype: Optional[str] = Query(
        None,
        description="Optional daytype filter ('W'=Weekday, 'A'=Saturday, 'U'=Sunday/Holiday)",
    ),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=366,
        description="Optional maximum observations to return (1-366)",
    ),
    offset: int = Query(0, ge=0, description="Zero-based observation offset"),
    service: RidershipService = Depends(get_ridership_service),
) -> RidershipTimeseriesResponse:
    """Serve bounded historical ridership time series for a canonical CTA route."""
    return service.get_route_timeseries(
        route_id=route_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        daytype=daytype,
        limit=limit,
        offset=offset,
    )
